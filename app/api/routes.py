import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import (
    Repository, Workflow, WorkflowRun, Job, Step, LLMCall, Recommendation,
)
from app.services.github_client import GitHubClient
from app.services.cost_calculator import update_all_costs

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/api/repos")
def list_repos(db: Session = Depends(get_db)):
    repos = db.query(Repository).order_by(Repository.full_name).all()
    return [
        {
            "id": r.id,
            "full_name": r.full_name,
            "default_branch": r.default_branch,
            "last_collected_at": r.last_collected_at.isoformat() if r.last_collected_at else None,
        }
        for r in repos
    ]


@router.post("/api/collect")
def collect_data(db: Session = Depends(get_db)):
    client = GitHubClient()
    stats = client.collect_all(db)
    update_all_costs(db)
    return {"status": "ok", "stats": stats}


@router.get("/api/overview")
def overview_metrics(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    repo: Optional[str] = Query(None),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    runs_query = db.query(WorkflowRun).filter(WorkflowRun.started_at >= since)
    if repo:
        runs_query = runs_query.join(Workflow).join(Repository).filter(
            Repository.full_name == repo
        )

    runs = runs_query.all()

    total_runs = len(runs)
    successful = sum(1 for r in runs if r.conclusion == "success")
    failed = sum(1 for r in runs if r.conclusion == "failure")
    durations = [r.duration_seconds for r in runs if r.duration_seconds]
    avg_duration = round(sum(durations) / len(durations)) if durations else 0

    total_compute_cost = sum(r.total_compute_cost or 0 for r in runs)
    total_llm_cost = sum(r.total_llm_cost or 0 for r in runs)

    llm_query = db.query(LLMCall).filter(LLMCall.timestamp >= since)
    if repo:
        llm_query = llm_query.filter(LLMCall.repo_full_name == repo)
    llm_calls = llm_query.all()

    total_tokens = sum(c.input_tokens + c.output_tokens for c in llm_calls)

    return {
        "total_runs": total_runs,
        "successful_runs": successful,
        "failed_runs": failed,
        "success_rate": round(successful / total_runs * 100, 1) if total_runs else 0,
        "avg_duration_seconds": avg_duration,
        "total_compute_cost": round(total_compute_cost, 2),
        "total_llm_cost": round(total_llm_cost, 2),
        "total_cost": round(total_compute_cost + total_llm_cost, 2),
        "total_llm_calls": len(llm_calls),
        "total_tokens": total_tokens,
        "period_days": days,
    }


@router.get("/api/runs")
def list_runs(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    repo: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        db.query(WorkflowRun)
        .join(Workflow)
        .join(Repository)
        .filter(WorkflowRun.started_at >= since)
    )
    if repo:
        query = query.filter(Repository.full_name == repo)

    runs = query.order_by(WorkflowRun.started_at.desc()).limit(limit).all()

    return [
        {
            "id": r.id,
            "run_number": r.run_number,
            "workflow_name": r.workflow.name,
            "repo_name": r.workflow.repository.full_name,
            "conclusion": r.conclusion,
            "trigger_event": r.trigger_event,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "duration_seconds": r.duration_seconds,
            "compute_cost": r.total_compute_cost,
            "llm_cost": r.total_llm_cost,
            "total_cost": round((r.total_compute_cost or 0) + (r.total_llm_cost or 0), 4),
            "branch": r.branch,
            "commit_sha": r.commit_sha[:8] if r.commit_sha else None,
        }
        for r in runs
    ]


@router.get("/api/runs/{run_id}/jobs")
def run_jobs(run_id: int, db: Session = Depends(get_db)):
    jobs = (
        db.query(Job)
        .filter(Job.run_id == run_id)
        .order_by(Job.started_at)
        .all()
    )
    return [
        {
            "id": j.id,
            "name": j.name,
            "runner_os": j.runner_os,
            "runner_type": j.runner_type,
            "conclusion": j.conclusion,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "duration_seconds": j.duration_seconds,
            "steps": [
                {
                    "name": s.name,
                    "number": s.number,
                    "conclusion": s.conclusion,
                    "duration_seconds": s.duration_seconds,
                }
                for s in sorted(j.steps, key=lambda s: s.number)
            ],
        }
        for j in jobs
    ]


@router.get("/api/cost-trends")
def cost_trends(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    repo: Optional[str] = Query(None),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(WorkflowRun).filter(WorkflowRun.started_at >= since)
    if repo:
        query = query.join(Workflow).join(Repository).filter(
            Repository.full_name == repo
        )
    runs = query.order_by(WorkflowRun.started_at).all()

    daily = {}
    for r in runs:
        if not r.started_at:
            continue
        day = r.started_at.strftime("%Y-%m-%d")
        if day not in daily:
            daily[day] = {"date": day, "compute_cost": 0, "llm_cost": 0, "runs": 0, "avg_duration": 0, "total_duration": 0}
        daily[day]["compute_cost"] += r.total_compute_cost or 0
        daily[day]["llm_cost"] += r.total_llm_cost or 0
        daily[day]["runs"] += 1
        daily[day]["total_duration"] += r.duration_seconds or 0

    for d in daily.values():
        d["compute_cost"] = round(d["compute_cost"], 4)
        d["llm_cost"] = round(d["llm_cost"], 4)
        d["total_cost"] = round(d["compute_cost"] + d["llm_cost"], 4)
        d["avg_duration"] = round(d["total_duration"] / d["runs"]) if d["runs"] else 0
        del d["total_duration"]

    return sorted(daily.values(), key=lambda x: x["date"])


@router.get("/api/llm-usage")
def llm_usage(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    repo: Optional[str] = Query(None),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(LLMCall).filter(LLMCall.timestamp >= since)
    if repo:
        query = query.filter(LLMCall.repo_full_name == repo)
    calls = query.all()

    by_model = {}
    by_purpose = {}
    for c in calls:
        key = f"{c.provider}/{c.model}"
        if key not in by_model:
            by_model[key] = {"model": key, "calls": 0, "tokens": 0, "cost": 0, "avg_latency_ms": 0, "total_latency": 0}
        by_model[key]["calls"] += 1
        by_model[key]["tokens"] += c.input_tokens + c.output_tokens
        by_model[key]["cost"] += c.estimated_cost or 0
        by_model[key]["total_latency"] += c.latency_ms or 0

        purpose = c.purpose or "unknown"
        if purpose not in by_purpose:
            by_purpose[purpose] = {"purpose": purpose, "calls": 0, "tokens": 0, "cost": 0}
        by_purpose[purpose]["calls"] += 1
        by_purpose[purpose]["tokens"] += c.input_tokens + c.output_tokens
        by_purpose[purpose]["cost"] += c.estimated_cost or 0

    for m in by_model.values():
        m["cost"] = round(m["cost"], 4)
        m["avg_latency_ms"] = round(m["total_latency"] / m["calls"]) if m["calls"] else 0
        del m["total_latency"]

    for p in by_purpose.values():
        p["cost"] = round(p["cost"], 4)

    return {
        "total_calls": len(calls),
        "total_tokens": sum(c.input_tokens + c.output_tokens for c in calls),
        "total_cost": round(sum(c.estimated_cost or 0 for c in calls), 4),
        "by_model": sorted(by_model.values(), key=lambda x: x["cost"], reverse=True),
        "by_purpose": sorted(by_purpose.values(), key=lambda x: x["cost"], reverse=True),
    }


@router.get("/api/top-workflows")
def top_workflows(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    runs = (
        db.query(WorkflowRun)
        .join(Workflow)
        .join(Repository)
        .filter(WorkflowRun.started_at >= since)
        .all()
    )

    by_workflow = {}
    for r in runs:
        key = f"{r.workflow.repository.full_name}/{r.workflow.name}"
        if key not in by_workflow:
            by_workflow[key] = {
                "workflow": key, "runs": 0, "total_cost": 0,
                "avg_duration": 0, "total_duration": 0,
                "success_rate": 0, "successes": 0,
            }
        by_workflow[key]["runs"] += 1
        by_workflow[key]["total_cost"] += (r.total_compute_cost or 0) + (r.total_llm_cost or 0)
        by_workflow[key]["total_duration"] += r.duration_seconds or 0
        if r.conclusion == "success":
            by_workflow[key]["successes"] += 1

    for w in by_workflow.values():
        w["total_cost"] = round(w["total_cost"], 4)
        w["avg_duration"] = round(w["total_duration"] / w["runs"]) if w["runs"] else 0
        w["success_rate"] = round(w["successes"] / w["runs"] * 100, 1) if w["runs"] else 0
        del w["total_duration"]
        del w["successes"]

    top = sorted(by_workflow.values(), key=lambda x: x["total_cost"], reverse=True)[:limit]
    return top


@router.get("/api/recommendations")
def list_recommendations(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
):
    query = db.query(Recommendation)
    if status:
        query = query.filter(Recommendation.status == status)
    recs = query.order_by(Recommendation.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "category": r.category,
            "title": r.title,
            "description": r.description,
            "estimated_savings": r.estimated_savings,
            "priority": r.priority,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recs
    ]


@router.post("/api/recommendations/{rec_id}/status")
def update_recommendation_status(
    rec_id: int,
    new_status: str = Query(...),
    db: Session = Depends(get_db),
):
    rec = db.query(Recommendation).filter_by(id=rec_id).first()
    if not rec:
        return {"error": "not found"}, 404
    rec.status = new_status
    db.commit()
    return {"status": "ok", "new_status": new_status}

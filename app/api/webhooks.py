import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import LLMCall, WorkflowRun

logger = logging.getLogger(__name__)
router = APIRouter()


class LLMCallPayload(BaseModel):
    provider: str
    model: str
    purpose: Optional[str] = None
    input_tokens: int
    output_tokens: int
    latency_ms: Optional[int] = None
    timestamp: Optional[str] = None
    repo_full_name: Optional[str] = None
    workflow_name: Optional[str] = None
    job_name: Optional[str] = None
    step_name: Optional[str] = None
    github_run_id: Optional[int] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None


class IngestPayload(BaseModel):
    calls: list[LLMCallPayload]


@router.post("/api/ingest")
def ingest_llm_calls(payload: IngestPayload, db: Session = Depends(get_db)):
    from app.services.cost_calculator import compute_llm_call_cost

    saved = 0
    for call_data in payload.calls:
        run_id = None
        if call_data.github_run_id:
            run = db.query(WorkflowRun).filter_by(
                github_run_id=call_data.github_run_id
            ).first()
            if run:
                run_id = run.id

        ts = datetime.now(timezone.utc)
        if call_data.timestamp:
            try:
                ts = datetime.fromisoformat(call_data.timestamp.replace("Z", "+00:00"))
            except ValueError:
                pass

        llm_call = LLMCall(
            run_id=run_id,
            provider=call_data.provider,
            model=call_data.model,
            purpose=call_data.purpose,
            input_tokens=call_data.input_tokens,
            output_tokens=call_data.output_tokens,
            latency_ms=call_data.latency_ms,
            timestamp=ts,
            repo_full_name=call_data.repo_full_name,
            workflow_name=call_data.workflow_name,
            job_name=call_data.job_name,
            step_name=call_data.step_name,
            github_run_id=call_data.github_run_id,
            commit_sha=call_data.commit_sha,
            branch=call_data.branch,
        )
        llm_call.estimated_cost = compute_llm_call_cost(llm_call)
        db.add(llm_call)
        saved += 1

    db.commit()
    logger.info(f"Ingested {saved} LLM calls")
    return {"status": "ok", "ingested": saved}

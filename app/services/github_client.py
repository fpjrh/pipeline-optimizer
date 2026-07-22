import json
import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.models.schemas import Repository, Workflow, WorkflowRun, Job, Step

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, url: str, params: Optional[dict] = None) -> dict | list:
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def _get_paginated(self, url: str, params: Optional[dict] = None, max_pages: int = 10) -> list:
        params = params or {}
        params.setdefault("per_page", 100)
        results = []
        for page in range(1, max_pages + 1):
            params["page"] = page
            data = self._get(url, params)
            if not data:
                break
            results.extend(data)
            if len(data) < params["per_page"]:
                break
        return results

    def discover_repos(self) -> list[dict]:
        if settings.repo_list:
            repos = []
            for full_name in settings.repo_list:
                try:
                    repo = self._get(f"{GITHUB_API}/repos/{full_name}")
                    repos.append(repo)
                except requests.HTTPError as e:
                    logger.warning(f"Could not fetch repo {full_name}: {e}")
            return repos

        if settings.github_org:
            return self._get_paginated(
                f"{GITHUB_API}/orgs/{settings.github_org}/repos",
                params={"type": "all", "sort": "updated"},
            )

        return self._get_paginated(
            f"{GITHUB_API}/user/repos",
            params={"sort": "updated", "affiliation": "owner,collaborator,organization_member"},
        )

    def get_workflows(self, repo_full_name: str) -> list[dict]:
        data = self._get(f"{GITHUB_API}/repos/{repo_full_name}/actions/workflows")
        return data.get("workflows", [])

    def get_workflow_yaml(self, repo_full_name: str, workflow_path: str) -> Optional[str]:
        try:
            url = f"{GITHUB_API}/repos/{repo_full_name}/contents/{workflow_path}"
            data = self._get(url)
            if data.get("encoding") == "base64":
                import base64
                return base64.b64decode(data["content"]).decode("utf-8")
        except requests.HTTPError:
            logger.warning(f"Could not fetch workflow YAML: {repo_full_name}/{workflow_path}")
        return None

    def get_workflow_runs(
        self, repo_full_name: str, workflow_id: int, since: Optional[datetime] = None
    ) -> list[dict]:
        params = {"status": "completed"}
        if since:
            params["created"] = f">={since.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        data = self._get(
            f"{GITHUB_API}/repos/{repo_full_name}/actions/workflows/{workflow_id}/runs",
            params=params,
        )
        return data.get("workflow_runs", [])

    def get_run_jobs(self, repo_full_name: str, run_id: int) -> list[dict]:
        data = self._get(
            f"{GITHUB_API}/repos/{repo_full_name}/actions/runs/{run_id}/jobs"
        )
        return data.get("jobs", [])

    def collect_all(self, db: Session) -> dict:
        stats = {"repos": 0, "workflows": 0, "runs": 0, "jobs": 0, "steps": 0}
        repos = self.discover_repos()
        logger.info(f"Found {len(repos)} repositories")

        for repo_data in repos:
            repo = self._upsert_repo(db, repo_data)
            stats["repos"] += 1

            workflows = self.get_workflows(repo.full_name)
            for wf_data in workflows:
                if wf_data.get("state") != "active":
                    continue

                workflow = self._upsert_workflow(db, repo, wf_data)
                stats["workflows"] += 1

                runs = self.get_workflow_runs(
                    repo.full_name, workflow.github_id, since=repo.last_collected_at
                )
                for run_data in runs:
                    run = self._upsert_run(db, workflow, run_data)
                    if run is None:
                        continue
                    stats["runs"] += 1

                    jobs = self.get_run_jobs(repo.full_name, run_data["id"])
                    for job_data in jobs:
                        job = self._upsert_job(db, run, job_data)
                        if job is None:
                            continue
                        stats["jobs"] += 1
                        stats["steps"] += len(job_data.get("steps", []))

            repo.last_collected_at = datetime.now(timezone.utc)
            db.commit()

        logger.info(f"Collection complete: {stats}")
        return stats

    def _upsert_repo(self, db: Session, data: dict) -> Repository:
        repo = db.query(Repository).filter_by(github_id=data["id"]).first()
        if not repo:
            repo = Repository(
                github_id=data["id"],
                full_name=data["full_name"],
                default_branch=data.get("default_branch", "main"),
            )
            db.add(repo)
            db.commit()
        return repo

    def _upsert_workflow(self, db: Session, repo: Repository, data: dict) -> Workflow:
        workflow = db.query(Workflow).filter_by(github_id=data["id"]).first()
        yaml_content = self.get_workflow_yaml(repo.full_name, data["path"])

        if not workflow:
            workflow = Workflow(
                repo_id=repo.id,
                github_id=data["id"],
                name=data["name"],
                path=data["path"],
                yaml_content=yaml_content,
            )
            db.add(workflow)
            db.commit()
        elif yaml_content:
            workflow.yaml_content = yaml_content
            db.commit()
        return workflow

    def _upsert_run(self, db: Session, workflow: Workflow, data: dict) -> Optional[WorkflowRun]:
        existing = db.query(WorkflowRun).filter_by(github_run_id=data["id"]).first()
        if existing:
            return None

        started = _parse_dt(data.get("run_started_at"))
        completed = _parse_dt(data.get("updated_at"))
        duration = None
        if started and completed:
            duration = int((completed - started).total_seconds())

        run = WorkflowRun(
            workflow_id=workflow.id,
            github_run_id=data["id"],
            run_number=data["run_number"],
            status=data.get("status"),
            conclusion=data.get("conclusion"),
            trigger_event=data.get("event"),
            started_at=started,
            completed_at=completed,
            duration_seconds=duration,
            commit_sha=data.get("head_sha"),
            branch=data.get("head_branch"),
        )
        db.add(run)
        db.commit()
        return run

    def _upsert_job(self, db: Session, run: WorkflowRun, data: dict) -> Optional[Job]:
        existing = db.query(Job).filter_by(github_job_id=data["id"]).first()
        if existing:
            return None

        started = _parse_dt(data.get("started_at"))
        completed = _parse_dt(data.get("completed_at"))
        duration = None
        if started and completed:
            duration = int((completed - started).total_seconds())

        depends_on = None
        if data.get("steps"):
            pass
        # GitHub API doesn't directly expose `needs` — we parse it from workflow YAML later

        job = Job(
            run_id=run.id,
            github_job_id=data["id"],
            name=data["name"],
            runner_os=data.get("runner_name"),
            runner_type=data.get("labels", [None])[0] if data.get("labels") else None,
            started_at=started,
            completed_at=completed,
            duration_seconds=duration,
            conclusion=data.get("conclusion"),
            depends_on=depends_on,
        )
        db.add(job)
        db.flush()

        for step_data in data.get("steps", []):
            s_started = _parse_dt(step_data.get("started_at"))
            s_completed = _parse_dt(step_data.get("completed_at"))
            s_duration = None
            if s_started and s_completed:
                s_duration = int((s_completed - s_started).total_seconds())

            step = Step(
                job_id=job.id,
                name=step_data["name"],
                number=step_data["number"],
                started_at=s_started,
                completed_at=s_completed,
                duration_seconds=s_duration,
                conclusion=step_data.get("conclusion"),
            )
            db.add(step)

        db.commit()
        return job


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None

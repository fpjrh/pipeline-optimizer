import logging
from sqlalchemy.orm import Session

from app.models.schemas import Job, WorkflowRun, LLMCall

logger = logging.getLogger(__name__)

RUNNER_COST_PER_MINUTE = {
    "ubuntu-latest": 0.008,
    "ubuntu-24.04": 0.008,
    "ubuntu-22.04": 0.008,
    "ubuntu-20.04": 0.008,
    "windows-latest": 0.016,
    "windows-2022": 0.016,
    "windows-2019": 0.016,
    "macos-latest": 0.08,
    "macos-15": 0.08,
    "macos-14": 0.08,
    "macos-13": 0.08,
}

RUNNER_COST_DEFAULT = 0.008  # assume Linux if unknown

# Cost per 1M tokens (input, output)
LLM_PRICING = {
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (15.0, 75.0),
    "claude-haiku-4-5": (0.80, 4.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (0.80, 4.0),
    "claude-3-opus-20240229": (15.0, 75.0),
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o3": (10.0, 40.0),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
}


def compute_job_cost(job: Job) -> float:
    if not job.duration_seconds:
        return 0.0
    minutes = job.duration_seconds / 60.0
    runner = (job.runner_type or "").lower()
    rate = RUNNER_COST_PER_MINUTE.get(runner, RUNNER_COST_DEFAULT)
    return round(minutes * rate, 6)


def compute_llm_call_cost(call: LLMCall) -> float:
    model = call.model or ""
    pricing = LLM_PRICING.get(model)
    if not pricing:
        for key, val in LLM_PRICING.items():
            if key in model or model in key:
                pricing = val
                break
    if not pricing:
        pricing = (3.0, 15.0)  # default to Sonnet-tier pricing

    input_cost = (call.input_tokens / 1_000_000) * pricing[0]
    output_cost = (call.output_tokens / 1_000_000) * pricing[1]
    return round(input_cost + output_cost, 6)


def update_run_costs(db: Session, run: WorkflowRun):
    compute_cost = 0.0
    for job in run.jobs:
        compute_cost += compute_job_cost(job)

    llm_cost = 0.0
    for call in run.llm_calls:
        call_cost = compute_llm_call_cost(call)
        call.estimated_cost = call_cost
        llm_cost += call_cost

    run.total_compute_cost = round(compute_cost, 6)
    run.total_llm_cost = round(llm_cost, 6)
    db.commit()


def update_all_costs(db: Session):
    runs = db.query(WorkflowRun).all()
    for run in runs:
        update_run_costs(db, run)
    logger.info(f"Updated costs for {len(runs)} runs")

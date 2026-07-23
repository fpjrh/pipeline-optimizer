# Pipeline Optimizer — Architecture Plan

## Context
Build a standalone AI agent that optimizes GitHub Actions pipelines for upcoming projects. These pipelines will heavily use AI/LLM calls (Anthropic, OpenAI, LangChain, etc.) alongside standard CI/CD tasks. The agent needs to track both compute costs and LLM token expenses, then provide intelligent optimization recommendations balancing pipeline velocity against total cost.

This is greenfield — the project and the pipelines it will monitor are both new.

## Project Location
`/Users/fpj/Development/python/pipeline-optimizer/`

## Tech Stack
- **Backend**: Python, FastAPI, SQLAlchemy, Pydantic Settings
- **Database**: SQLite
- **Frontend**: HTML/CSS/JS, Chart.js
- **GitHub**: PyGithub or `gh` CLI / REST API
- **AI Agent**: Anthropic SDK (Claude)

---

## Project Structure

```
pipeline-optimizer/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Pydantic Settings
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLAlchemy engine/session
│   │   └── schemas.py             # ORM models
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # Dashboard & metrics endpoints
│   │   └── webhooks.py            # Ingest endpoint for instrumentation data
│   ├── services/
│   │   ├── __init__.py
│   │   ├── github_client.py       # GitHub Actions API data collection
│   │   ├── analyzer.py            # Pipeline analysis engine
│   │   ├── cost_calculator.py     # Cost computation (compute + tokens)
│   │   └── agent.py               # AI agent for recommendations
│   ├── templates/
│   │   └── dashboard.html
│   └── static/
│       ├── css/style.css
│       └── js/dashboard.js
├── instrumentation/               # Standalone package for embedding in pipelines
│   ├── __init__.py
│   ├── tracker.py                 # Core tracking logic
│   ├── wrappers.py                # LLM provider wrappers (Anthropic, OpenAI, LangChain)
│   ├── context.py                 # Pipeline context (repo, workflow, job, step)
│   └── reporter.py                # Send collected metrics to optimizer API
├── scripts/
│   ├── start.sh
│   └── collect.py                 # CLI script to trigger GitHub data collection
├── requirements.txt
├── .env.example
└── README.md
```

---

## Core Components

### 1. Instrumentation Library (`instrumentation/`)
A lightweight, importable package that pipeline steps embed to track LLM usage.

**API Design:**
```python
from pipeline_optimizer.instrumentation import track_llm, init_tracker

# Initialize at pipeline step start — auto-detects GitHub Actions env vars
init_tracker(api_url="https://your-optimizer/api/ingest")

# Decorator approach
@track_llm(provider="anthropic", purpose="code-review")
def review_code(diff):
    response = anthropic_client.messages.create(...)
    return response

# Context manager approach
with track_llm(provider="openai", purpose="test-generation"):
    response = openai_client.chat.completions.create(...)

# Auto-wrapper approach (monkey-patches the client)
from pipeline_optimizer.instrumentation.wrappers import wrap_anthropic
client = wrap_anthropic(anthropic.Anthropic())
# All calls automatically tracked
```

**What it captures per LLM call:**
- Provider + model name
- Input/output token counts
- Latency (wall clock)
- Estimated cost (using known pricing tables)
- Purpose tag (user-provided label like "code-review", "test-gen")
- Pipeline context (auto-detected from `GITHUB_*` env vars):
  - Repository, workflow name, job name, step name
  - Run ID, run number, trigger event
  - Commit SHA, branch

**Reporting:** Batches metrics and POSTs to the optimizer's `/api/ingest` endpoint at step completion, or writes to a JSON artifact file that gets collected later.

### 2. GitHub Actions Data Collector (`services/github_client.py`)
Pulls pipeline structure and run history from GitHub API.

**Collects:**
- Workflow definitions (parsed from YAML via API)
- Workflow runs (status, duration, trigger, conclusion)
- Job details (name, duration, runner type, dependencies via `needs`)
- Step details (name, duration, conclusion)
- Billing/usage data (when available via GitHub API)

**Approach:** Periodic collection via CLI script or scheduled endpoint. Stores incrementally — only fetches runs newer than last collection.

### 3. Analysis Engine (`services/analyzer.py`)
Examines collected data to identify optimization opportunities.

**Analysis categories:**
- **Parallelization**: Jobs that don't depend on each other but run sequentially
- **Caching**: Steps that install dependencies or build artifacts repeatedly
- **Redundancy**: Similar steps across workflows that could be consolidated
- **LLM optimization**:
  - Calls using expensive models where cheaper ones would suffice
  - Missing prompt caching opportunities
  - Calls that could be batched
  - High-variance latency calls that could use timeouts/retries
- **Cost hotspots**: Rank steps/jobs/workflows by total cost (compute + LLM)
- **Duration hotspots**: Critical path analysis — which jobs gate the pipeline

### 4. AI Agent (`services/agent.py`)
Claude-powered agent that reasons about pipeline architecture.

**Context it receives:**
- Workflow YAML structure (job DAG, step definitions)
- Historical run data (durations, costs, failure rates)
- LLM usage patterns (which calls, which models, token volumes)
- Analysis engine findings (pre-computed optimizations)

**What it produces:**
- Prioritized optimization recommendations with estimated savings
- Specific YAML changes for pipeline improvements
- Model substitution suggestions (e.g., "use Haiku instead of Sonnet for this linting step")
- Caching strategy recommendations

### 5. Cost Calculator (`services/cost_calculator.py`)
Unified cost computation.

**Compute costs:** GitHub Actions runner pricing (Linux $0.008/min, Windows $0.016/min, macOS $0.08/min) applied to job durations.

**LLM costs:** Pricing tables for known models (Claude Sonnet, Opus, Haiku; GPT-4o, GPT-4o-mini, etc.) applied to token counts. Updatable config.

---

## Data Model

### `Repository`
- id, github_id, full_name, default_branch, last_collected_at

### `Workflow`
- id, repo_id (FK), github_id, name, path, yaml_content

### `WorkflowRun`
- id, workflow_id (FK), github_run_id, run_number
- status, conclusion, trigger_event
- started_at, completed_at, duration_seconds
- total_compute_cost, total_llm_cost
- commit_sha, branch

### `Job`
- id, run_id (FK), github_job_id, name
- runner_os, runner_type
- started_at, completed_at, duration_seconds
- conclusion, depends_on (JSON list of job names)

### `Step`
- id, job_id (FK), name, number
- started_at, completed_at, duration_seconds
- conclusion

### `LLMCall`
- id, run_id (FK), job_name, step_name
- provider, model, purpose
- input_tokens, output_tokens
- latency_ms, estimated_cost
- timestamp
- commit_sha, branch

### `Recommendation`
- id, repo_id (FK), category (parallelization/caching/llm/cost/etc.)
- title, description, estimated_savings
- priority (high/medium/low)
- status (new/accepted/dismissed)
- created_at, workflow_run_id (FK, nullable — which run triggered this)

---

## Dashboard Layout

**Tab 1 — Overview:**
- Total pipeline cost (compute + LLM) over time (line chart)
- Cost breakdown: compute vs LLM tokens (pie chart)
- Pipeline velocity: avg duration trend (line chart)
- Top 5 most expensive workflows (bar chart)

**Tab 2 — LLM Usage:**
- Token usage by provider/model (stacked bar)
- Cost by purpose/label (pie chart)
- Model usage distribution
- Calls per pipeline run trend

**Tab 3 — Pipelines:**
- Workflow list with avg duration, cost, failure rate
- Drill into runs → jobs → steps with timing waterfall
- Job dependency DAG visualization

**Tab 4 — Recommendations:**
- Active recommendations with priority, category, estimated savings
- Accept/dismiss actions
- History of past recommendations

---

## Implementation Phases

### Phase 1: Foundation
- Project scaffolding (FastAPI app, config, database)
- Data model + SQLAlchemy models
- GitHub client: collect workflow definitions and run history
- Basic dashboard showing pipeline runs and durations
- **Verify:** Can collect and display workflow runs from a test repo

### Phase 2: Instrumentation Library
- Core tracker with decorator and context manager APIs
- Auto-detection of GitHub Actions environment
- Anthropic + OpenAI wrappers
- Reporter that POSTs to `/api/ingest` endpoint
- Ingest webhook endpoint in the optimizer
- **Verify:** Embed in a test GitHub Action, see LLM call data appear in dashboard

### Phase 3: Cost Engine
- Compute cost calculator (runner pricing × duration)
- LLM cost calculator (model pricing × tokens)
- Cost aggregation per run/workflow/repo
- Cost trend charts on dashboard
- LLM Usage tab
- **Verify:** Dashboard shows accurate cost breakdowns

### Phase 4: Analysis Engine
- Pipeline structure analysis (parallelization, caching, redundancy)
- LLM usage analysis (model optimization, batching opportunities)
- Cost hotspot identification
- Store findings as recommendations
- **Verify:** Engine produces sensible recommendations from sample data

### Phase 5: AI Agent
- Agent prompt design with pipeline context
- Recommendation generation from analysis + raw data
- Natural language explanations of optimizations
- Recommendations tab on dashboard
- **Verify:** Agent produces actionable, specific recommendations

---

## Key Trade-offs

1. **Instrumentation as a library vs GitHub Action**: Library is more flexible (works in any step, any provider), but requires code changes in each pipeline. A custom GitHub Action would be easier to add but less granular. → **Go with library** — more powerful, and the user's pipelines already have custom code.

2. **Push (instrumentation reports to API) vs Pull (optimizer reads artifacts)**: Push is real-time but requires the optimizer to be running during pipeline execution. Artifact-based pull works offline but adds latency. → **Support both** — push as primary, with JSON artifact fallback.

3. **SQLite vs PostgreSQL**: SQLite is simpler and matches the user's existing pattern. May need to migrate if data volume grows. → **Start with SQLite**, same as gitlab-dashboard.

4. **Single-repo vs multi-repo**: Design for multi-repo from the start — the user has multiple projects. The `Repository` table makes this natural.

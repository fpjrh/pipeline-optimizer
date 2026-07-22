# Pipeline Optimizer

AI-powered GitHub Actions pipeline optimization agent that balances pipeline velocity against cost — both compute time and LLM token expense.

## What It Does

Pipeline Optimizer collects data from two sources and uses AI to generate actionable optimization recommendations:

1. **GitHub Actions API** — workflow runs, job durations, step timings, runner types
2. **LLM Instrumentation** — token counts, latency, model usage, and cost for every AI/LLM call in your pipelines

### Dashboard

A 4-tab web dashboard provides visibility into:

- **Overview** — total cost trends (compute + LLM), pipeline velocity, success rates, top workflows by cost
- **LLM Usage** — token usage by model, cost by purpose, model usage breakdown with latency
- **Pipelines** — workflow list with duration/cost/success metrics, recent run history
- **Recommendations** — AI-generated optimization suggestions with priority, estimated savings, and accept/dismiss actions

### Analysis Categories

- **Parallelization** — jobs that could run concurrently but don't
- **Caching** — repeated dependency installs or builds that could be cached
- **Redundancy** — similar steps across workflows that could be consolidated
- **LLM Optimization** — expensive models where cheaper ones suffice, missing prompt caching, batching opportunities
- **Cost Hotspots** — most expensive steps, jobs, and workflows ranked by total cost

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy, Pydantic Settings
- **Database**: SQLite
- **Frontend**: HTML/CSS/JS, Chart.js
- **GitHub**: GitHub REST API
- **AI Agent**: Anthropic SDK (Claude)

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/fpjrh/pipeline-optimizer.git
cd pipeline-optimizer
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub PAT with `repo` and `actions:read` scopes |
| `GITHUB_ORG` | No | GitHub organization to monitor (if empty, uses authenticated user's repos) |
| `COLLECT_REPOS` | No | Comma-separated `owner/repo` list (overrides org-level discovery) |
| `ANTHROPIC_API_KEY` | For agent | Anthropic API key for AI-powered recommendations |
| `AGENT_MODEL` | No | Claude model for recommendations (default: `claude-sonnet-5`) |
| `PORT` | No | Server port (default: `8100`) |
| `DATABASE_URL` | No | SQLite path (default: `sqlite:///./pipeline_optimizer.db`) |

### 3. Start the server

```bash
./scripts/start.sh
```

Open http://localhost:8100 in your browser.

### 4. Collect data

Click **Collect Data** in the dashboard, or run the CLI:

```bash
python scripts/collect.py
```

## Instrumentation Library

The `instrumentation/` package is designed to be embedded in your GitHub Actions pipeline steps to track LLM usage automatically.

### Planned API (Phase 2)

```python
from pipeline_optimizer.instrumentation import track_llm, init_tracker

# Auto-detects GitHub Actions environment variables
init_tracker(api_url="https://your-optimizer-host/api/ingest")

# Decorator
@track_llm(provider="anthropic", purpose="code-review")
def review_code(diff):
    response = client.messages.create(...)
    return response

# Context manager
with track_llm(provider="openai", purpose="test-generation"):
    response = openai_client.chat.completions.create(...)
```

### Manual Ingest

You can also POST LLM call data directly:

```bash
curl -X POST http://localhost:8100/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "calls": [{
      "provider": "anthropic",
      "model": "claude-sonnet-5",
      "purpose": "code-review",
      "input_tokens": 5000,
      "output_tokens": 1200,
      "latency_ms": 3400,
      "repo_full_name": "myorg/myrepo",
      "workflow_name": "ci",
      "job_name": "review",
      "step_name": "ai-review"
    }]
  }'
```

## Project Structure

```
pipeline-optimizer/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Pydantic Settings (.env config)
│   ├── models/
│   │   ├── database.py          # SQLAlchemy engine/session
│   │   └── schemas.py           # ORM models (Repository, Workflow, Run, Job, Step, LLMCall, Recommendation)
│   ├── api/
│   │   ├── routes.py            # Dashboard & metrics API endpoints
│   │   └── webhooks.py          # LLM call ingest endpoint
│   ├── services/
│   │   ├── github_client.py     # GitHub Actions API data collector
│   │   └── cost_calculator.py   # Compute + LLM cost computation
│   ├── templates/
│   │   └── dashboard.html       # 4-tab dashboard
│   └── static/
│       ├── css/style.css
│       └── js/dashboard.js
├── instrumentation/             # Embeddable LLM tracking library (Phase 2)
├── scripts/
│   ├── start.sh                 # Start the server
│   ├── stop.sh                  # Stop the server
│   └── collect.py               # CLI data collection
├── requirements.txt
└── .env.example
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard UI |
| `GET` | `/api/repos` | List monitored repositories |
| `POST` | `/api/collect` | Trigger GitHub data collection |
| `GET` | `/api/overview` | Summary metrics (runs, costs, tokens) |
| `GET` | `/api/runs` | Recent workflow runs |
| `GET` | `/api/runs/{id}/jobs` | Jobs and steps for a specific run |
| `GET` | `/api/cost-trends` | Daily cost trend data |
| `GET` | `/api/llm-usage` | LLM usage breakdown by model and purpose |
| `GET` | `/api/top-workflows` | Workflows ranked by cost |
| `GET` | `/api/recommendations` | Optimization recommendations |
| `POST` | `/api/recommendations/{id}/status` | Accept or dismiss a recommendation |
| `POST` | `/api/ingest` | Ingest LLM call metrics from instrumentation |

Most `GET` endpoints accept `days` (default: 30) and `repo` (filter by repository) query parameters.

## Cost Calculation

### Compute Costs

Based on GitHub Actions runner pricing:

| Runner | Cost/min |
|--------|----------|
| Ubuntu (Linux) | $0.008 |
| Windows | $0.016 |
| macOS | $0.080 |

### LLM Costs

Built-in pricing tables for common models (per 1M tokens):

| Model | Input | Output |
|-------|-------|--------|
| Claude Sonnet 5 | $3.00 | $15.00 |
| Claude Haiku 4.5 | $0.80 | $4.00 |
| Claude Opus 4.8 | $15.00 | $75.00 |
| GPT-4o | $2.50 | $10.00 |
| GPT-4o-mini | $0.15 | $0.60 |

## Roadmap

- [x] **Phase 1**: Foundation — FastAPI app, data model, GitHub collector, dashboard
- [ ] **Phase 2**: Instrumentation library — decorator/context manager API, provider wrappers, auto-reporting
- [ ] **Phase 3**: Cost engine — compute + LLM cost charts, LLM Usage tab analytics
- [ ] **Phase 4**: Analysis engine — parallelization detection, caching opportunities, model optimization
- [ ] **Phase 5**: AI agent — Claude-powered recommendation generation with natural language explanations

## License

MIT

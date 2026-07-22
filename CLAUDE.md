# CLAUDE.md — Pipeline Optimizer

## Project Overview

Pipeline Optimizer is an AI-powered tool for analyzing and optimizing GitHub Actions pipelines. It tracks both compute costs (runner minutes) and LLM token expenses across CI/CD pipelines, then generates optimization recommendations.

## Architecture

- **Backend**: FastAPI with SQLAlchemy ORM, SQLite database, Pydantic Settings for config
- **Frontend**: Single-page HTML dashboard with vanilla JS and Chart.js (no build step)
- **Entry point**: `app/main.py` — mounts static files, includes route and webhook routers, initializes database on startup
- **Config**: `app/config.py` — all settings from `.env` file via `pydantic-settings`

## Key Directories

- `app/api/` — FastAPI route handlers. `routes.py` has dashboard + metrics endpoints; `webhooks.py` has the `/api/ingest` endpoint for receiving LLM call data
- `app/services/` — Business logic. `github_client.py` collects from GitHub API; `cost_calculator.py` computes costs using runner and model pricing tables
- `app/models/` — `schemas.py` has all SQLAlchemy ORM models; `database.py` has engine/session setup
- `app/templates/` — Jinja2 HTML template for the dashboard
- `app/static/` — CSS and JS served directly by FastAPI
- `instrumentation/` — Standalone library for embedding in pipelines (Phase 2, not yet implemented)
- `scripts/` — `start.sh`, `stop.sh`, `collect.py` for server and data management

## Data Model

Six core tables in SQLite:
- `Repository` → `Workflow` → `WorkflowRun` → `Job` → `Step` (pipeline hierarchy)
- `LLMCall` — linked to `WorkflowRun` when possible, stores provider/model/tokens/cost
- `Recommendation` — optimization suggestions with category, priority, status

## Running the Project

```bash
cp .env.example .env  # configure GITHUB_TOKEN at minimum
pip install -r requirements.txt
./scripts/start.sh    # starts uvicorn on port 8100
```

## Conventions

- Follow the same patterns as the existing codebase: FastAPI dependency injection with `Depends(get_db)`, SQLAlchemy ORM queries, Pydantic models for request/response validation
- Cost calculator has pricing tables as module-level dicts — update these when adding new models
- Dashboard uses tab-based navigation with `localStorage` persistence (same pattern as gitlab-dashboard)
- Dark mode support via CSS variables and `body.dark-mode` class
- API endpoints accept `days` and `repo` query params for filtering

## Implementation Status

- **Phase 1 (Complete)**: Project scaffolding, data model, GitHub Actions data collector, cost calculator, 4-tab dashboard, LLM ingest webhook
- **Phase 2 (Next)**: Instrumentation library — `instrumentation/tracker.py`, `wrappers.py`, `context.py`, `reporter.py`
- **Phase 3**: Cost engine charts and LLM usage analytics
- **Phase 4**: Analysis engine (`app/services/analyzer.py` — not yet created)
- **Phase 5**: AI agent (`app/services/agent.py` — not yet created)

## Testing

No test suite yet. Verify manually:
1. Start the server (`./scripts/start.sh`)
2. Open http://localhost:8100
3. Click "Collect Data" (requires `GITHUB_TOKEN` in `.env`)
4. POST to `/api/ingest` to test LLM call tracking

# AutoSage Backend

FastAPI + LangGraph agents + Celery workers. Full project documentation lives in the
[repository README](../README.md) (architecture, complete API surface, environment
variables, core flows).

## Stack

- **Python 3.11+**, FastAPI, Pydantic v2, SQLAlchemy (async) + Alembic
- **PostgreSQL + pgvector**, **Redis** (Celery broker/results), **MLflow**
- **LangGraph** agent workflows, **Celery** for async experiment execution
- **Docker** sandbox (`autosage-runner:latest`) for generated-code execution

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # Linux/macOS

pip install -e .
cp .env.example .env              # every var has a dev default in app/core/config.py
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- Docs: `http://localhost:8000/docs`
- Health (checks PostgreSQL): `http://localhost:8000/api/v1/health`
- Liveness: `http://localhost:8000/health`

Infrastructure for local development:

```bash
docker compose -f ../docker-compose.dev.yml up -d   # postgres + pgvector, redis, mlflow
```

> An embedded Celery worker starts with the API by default
> (`CELERY_EMBEDDED_WORKER=True`, `solo` pool — Windows-safe), so no separate
> worker process is needed in development.

## Commands

```bash
pytest tests/unit -v          # 12 unit suites
pytest tests/integration -v   # 7 integration suites (needs Docker/Redis)
pytest tests/ -v              # everything

mypy app/                     # type checking
ruff check app/               # linting

alembic upgrade head          # apply migrations
alembic revision --autogenerate -m "message"

# Sandbox runner image (required before POST /sandbox/execute)
cd app/engine/sandbox/dockerfile
docker build -f Dockerfile.runner -t autosage-runner:latest .
```

## Layout

```
app/
├── agents/        # LangGraph agent definitions & state schemas
├── api/v1/        # REST routers + SSE/WebSocket streaming (endpoints/)
├── core/          # config, security, telemetry, runtime (embedded worker)
├── db/            # async engine, sessions, dependencies
├── engine/        # LLM gateway, Docker sandbox, verification, memory
├── models/        # SQLAlchemy ORM models
├── repositories/  # data-access layer
├── schemas/       # Pydantic v2 schemas
├── services/      # health, event publishing, business services
├── workers/       # Celery app & tasks
└── main.py        # app factory, CORS, embedded worker lifecycle
```

# AutoSage

> **A Verified Multi-Agent System for Natural-Language-Driven Automated Machine Learning**

AutoSage turns a natural-language problem statement — with or without a dataset — into a machine-learning pipeline you can audit. Every stage, every design decision and every verification check is recorded with the evidence behind it, and generated code can be executed on demand inside a hardened Docker sandbox.

The product surface is four connected pages:

| Page | Route | What it does |
|------|-------|--------------|
| **Generate & Verify** | `/objectives` | Describe a problem → runs a four-objective verification session over SSE; every check shows *expected / actual / evidence / reasoning / confidence*, ending in a final report where each decision carries its rationale and confidence |
| **Pipeline** | `/pipeline` | The plan generated for the current session (stages, edges, assumptions, risks) rendered as an explorable graph |
| **Sandbox** | `/sandbox` | Monaco IDE over the generated files; **Run** executes *your edited* Python in the Docker sandbox — generated output is never executed automatically |
| **Evidence** | `/evidence` | The reasoning lineage DAG for a run: `Agent → Decision → Evidence → Result` |

The classic experiment surface sits alongside it: `/new`, `/experiments`, `/datasets`, `/models`, `/agents`, `/memory`, `/checkllm`, `/workspace`, `/settings`.

---

## Architectural Philosophy

1. **Multi-Agent Specialization**: Discrete LangGraph agents handle discovery, statistical profiling, preprocessing, model selection, experiment execution, and verification.
2. **Empirical Verification Gate**: Generated code and model outcomes pass automated AST security analysis, data leakage checks, metric sanity verification, and baseline dominance tests before acceptance.
3. **Reasoning Lineage (Evidence Trail)**: Every architectural choice is recorded in an immutable DAG: `Agent → Decision → Evidence → Result`.
4. **Extraction-Verification Memory**: Verified winning solutions are fingerprinted and indexed using `pgvector` for semantic knowledge reuse.
5. **Secure Sandboxing**: LLM-generated code executes inside hardened, isolated Docker containers with no network access, non-root privileges, read-only rootfs, and strict CPU/memory/pids/timeout quotas.
6. **Durable Sessions**: Verification frames are persisted server-side as they are emitted. The client keeps a pointer to the current run and restores from `GET /objective-verification/sessions/{run_id}` after any reload or tab switch, re-attaching to the live stream instead of starting over.

---

## Directory Structure

```
autoSage/
├── .github/workflows/ci.yml      # CI: backend-test + frontend-check jobs
├── backend/                      # FastAPI + LangGraph agents + Celery workers
│   ├── alembic/                  # Database migrations
│   ├── app/
│   │   ├── agents/               # LangGraph agent definitions & state schemas
│   │   ├── api/v1/               # REST routers + SSE/WebSocket streaming
│   │   │   └── endpoints/        # auth, experiments, objective-verification,
│   │   │                         # pipeline, sandbox, evidence, memory, ...
│   │   ├── core/                 # Configuration, security, telemetry, runtime
│   │   ├── db/                   # Async engine, sessions, dependencies
│   │   ├── engine/               # LLM gateway, Docker sandbox, verification, memory
│   │   │   └── sandbox/dockerfile/  # Dockerfile.runner + runner requirements
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── repositories/         # Data-access layer
│   │   ├── schemas/              # Pydantic v2 schemas
│   │   ├── services/             # Health, event publishing, business services
│   │   └── workers/              # Celery app & task definitions
│   ├── tests/                    # 12 unit + 7 integration suites (e2e scaffolded)
│   ├── Dockerfile.backend
│   └── pyproject.toml            # deps, ruff, mypy, pytest config
├── frontend/                     # Vite 8 + React 19 + TypeScript SPA
│   ├── index.html
│   ├── vite.config.ts            # dev proxy /api + /health → backend (SSE-safe)
│   └── src/
│       ├── App.tsx               # Routes, protected layout, page transitions
│       ├── pages/                # Home, Objectives, Pipeline, Sandbox, Evidence, ...
│       ├── components/
│       │   ├── layout/           # Sidebar, PageHeader
│       │   ├── workspace/        # SandboxIDE, MonacoCodeEditor, FileTabs, Terminal
│       │   ├── verification/     # ObjectiveViews, WorkspaceSelect
│       │   ├── pipeline/ graph/  # PlanAnalysisPanel, pipeline graphs
│       │   ├── ui/ anim/         # Theme, toasts, transitions, motion primitives
│       ├── lib/                  # api.ts (fetch client + SSE), monacoSetup.ts,
│       │                         # objectiveRun.ts, pipelinePlanStore.ts
│       └── store/                # StoreProvider/useStore (auth + global state)
├── data/
│   ├── uploads/                  # Ephemeral raw user datasets
│   ├── artifacts/                # Exported models, pipelines, bundles
│   └── mlflow/                   # MLflow tracking artifacts (dev)
├── docker-compose.dev.yml        # Dev infra: PostgreSQL + pgvector, Redis, MLflow
├── docker-compose.yml            # Slim infra: PostgreSQL + Redis
└── PRODUCT.md                    # Product specification
```

---

## Implementation Status

| Phase | Component | Status |
|-------|-----------|--------|
| **1** | FastAPI Foundation, PostgreSQL + pgvector, Alembic | ✅ Complete |
| **2** | Authentication (Supabase Auth RS256/JWKS, Better-Auth HS256, local dev-token) | ✅ Complete |
| **3** | Workspaces, Projects, Datasets CRUD | ✅ Complete |
| **4** | Experiment Lifecycle API (create, list, get, update, delete, start, cancel) | ✅ Complete |
| **5** | Celery + Redis Async Execution, Retry/Backoff, Task Routing | ✅ Complete |
| **6** | LangGraph Workflow, State, Checkpointing, Runner | ✅ Complete |
| **7** | Specialized Agents (Orchestrator, Discovery, Profiler, Preprocessor, ModelSelector, MLExperiment, Verifier) | ✅ Complete |
| **8** | LLM Gateway (OpenRouter, Groq, HF), Structured Outputs, Heuristic Fallback | ✅ Complete |
| **9** | Modular Tool System (Registry, built-in tools, Agent→Tool→Result) | ✅ Complete |
| **10** | Docker ML Sandbox (CPU/memory/pids limits, no network, read-only rootfs, non-root, cleanup) | ✅ Complete |
| **11** | Frontend-Backend Integration (Auth, Experiments, streaming, error handling) | ✅ Complete |
| **12** | **Target Column Removed from Objective Verification** | ✅ Complete — dataset and target column are optional; code generation proceeds and notes its assumptions |
| **13** | **Sandbox File Tab Switching Fixed** | ✅ `handleTabChange` correctly updates `FileTab.active` |
| **14** | **Monaco IDE in the Sandbox** | ✅ `@monaco-editor/react` wrapper bound to the **locally bundled** `monaco-editor@0.57.0` (`loader.config({ monaco })`, `?worker` files, `vs-dark`) — no CDN fetch; CodeMirror removed |
| **15** | **Four-Objective Verification Sessions** | ✅ `POST /objective-verification/sessions` → run id immediately; SSE frames (`stage`/`report`/`error`) for input → objective_1..4 → report, with replay for late subscribers |
| **16** | **Session Persistence Across Navigation** | ✅ Results survive tab/page switches: restore from `GET /sessions/{run_id}` + SSE re-attach when still running; a new query replaces the old session |
| **17** | **Pipeline Planner wired into Generate & Verify** | ✅ A completed verification also publishes a pipeline plan (`POST /pipeline/plan`) so Pipeline / Sandbox / Evidence open with content |
| **18** | **Sandbox is Runnable from the IDE** | ✅ **Run** executes user-owned Python tabs through `POST /sandbox/execute`; status probe runs in generated mode; generated output is never auto-executed |
| **19** | **Objectives page fits the viewport** | ✅ Compact page header + one-line query bar when a session exists; Verification Sequence sized to its content (no scrolling); Backend Log takes the remaining column height; no phantom page scroll |

---

## Quickstart

### 1. Prerequisites

- Python 3.11+
- Node.js 20.19+ & npm (Vite 8 requirement)
- Docker Desktop with Compose (PostgreSQL, Redis, MLflow — and the sandbox runner image)

### 2. Local Infrastructure

```bash
# Clone and enter repo
cd autoSage

# Postgres (with pgvector), Redis, and MLflow
docker compose -f docker-compose.dev.yml up -d

# Verify services are healthy
docker compose -f docker-compose.dev.yml ps
```

### 3. Backend (port 8000)

```bash
cd backend

# Create + activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # Linux/macOS

# Install dependencies
pip install -e .

# Configure environment (copy template and edit)
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the API (with auto-reload)
uvicorn app.main:app --reload --port 8000
```

- **API root:** `http://localhost:8000`
- **Interactive docs:** `http://localhost:8000/docs`
- **Detailed health (checks PostgreSQL):** `http://localhost:8000/api/v1/health`
- **Liveness probe:** `http://localhost:8000/health`

> **No separate worker process is needed in dev.** By default the API starts an embedded Celery worker in a background thread (`CELERY_EMBEDDED_WORKER=True`, `solo` pool — Windows-safe). Set it to `False` only if you run a standalone worker.

### 4. Frontend (port 5173)

```bash
cd frontend

# Install dependencies
npm install

# Configure (optional — defaults are correct for local dev)
cp .env.example .env.local

# Start the Vite dev server
npm run dev
```

**Frontend runs at:** `http://localhost:5173`

The dev server proxies `/api` and `/health` to `VITE_BACKEND_ORIGIN` (default `http://127.0.0.1:8000`), so all requests are same-origin and no CORS setup is needed. SSE is exempted from proxy buffering so verification frames arrive in real time.

### 5. Build the ML Sandbox Image

Required before any sandbox **Run** (and before training jobs):

```bash
cd backend/app/engine/sandbox/dockerfile
docker build -f Dockerfile.runner -t autosage-runner:latest .
```

---

## Key Environment Variables

### Backend (`backend/.env`)

Every variable has a dev default in `app/core/config.py`, so the service also boots with no `.env` at all.

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL + pgvector async URL (append `?sslmode=require` for managed Postgres) | `postgresql+asyncpg://postgres:postgres@localhost:5432/autosage` |
| `BACKEND_CORS_ORIGINS` | Allowed browser origins (JSON array or comma string) | `["http://localhost:3000"]` |
| `REDIS_URL` | Redis broker / result backend base | `redis://localhost:6379/0` |
| `CELERY_TASK_ALWAYS_EAGER` | Run tasks inline (no broker; tests) | `False` |
| `CELERY_EMBEDDED_WORKER` | Start the Celery worker inside the API process | `True` |
| `MLFLOW_TRACKING_URI` / `MLFLOW_EXPERIMENT_NAME` | MLflow tracking | `http://localhost:5000` / `autosage_default` |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Production auth (RS256 JWTs verified via JWKS) + storage | Optional (dev works without) |
| `JWT_ALGORITHM` / `ACCESS_TOKEN_EXPIRE_MINUTES` | Token verification | `RS256` / `1440` |
| `AUTH_DEV_TOKEN_ENABLED` | Enable `POST /api/v1/auth/dev-token` (dev only; production answers 404 by design) | `True` |
| `GROQ_API_KEY` / `OPENROUTER_API_KEY` / `HUGGINGFACE_API_TOKEN` | LLM providers (leave empty → heuristic fallback) | Optional |
| `DEFAULT_FAST_MODEL` / `DEFAULT_REASONING_MODEL` | Model selection | `groq/llama-3.1-8b-instant`, `openrouter/meta-llama/llama-3.3-70b-instruct` |
| `LLM_ALLOW_HEURISTIC_FALLBACK` | Deterministic fallback when no provider is configured | `True` |
| `DOCKER_SANDBOX_IMAGE` | Docker image for sandbox execution | `autosage-runner:latest` |
| `SANDBOX_ENABLED` / `SANDBOX_TIMEOUT_SECONDS` / `SANDBOX_PIDS_LIMIT` / `SANDBOX_READONLY_ROOTFS` | Sandbox hardening | `True` / `300` / `100` / `True` |

### Frontend (`frontend/.env.local`)

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | API base path/URL (use the dev proxy path to avoid CORS) | `/api/v1` |
| `VITE_BACKEND_ORIGIN` | Backend origin used by the Vite dev proxy | `http://127.0.0.1:8000` |
| `VITE_WS_BASE_URL` | WebSocket base for experiment streams (bare origin gains `/api/v1`) | derived from the HTTP base |
| `VITE_ALLOW_DEV_TOKEN` | Force-enable/disable the local dev-token minter | localhost only |
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` | Enable email/password + guest login on the Login page | unset |

> If you bypass the Vite proxy (serve the SPA from another origin or call `:8000` directly), add that origin to `BACKEND_CORS_ORIGINS` — the default allowlist is `http://localhost:3000`.

---

## Development Commands

### Backend

```bash
# Unit tests (12 suites)
pytest tests/unit -v

# Integration tests (7 suites — needs Docker/Redis)
pytest tests/integration -v

# Type checking
mypy app/

# Linting
ruff check app/

# Rebuild the sandbox image
cd app/engine/sandbox/dockerfile
docker build -f Dockerfile.runner -t autosage-runner:latest .

# Apply migrations / create a new one
alembic upgrade head
alembic revision --autogenerate -m "message"
```

### Frontend

```bash
# Type checking (also runs as part of build)
npx tsc -b

# Linting (oxlint)
npm run lint
# or on specific files:
npx oxlint src/pages/Objectives.tsx

# Production build (tsc -b && vite build)
npm run build

# Serve the production build locally
npm run preview
```

---

## API Endpoints (v1)

All routes below are mounted under `/api/v1` unless noted. Full interactive documentation lives at `/docs`.

### Health
- `GET /health` *(root)* — container liveness probe
- `GET /api/v1/health` — service health incl. PostgreSQL reachability

### Authentication
- `POST /auth/dev-token` — mint a development JWT (local dev only; production returns 404 by design)
- `GET /auth/me` — current user profile
- `GET /auth/session` — session introspection

### Objective Verification (the Generate & Verify flow)
- `GET /objective-verification/objectives` — the four canonical objectives and their checks (fixed graph definition; the client never hardcodes them)
- `GET /objective-verification/stages` — fixed stage order (`input → objective_1..4 → report`)
- `GET /objective-verification/datasets` — datasets available for a fresh session
- `POST /objective-verification/sessions` — start a session; returns `run_id` immediately (never blocks on verification)
- `GET /objective-verification/sessions/{run_id}` — durable state: replayed frames, generated files, activity log, final report
- `GET /objective-verification/sessions/{run_id}/stream` — SSE progress (`stage`, `report`, `error` events); frames are persisted as emitted, so late/reconnecting subscribers replay what they missed

### Pipeline Planner
- `POST /pipeline/plan` — generate a plan (task type, target metric, complexity, stages, edges, summary, assumptions, risks, source)
- `GET /pipeline/status` — planner availability (`llm_available`, `fallback_enabled`)

### Sandbox
- `POST /sandbox/execute` — execute a script in the Docker sandbox; returns stdout/stderr, metrics, artifacts, exit code, duration
- `GET /sandbox/status` — availability + effective hardening config (image, CPU/memory limits, timeout, pids, read-only rootfs)

### Experiments, Projects, Datasets, Runs
- `POST/GET/PATCH/DELETE /experiments`, `POST /experiments/{id}/start`, `POST /experiments/{id}/cancel`
- `WS /experiments/{id}/ws?token=` — live experiment stream (REST polling is the fallback); also `WS /ws`
- `GET/POST /projects`, `GET /projects/{project_id}/datasets`
- `GET /datasets/resolve` — does this filename exist? · `POST /datasets/upload`
- `POST /projects/{project_id}/runs/` — launch a run · `GET /projects/{project_id}/runs/{run_id}/stream` — run events

### Evidence, Verification, Memory
- `GET /runs/{run_id}/evidence` — evidence DAG (nodes + edges)
- `POST /verification/decision`, `POST /verification/experiment`, `POST /verification/evidence/search`, `GET /verification/sources`
- `GET /memory/search` — pgvector-backed similarity search over verified solutions

### Storage, Reproducibility, LLM, Workspaces, Diagnostics
- `GET /storage/stats`
- `GET /reproducibility`, `GET /experiments/{id}/reproducibility`
- `GET /llm/status`, `POST /llm/check`, `POST /llm/select`
- `GET/POST /workspaces`
- `GET /diagnostics`

---

## Core Flows

### Generate & Verify (the main flow)

```
1. POST /objective-verification/sessions
     { workspace_id, problem_statement, dataset_name?, target_column?, task_type?, primary_metric? }
   → { run_id, experiment_id, stream_url }            # returns immediately
2. GET  /objective-verification/sessions/{run_id}/stream   (SSE, Bearer token)
   → stage frames: input → objective_1 → … → objective_4 → report
3. Each check carries: expected / actual / evidence[] / reasoning /
   confidence / artifact / category (source|probe|session|generated|empirical)
   / verification_level (source|config|generated|runtime)
4. report frame → final verdict + per-decision rationale & confidence
5. Client also POSTs /pipeline/plan with the same description and publishes
   the plan → Pipeline, Sandbox and Evidence open with content
6. run id persisted (sessionStorage `as_objective_run`) → any reload or tab
   switch restores from GET /sessions/{run_id} and re-attaches the stream
```

`NOT_VERIFIED` is deliberately not a pass: it means the evidence a check needed does not exist (on a fresh session, anything depending on a training run — verification never trains).

### Sandbox Execution

```
1. GET  /sandbox/status  → available + hardening config (probes in generated mode)
2. User edits a generated file in Monaco and presses Run
3. Only "user-owned" Python tabs run (edited tabs, or tabs not created by
   codegen); generated output is never executed automatically
4. POST /sandbox/execute { script, dataset_path?, env_vars?, mlflow_run_id? }
   → stdout/stderr, metrics, artifacts, exit_code, duration
5. Terminal renders only after a real run; the Run bar always explains why
   Run is disabled when it is (runDisabledReason)
```

### Experiment Run (legacy surface)

```
1. POST /experiments → CREATED
2. POST /experiments/{id}/start → QUEUED (+ celery_task_id)
3. WS /experiments/{id}/ws streams stage updates (polling every 2.5 s is the fallback)
4. RUNNING → COMPLETED / FAILED / CANCELLED
5. GET  /runs/{run_id}/evidence → reasoning lineage DAG
```

---

## Frontend Architecture

```
src/
├── lib/
│   ├── api.ts               # Single fetch-based client
│   │                        #  · base: VITE_API_BASE_URL → VITE_BACKEND_ORIGIN/api/v1 → /api/v1
│   │                        #  · Bearer token with local dev-token minting (localhost only)
│   │                        #  · typed ApiError + friendly messages, one retry on 401 in dev
│   │                        #  · SSE via fetch + ReadableStream (EventSource can't send headers)
│   ├── objectiveRun.ts      # Current run pointer (sessionStorage `as_objective_run`)
│   ├── pipelinePlanStore.ts # Pipeline drafts (sessionStorage-backed, per-draft ids)
│   ├── monacoSetup.ts       # loader.config({ monaco }) — local bundle + ?worker imports
│   └── supabaseAuth.ts guestAuth.ts  # production auth paths
├── store/store.tsx          # StoreProvider/useStore: auth bootstrap, experiment
│                            # WS stream + polling fallback, toasts
├── components/
│   ├── workspace/           # SandboxIDE (tabs, explorer, run gating), MonacoCodeEditor,
│   │                        # FileTabs, FileExplorer, Terminal, StatusBar, ExecutionTimeline
│   ├── verification/        # ObjectiveViews: objectives, checks, report, decisions
│   ├── pipeline/ graph/     # PlanAnalysisPanel, PlanActions, pipeline graphs
│   └── layout/ Sidebar.tsx  # Sidebar + PageHeader (dense variant)
└── pages/                   # One file per route
```

**Headless verification recipe (used during development):**
start a dev server, seed `sessionStorage.as_objective_run` with a known run id via `addInitScript`, drive the page with `playwright-core` + `channel: 'chrome'`, and assert layout invariants (`main.scrollHeight <= main.clientHeight`, sequence `scrollHeight === clientHeight`, right column fully visible).

---

## Testing & CI

- **Backend:** `pytest tests/ -v` — `tests/unit` (12 suites), `tests/integration` (7 suites, needs Docker/Redis), `tests/e2e` scaffolded. Configured in `pyproject.toml` (`[tool.pytest.ini_options]`), plus `mypy app/` and `ruff check app/`.
- **Frontend:** `npx tsc -b` (type gate), `npm run lint` (oxlint), `npm run build` (tsc + vite).
- **CI:** `.github/workflows/ci.yml` runs `backend-test` and `frontend-check` on push and pull request.

---

## Notes

- **Celery Eager Mode:** set `CELERY_TASK_ALWAYS_EAGER=True` to run tasks inline without Redis. Note: asyncio event-loop conflicts can occur with LangGraph; use Redis for full integration testing.
- **Sandbox image:** build `autosage-runner:latest` before running sandbox executions or training jobs — it ships scikit-learn, XGBoost, LightGBM and PyTorch (CPU).
- **Generated code is never executed automatically.** Execution always requires an explicit Run in the Sandbox (or a training job).
- **LLM providers:** at least one of OpenRouter / Groq / HuggingFace for LLM-driven agents; without keys, agents fall back to deterministic heuristics (`LLM_ALLOW_HEURISTIC_FALLBACK=True`), and the pipeline planner reports `source: heuristic`.
- **PostgreSQL:** the backend needs Postgres with the `pgvector` extension; point `DATABASE_URL` at it (append `?sslmode=require` for managed instances).
- **Bundle size:** Monaco is bundled locally, so the main JS chunk is ~5 MB (~1.3 MB gzip). It is not fetched from a CDN; if the weight matters, lazy-loading the editor behind the `/sandbox` route is the next step.
- **Concurrent sessions:** starting a new query replaces the previous verification session and its pipeline draft.

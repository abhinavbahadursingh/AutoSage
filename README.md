# AutoSage
> **A Verified Multi-Agent System for Natural-Language-Driven Automated Machine Learning**

AutoSage transforms natural language problem descriptions and raw tabular datasets into rigorously verified, reproducible machine learning pipelines.

## Architectural Philosophy
1. **Multi-Agent Specialization**: Discrete LangGraph agents handle discovery, statistical profiling, preprocessing, model selection, experiment execution, and verification.
2. **Empirical Verification Gate**: Generated code and model outcomes pass automated AST security analysis, data leakage checks, metric sanity verification, and baseline dominance tests before acceptance.
3. **Reasoning Lineage (Evidence Trail)**: Every architectural choice is recorded in an immutable DAG: `Agent -> Decision -> Evidence -> Result`.
4. **Extraction-Verification Memory**: Verified winning solutions are fingerprinted and indexed using `pgvector` for semantic knowledge reuse.
5. **Secure Sandboxing**: LLM-generated code executes inside hardened, isolated Docker containers with no network access, non-root privileges, and strict resource quotas.

---

## Directory Structure
```
autoSage/
├── .github/workflows/          # CI and container build workflows
├── backend/                    # FastAPI Backend, LangGraph Agents, and Celery Workers
│   ├── alembic/                # Database migrations
│   ├── app/
│   │   ├── agents/             # LangGraph agent definitions & state schemas
│   │   ├── api/v1/             # REST & SSE streaming routers
│   │   ├── core/               # Configuration, security, telemetry, database
│   │   ├── engine/             # LLM gateway, Docker sandbox, verification, memory
│   │   ├── models/             # SQLAlchemy ORM database models
│   │   ├── schemas/            # Pydantic v2 schemas
│   │   └── workers/            # Celery application & asynchronous worker tasks
│   └── tests/                  # Unit, integration, and E2E test suites
├── frontend/                   # Next.js 14 App Router, Tailwind CSS, shadcn/ui
│   ├── app/                    # Pages: Dashboard, Runs, Evidence DAG, Artifacts
│   ├── components/             # UI components, Streaming console, ReactFlow DAG
│   └── lib/                    # API client, SSE streaming listeners, Zustand stores
├── data/
│   ├── uploads/                # Ephemeral storage for raw user datasets
│   └── artifacts/              # Final exported models, pipelines, and bundles
└── docker-compose.dev.yml      # Local dev environment (PostgreSQL + pgvector, Redis, MLflow)
```

---

## Implementation Status

| Phase | Component | Status |
|-------|-----------|--------|
| **1** | FastAPI Foundation, PostgreSQL + pgvector, Alembic | ✅ Complete |
| **2** | Authentication (JWT, Better Auth compatible, dev-token) | ✅ Complete |
| **3** | Workspaces, Projects, Datasets CRUD | ✅ Complete |
| **4** | Experiment Lifecycle API (create, list, get, update, delete, start, cancel) | ✅ Complete |
| **5** | Celery + Redis Async Execution, Retry/Backoff, Task Routing | ✅ Complete |
| **6** | LangGraph Workflow, State, Checkpointing, Runner | ✅ Complete |
| **7** | Specialized Agents (Orchestrator, Discovery, Profiler, Preprocessor, ModelSelector, MLExperiment, Verifier) | ✅ Complete |
| **8** | LLM Gateway (OpenRouter, Groq, HF), Structured Outputs, Heuristic Fallback | ✅ Complete |
| **9** | Modular Tool System (Registry, 7 Built-in Tools, Agent→Tool→Result) | ✅ Complete |
| **10** | Docker ML Sandbox (CPU/Memory limits, No Network, Non-root, Cleanup) | ✅ Complete |
| **11** | Frontend-Backend Integration (Auth, Experiments, Polling, Error Handling) | ✅ Complete |

---

## Quickstart

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- Docker Desktop with Compose (for PostgreSQL, Redis, MLflow)

### 2. Local Infrastructure Setup
```bash
# Clone and enter repo
cd autoSage

# Start Postgres (with pgvector), Redis, and MLflow
docker compose -f docker-compose.dev.yml up -d

# Verify services are healthy
docker compose -f docker-compose.dev.yml ps
```

### 3. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell):
.venv\Scripts\Activate.ps1
# Activate (Linux/macOS):
# source .venv/bin/activate

# Install dependencies
pip install -e .

# Run database migrations
alembic upgrade head

# Configure environment (copy template and edit)
cp .env.example .env
# Edit .env with your Supabase/Postgres credentials and API keys

# Start FastAPI server (with auto-reload)
uvicorn app.main:app --reload --port 8000
```

**Backend runs at:** `http://localhost:8000`  
**API Docs:** `http://localhost:8000/docs`  
**Health Check:** `http://localhost:8000/health`

### 4. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Configure API URL (optional - defaults to localhost:8000)
cp .env.example .env.local
# Edit .env.local if backend runs elsewhere

# Start Next.js dev server
npm run dev
```

**Frontend runs at:** `http://localhost:3000`

---

## Key Environment Variables

### Backend (`backend/.env`)
| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL + pgvector connection string | Required |
| `REDIS_URL` | Redis for Celery broker | `redis://localhost:6379/0` |
| `CELERY_TASK_ALWAYS_EAGER` | Run tasks inline (no broker needed for dev) | `False` |
| `SUPABASE_URL` | Supabase project URL (e.g. https://xyz.supabase.co) | Required |
| `SUPABASE_ANON_KEY` | Supabase public anon key | Required |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | Required for prod |
| `SUPABASE_STORAGE_BUCKET` | Supabase storage bucket name | `autosage-files` |
| `AUTH_DEV_TOKEN_ENABLED` | Enable `/auth/dev-token` endpoint | `True` (dev only) |
| `OPENROUTER_API_KEY` / `GROQ_API_KEY` / `HUGGINGFACE_API_TOKEN` | LLM provider keys | Optional |
| `SANDBOX_IMAGE_TAG` | Docker image for ML sandbox | `autosage-runner:latest` |

### Frontend (`frontend/.env.local`)
| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | Backend API base URL | `http://localhost:8000/api/v1` |

---

## Development Commands

### Backend
```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests (requires Docker/Redis)
pytest tests/integration/ -v

# Run all tests
pytest tests/ -v

# Type checking
mypy app/

# Linting
ruff check app/

# Build sandbox Docker image
cd app/engine/sandbox/dockerfile
docker build -t autosage-runner:latest .
```

### Frontend
```bash
# Type checking
npx tsc --noEmit

# Linting
npm run lint

# Production build
npm run build
npm start
```

---

## API Endpoints (v1)

### Authentication
- `POST /auth/dev-token` — Mint development JWT (dev only)
- `GET /auth/me` — Current user profile
- `GET /auth/session` — Session introspection

### Workspaces
- `GET /workspaces` — List user workspaces
- `POST /workspaces` — Create workspace

### Experiments
- `POST /experiments` — Create experiment (status: CREATED)
- `GET /experiments` — List experiments (paginated, filterable)
- `GET /experiments/{id}` — Get experiment with result_summary
- `PATCH /experiments/{id}` — Update experiment
- `DELETE /experiments/{id}` — Delete experiment
- `POST /experiments/{id}/start` — Enqueue workflow (CREATED → QUEUED)
- `POST /experiments/{id}/cancel` — Cancel experiment

---

## Frontend Integration Layer

The frontend uses a clean service/hook architecture:

```
lib/
├── api.ts              # Axios client, token interceptors, 401 handler
├── services/
│   ├── auth.ts         # loginWithDevToken, fetchMe, fetchSession, logout
│   ├── experiments.ts  # listExperiments, getExperiment, createExperiment, startExperiment, cancelExperiment
│   └── workspaces.ts   # listWorkspaces, createWorkspace, ensureDefaultWorkspace
├── hooks/
│   ├── useExperiments  # Paginated list with status filter
│   └── useExperiment   # Single experiment with auto-polling (2s) on active statuses
├── stores/
│   └── useAuthStore    # Zustand: session restore, login, logout, error handling
└── types.ts            # TypeScript mirrors of Pydantic schemas
```

---

## Verified Flow

```
1. Login (POST /auth/dev-token) → JWT stored in localStorage
2. AuthStore.restore() → GET /auth/me validates token
3. Create Experiment (POST /experiments) → Returns CREATED
4. List Experiments (GET /experiments) → useExperiments hook
5. View Experiment (GET /experiments/{id}) → useExperiment hook
6. Start Experiment (POST /experiments/{id}/start) → Returns QUEUED + celery_task_id
7. Poll via useExperiment (2s interval) → RUNNING → COMPLETED/FAILED
8. Display workflow stages, metrics, artifacts, verification results
```

---

## Testing the Complete Flow

```bash
# 1. Start infrastructure
docker compose -f docker-compose.dev.yml up -d

# 2. Start backend
cd backend && .venv\Scripts\Activate.ps1 && uvicorn app.main:app --reload --port 8000

# 3. Start frontend
cd frontend && npm run dev

# 4. Open http://localhost:3000
#    - Sign in with dev@autosage.local (dev token)
#    - Create experiment via natural language prompt
#    - Start experiment → watch workflow stages execute
#    - View results, metrics, verification summary
```

---

## Notes

- **Celery Eager Mode**: For development without Redis, set `CELERY_TASK_ALWAYS_EAGER=True` in `.env`. Note: asyncio event loop conflicts may occur with LangGraph; use Redis for full integration testing.
- **Docker Sandbox**: The ML sandbox image (`autosage-runner`) must be built before running training jobs. It includes scikit-learn, XGBoost, LightGBM, and PyTorch (CPU).
- **LLM Providers**: At least one provider API key (OpenRouter, Groq, or HuggingFace) is required for LLM-driven agents. Without keys, agents fall back to deterministic heuristics.
- **Supabase/PostgreSQL**: The backend expects a PostgreSQL instance with pgvector extension. Update `DATABASE_URL` in `.env` accordingly.
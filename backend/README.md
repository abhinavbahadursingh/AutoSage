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

## Quickstart

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ & pnpm / npm
- Docker Desktop with Compose

### 2. Local Infrastructure Setup
```bash
# Clone and enter repo
cd autoSage

# Start Postgres (with pgvector), Redis, and MLflow
docker compose -f docker-compose.dev.yml up -d

# Copy environment template
cp .env.example .env
```

### 3. Backend Setup
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to access the AutoSage interface.

# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: ML practitioners — data scientists and ML engineers working with raw tabular datasets. They describe problems in natural language, upload CSVs, configure experiments, and need rigorous, reproducible results quickly.

Secondary (open): software engineers without deep ML expertise, and collaborative teams sharing workspaces — not yet confirmed as primary.

Situation: local development loop with Docker infra (Postgres + pgvector, Redis, MLflow), creating workspaces → projects → datasets → experiments, starting runs and polling for RUNNING → COMPLETED/FAILED with verification summary.

## Product Purpose

AutoSage transforms natural-language problem descriptions and raw tabular datasets into rigorously verified, reproducible machine learning pipelines.

Why it exists: remove manual pipeline glue while keeping empirical rigor — every architectural choice must be evidenced, not just generated.

Success means: a started experiment completes with sane metrics, baseline dominance, no leakage/security failures, plus exported artifacts, evidence DAG, and reusable memory.

## Positioning

Verified lineage. Every choice is recorded in an immutable DAG: `Agent -> Decision -> Evidence -> Result`, gated by automated AST security analysis, data leakage checks, metric sanity verification, and baseline dominance tests before acceptance.

Neighbors can generate pipelines; they cannot truthfully copy the verification gate + reasoning lineage + sandboxed reproducibility as one system.

## Operating Context

Workflows:
1. Login via dev-token → JWT in localStorage → `AuthStore.restore()` validates via `GET /auth/me`.
2. Create workspace / project / dataset (CRUD).
3. Create experiment (status CREATED) via natural-language prompt.
4. Start experiment (`POST /experiments/{id}/start` → QUEUED + celery_task_id).
5. Poll via `useExperiment` (2s interval) through RUNNING → COMPLETED/FAILED; view stages, metrics, artifacts, verification.

Environments: local dev — Docker Compose (Postgres + pgvector, Redis, MLflow at :5000), FastAPI backend at :8000, Vite frontend at :3000 (actual: Vite, not Next.js 14 despite README claim).

Agents & execution: LangGraph workflow with checkpointing — Orchestrator, Discovery, Profiler, Preprocessor, ModelSelector, MLExperiment, Verifier; Celery + Redis async execution with retry/backoff; LLM gateway (OpenRouter, Groq, HF) with deterministic heuristic fallback; modular tool registry (7 built-in); hardened Docker sandbox (no network, non-root, CPU/memory limits, cleanup).

Frontend routes: `/` Home, `/login`, `/workspace`, `/new`, `/experiments`, `/agents`, `/evidence`, `/memory`, `/datasets`, `/models`, `/settings` — with sidebar layout, protected routes, streaming console, ReactFlow DAG (Evidence), Zustand stores, Axios + SSE listeners.

## Capabilities and Constraints

Confirmed functionality:
- Auth: JWT, dev-token minter (`POST /auth/dev-token`), `GET /auth/me`, `GET /auth/session`.
- Workspaces, Projects, Datasets CRUD.
- Experiments: create, list (paginated/filterable), get with result_summary, update, delete, start, cancel.
- Async execution, MLflow tracking, pgvector semantic memory of winning solutions (fingerprint + index).

Technical constraints (must preserve):
- Backend Python 3.11+, FastAPI, SQLAlchemy, Alembic, Celery + Redis.
- Frontend Vite + React 19 + React Router 7 + Tailwind CSS 4 + Framer Motion.
- Infra: PostgreSQL + pgvector required (`DATABASE_URL`), Redis (`REDIS_URL`), `autosage-runner:latest` sandbox image must be built (scikit-learn, XGBoost, LightGBM, Torch CPU).
- LLM keys optional; without keys agents use heuristics.
- `CELERY_TASK_ALWAYS_EAGER=True` allows dev without broker but conflicts with LangGraph asyncio — use Redis for full integration.

Terminology: Workspace > Project > Dataset > Experiment > Run stages > Artifacts; Verification = AST + leakage + sanity + baseline.

Explicitly undecided: expansion beyond ML practitioners, pricing/licensing, hosted vs self-hosted defaults.

## Brand Commitments

Name: AutoSage. Tagline: A Verified Multi-Agent System for Natural-Language-Driven Automated Machine Learning.

No confirmed voice, logo, palette, or personality constraints volunteered. Do not invent them.

## Evidence on Hand

Real: `README.md` architecture + API list; `backend/openapi.json`; `backend/app/agents/`, `engine/`, `api/v1/`; `frontend/src/App.tsx` routes, `pages/`, `components/`, `store/`; `docker-compose.dev.yml` services.

Absences future work must not fabricate: no testimonials, customers, case studies, benchmarks, pricing, or press. Do not invent datasets, metrics, or model wins.

## Product Principles

1. Verification before acceptance — no result ships without passing security, leakage, sanity, and baseline gates.
2. Evidence over claims — every decision links to data and code in the DAG.
3. Reproducibility by default — sandboxed, versioned, exportable bundles.
4. Natural language in, rigor out — accessibility never lowers the bar.
5. Reuse what is proven — verified wins become indexed memory, not folklore.

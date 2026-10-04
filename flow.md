# AutoSage Experiment Execution — Full Lifecycle

From **Run Experiment** button click to a persisted, rendered **COMPLETED** experiment.
Every layer: React page → Zustand store → REST API → Celery worker → LangGraph workflow →
WebSocket events → DB persistence → frontend re-render.

---

## 1. Frontend — button click (`frontend/src/pages/NewExperiment.tsx:322`)

The `Run Experiment` button calls `submit()` (line 118) after Cmd/Ctrl+Enter or click:

- Guard: `if (!prompt.trim() || submitting || busy) return` — no double-submit.
- `setSubmitting(true)` swaps the label to `Creating…` and disables the button.
- Calls `createAndRun({ prompt, dataset, target, metric, budget, verificationLevel })` from the store.
- On success: `navigate('/workspace')`. Failures surface via a toast only.

The page itself shows a **Preflight** panel: a client-side `analyze()` heuristic derives
task type / metric hint / compare intent; a `memory` match list and a "POST /experiments →
start · JWT Bearer" backend hint. Note: `budget` and `verificationLevel` are UI-only — they
are **not** sent to the API (line 235, 254).

## 2. Store — `createAndRun` (`frontend/src/store/store.tsx:504`)

Inside the callback:

1. `setBusy(true)` — global busy flag; console log `[autosage] Run Experiment clicked · building config…`.
2. `ensureWorkspace()` — `GET /api/v1/workspaces?page=1&page_size=20`; reuse the first or
   `POST /api/v1/workspaces` to create "Default Workspace".
3. Title is derived from the first sentence of the prompt (≤58 chars).
4. Config is built from what the backend allows (`schemas/experiment.py`):
   - `prompt`, `dataset`, `dataset_name`, `target_column`, `evaluation_metric`, `source: 'frontend'`,
     `task_type` (`regression` vs `classification` inferred from the prompt regex),
     `metric` (only when in the allowed list), `split_strategy: 'random'`, `imbalance_handling: 'none'`.
5. `POST /api/v1/experiments` — creates the row (`status=CREATED`).
   `pushLog(created.id, { agent: 'Orchestrator', text: 'experiment created · …' })` and
   `console.info('[autosage] POST /experiments → created · status=…')`.
6. `POST /api/v1/experiments/{id}/start` — this enqueues execution.
   The response's status is applied (`applyRaw`), a log line + toast, and
   `console.info` shows the 7-stage pipeline. A local "stage plan" of all 7 agents is also
   pushed into the experiment's log feed as queued entries.
7. `setActiveId(created.id)`, `setSelectedNodeId(null)`, `refreshExperiments()` —
   the workspace switches to this experiment. `createAndRun` itself does **not** open the
   socket or poller: a `useEffect` keyed on `activeId` + experiment status (store.tsx:455)
   detects the new row in `QUEUED`, initialises `runState` (`stageIndex: 0`,
   `startedAt` from `started_at`), then calls `connectWs(exp.id)` and `startPolling(exp.id)`.
8. `setBusy(false)`.

## 3. REST — `POST /api/v1/experiments/{id}/start` (`backend/app/api/v1/endpoints/experiments.py:113`)

- Auth: `CurrentUser` dep + workspace-scoped `DbSession`.
- `experiment_service.start_for_user(session, id, user.id)` → enqueues a created experiment
  (`CREATED → QUEUED`, 409 otherwise), sets `started_at`, returns the experiment.
- `execution_service.enqueue_experiment(experiment.id)`:
  - `run_experiment.apply_async(args=[id], queue='experiments')` where the broker is
    `sqla+sqlite:///D:/autoSage/data/celery_broker.db` (from `backend/.env`), NOT Redis.
  - Fire-and-forget; returns a Celery task id. Broker failures → `ServiceUnavailableError`
    (HTTP 503) and the row stays QUEUED.
- `attach_task_id` persists `celery_task_id` on the row.
- Response: full `ExperimentRead` (id, config, status=QUEUED, celery_task_id, timestamps…).

## 4. Celery worker — picking up the task

The worker is started **embedded in the API process** (dev default) so events are local:

- `main.py` lifespan: `CELERY_EMBEDDED_WORKER=True` → `_start_embedded_worker()` spins up
  `celery_app.Worker(queues=['experiments'], pool='solo', concurrency=2)` in a daemon thread.
  Uvicorn `--reload` re-runs this on code changes; the serving child process binds port 8000.
- A standalone worker for production:
  `celery -A app.workers.celery_app worker -Q experiments --concurrency=2`.
  (Two stale standalone workers were killed during the fix — they were executing old code.)

When the task arrives, the registered name is `experiments.run_experiment`
(`tasks.py:62`, bound via `include=["app.workers.tasks"]`). The decorated task
`run_experiment` (tasks.py:475) executes:

```python
return _run_coro_sync(_execute_async(self, experiment_id))
```

## 5. Async/event-loop discipline (`tasks.py:67`)

`_run_coro_sync` handles both contexts:

- **No running loop** (plain worker thread — the normal case): `asyncio.run(...)`.
- **Running loop** (eager mode in a request thread): submit to a `ThreadPoolExecutor(max_workers=1)`
  thread that runs its own loop.

In both cases `_await_and_dispose_engine(coro)` wraps the coroutine and disposes any
SQLAlchemy engine cached for that loop, so the global asyncpg engine is rebuilt per loop
(`app.db.session.init_engine` is idempotent per loop, `dispose_engine_for_current_loop`
in the `finally`).

## 6. `_execute_async` body (`tasks.py:140`)

Around one workflow run:

1. `set_experiment_id` context var for log correlation.
2. `async with task_session() as session:` — a fresh `AsyncSessionLocal` session on the task's loop.
3. Load the experiment; skip terminals (`CANCELLED`, `COMPLETED`); if FAILED with no retries
   left, treat as terminal; normalize `CREATED → QUEUED → RUNNING` via
   `experiment_service.transition_experiment` (validates every transition).
4. `publish_experiment_started(...)` — WS event.
5. `final_state = await _run_workflow(experiment)` — `asyncio.to_thread(run_experiment_workflow, ...)`
   (LangGraph is sync; it executes off the event loop). `fail_stage` from config is honored.
6. On workflow exception: `_handle_workflow_error` — persist FAILED, publish
   `experiment.failed`, retry with exponential backoff while `retry_count < max_retries`.
7. On success: persist the enriched `result_summary` (below), then `RUNNING → COMPLETED`
   (or → FAILED when `final_state.status == 'FAILED'`), and `publish_experiment_completed`.
8. `clear_experiment_id` in `finally`.

Persisted `experiment.result_summary`:

```json
{
  "stages_completed": ["orchestrator","discovery","profiler","preprocessor","model_selector","ml_experiment","verification"],
  "current_stage": "verification",
  "status": "COMPLETED",
  "verification_passed": true,
  "verification": {"checks":["metric_sanity"],"passed":true,"summary":"…","failures":[]},
  "ml_result": {"metric":"accuracy","value":0.87,"validation_strategy":"holdout","notes":"…","attempt":1,"source":"heuristic"},
  "model_spec": {"family":"gradient_boosting","params":{"max_depth":4,"n_estimators":100},"candidates":[...],"rationale":"…"},
  "preprocessing_spec": {"imputation":"median","encoding":"one-hot","scaling":"standard","outlier_handling":"iqr",…},
  "dataset_info": {"name":"mock_dataset.csv","rows":1000,"columns":[...],"task_hint":"classification",…},
  "profile": {"n_rows":1000,"n_features":2,"missing_rate":0.0,"summary":"…",…},
  "attempt": 1,
  "events": ["…last 20 lifecycle strings…"]
}
```

## 7. Workflow runner (`backend/app/agents/runner.py`)

`run_experiment_workflow(experiment_id, workspace_id, max_attempts, fail_stage, checkpointer=None)`:

1. `build_experiment_graph(checkpointer)` — LangGraph `StateGraph` over
   `ExperimentWorkflowState` (a TypedDict with `operator.add` reducers for `stages_completed`,
   `events`, `errors`, `tool_calls`).
2. `initial_workflow_state(...)` — `attempt=0`, `max_attempts=settings.WORKFLOW_MAX_ATTEMPTS` (2),
   `status='RUNNING'`, `stages_completed=[]`, `events=['experiment … queued']`.
3. `config = {"configurable": {"thread_id": f"experiment-{id}"}}` — one isolated checkpoint
   history per experiment (`MemorySaver`; a durable checkpointer can be injected).
4. `graph.invoke(initial, config)` inside observability contexts
   (`TimingContext`, `trace_operation('langgraph.workflow')`, `log_with_context`).
5. Returns the final state dict. Node failures raise out; see §6.6.

## 8. Graph topology (`backend/app/agents/graph.py`)

Nodes (each wrapped by `_wrap_node_with_observability`):

```
START → orchestrator → discovery → profiler → preprocessor → model_selector
      → ml_experiment → verification → conditional(route_after_verification)
            ↑                                    |   |     |
            └── retry (attempt < max_attempts) ──┘   |     |
                                              complete |  fail
                                                      END  failed → END
```

- `route_after_verification`: `verification_passed` → `"complete"`; else while
  `attempt < max_attempts` → `"retry"` (loops back to `ml_experiment`); otherwise `"fail"`
  → `mark_failed` terminal node → `status='FAILED'`, `stages_completed=['failed']`.
- `thread_id_for`: `experiment-<uuid>`.
- `STAGE_ORDER` (canonical): `orchestrator, discovery, profiler, preprocessor, model_selector,
  ml_experiment, verification` — mirrored in the frontend's `BACKEND_STAGE_MAP`.

### Node semantics (all degrade to deterministic heuristics when no LLM provider is configured —
`LLM_ALLOW_HEURISTIC_FALLBACK=True`):

| node | agent class | state slot written |
|---|---|---|
| orchestrator | OrchestratorAgent | `events`, plan |
| discovery | DiscoveryAgent | `dataset_info` |
| profiler | ProfilerAgent | `profile` |
| preprocessor | PreprocessorAgent | `preprocessing_spec` |
| model_selector | ModelSelectorAgent | `model_spec` |
| ml_experiment | MLExperimentAgent | `ml_result`, `attempt` |
| verification | VerifierAgent | `verification`, `verification_passed` |

Each node returns a structured Pydantic output (`app/agents/schemas.py` — every field a real
artifact: `family`, `params`, `candidates`, `rationale`, `checks`, `failures`, `metric`, `value`,
`validation_strategy`, `n_rows`, `feature_types`, …).

## 9. Per-stage live publishing (`graph.py` wrapper)

Around every node call the wrapper:

1. Emits `agent.started` (`agent_name=stage`, `stage=stage`, `attempt`).
2. For `ml_experiment`: emits `ml.started` (`model_family`, `model_params` from `model_spec`).
3. Executes the node (raises → `agent.failed` is emitted, then the exception propagates).
4. Emits `agent.completed` (`output_summary` from the node's partial state update).
5. For `ml_experiment`: emits `ml.completed` with the real `ml_result` as `metrics`.
6. For `verification`: emits `verification.completed` (`passed`, `metrics=verification`,
   `gate_decision=complete|retry`).
7. Emits `experiment.completed` / `experiment.failed` are sent by the Celery task (§6).

Each node also logs `workflow_node_start/complete` with timing + tracing.

## 10. WS delivery (`event_publisher.py`, `websocket_manager.py`)

`publish_*` → `EventPublisher.publish_sync`:

- If called from a thread with **no running loop** (the worker thread): schedules
  `self.publish(...)` onto the **API main loop** via `asyncio.run_coroutine_threadsafe(...).result(timeout=10)`.
  This is why `main.py` lifespan captures `set_main_event_loop(asyncio.get_running_loop())` —
  WS sends only happen on the loop that owns the sockets.
- If a loop **is** running (eager/test path): delegates to a helper thread with its own loop.
- `publish` broadcasts through `get_connection_manager().broadcast(experiment_id, event)`
  to subscribed WS channels; when 0 local receivers, it hands off to the Redis pub/sub
  bridge (`EVENTS_CHANNEL_PREFIX = 'autosage:events:'`) — skipped silently when Redis is down.

The API process lifespan starts the bridge loop (`start_event_bridge`) for cross-process
events; in the embedded-worker setup all publishing is already in-process.

## 11. Frontend WS subscription (`store.tsx:230` `connectWs`)

After `createAndRun` (and on `run(exp.id)` — which *does* call `connectWs`/`startPolling`
itself):

1. Fresh token via `ensureToken`; `new WebSocket(experimentWsUrl(experimentId, token))`.
2. On `event.agent.started|agent.completed|agent.failed`: `stageFromBackend(p.stage)` →
   `setLiveStage(stage)`, plus a `pushLog` entry (`stage started · …` / `stage completed · …` /
   `stage failed · …`).
3. `experiment.started` → `liveStage='request'`. `ml.started` → `'training'`.
   `ml.completed` → `'evaluation'`. `verification.started/completed` → `'verification'`.
   `experiment.completed` → `'pipeline'` + `GET /experiments/{id}` → `applyRaw`.
4. On close: retries once with a fresh token on handshake failure; a 1008 with
   "not found|forbidden" stops retrying (polling fallback).
5. A parallel **poller** (`startPolling`) fetches the experiment every few seconds and
   `applyRaw`s it as a safety net.

`liveStage` drives `deriveNodes(status, resultSummary, liveStage)`:

- `QUEUED/RETRYING`: `request` node is `queued` ("Queued on backend worker.").
- `RUNNING`: stages before the live stage render `done`, the live one `active`, the rest
  `queued` (decision = real `stageOutputSummary` when available).
- `COMPLETED`: every node is `done`, and each node's `decision` is the real persisted
  stage output (dataset stats, profile summary, preprocessing rationale, model rationale,
  ml metric value, verification summary).
- `FAILED`/`CANCELLED`: only explicitly-completed stages stay `done`.

`mapExperiment` maps the rest: `dataset`, `target`, `metric` (falls back to `ml_result.metric`),
`model` (from `result_summary.model_spec.family`), `runtime` (`completed_at - started_at`),
`verificationStatus` (`COMPLETED → VERIFIED`, `FAILED → QUARANTINED`), `metrics` from
`ml_result` flattened to `{name: metric, value}`.

## 12. REST fetch paths used by the UI

- `GET /api/v1/experiments/{id}` → `applyRaw` — the final GET after `experiment.completed`
  carries the fully-persisted `result_summary`.
- `GET /api/v1/experiments?…` → `refreshExperiments` — refreshes the list/sidebar
  (`N stages · done/total`, status dot).
- `GET /api/v1/experiments/{id}` is also polled while `QUEUED/RUNNING/RETRYING`.

## 13. Workspace rendering (`frontend/src/pages/Workspace.tsx`)

For the active experiment:

1. **Header**: name, status badge (+ pulsing dot when live), verification badge,
   prompt/id, error banner if `errorDetail`, Cancel (active) or Run/Re-run button.
2. **Meta row**: Dataset · Model · Runtime · Metric · Target · Created.
3. **Execution timeline** (`ExecutionTimeline`): one node per `STAGE_META` entry,
   each colored by `NodeState` (`idle/queued/active/done/failed`), `doneCount/9 stages`.
4. **Metric cards** (top 3 of `exp.metrics`, e.g. `accuracy = 0.870`) — empty state
   `Primary metric: —`, `Model: —`, `Status`.
5. **Current activity**: the active/failed node, or the final node when COMPLETED;
   shows agent, elapsed/status, action, decision, and an "Inspect this agent →" link.
6. **Run result** (only when `status === 'COMPLETED'`):
   - **Final model** card: `model_spec.family`, rationale, primary metric.
   - **Pipeline / preprocessing** card: imputation / encoding / scaling / outliers /
     engineered features / dropped columns / rationale — all from `preprocessing_spec`.
   - **Verification** card: `verification.summary`, `checks[]`, `failures[]`.
   - **Stage outputs** card: per-stage decision text derived from the state slots.
   - **Event trail** card: last 14 entries of `result_summary.events`.
7. **AgentDrawer** (click a timeline node): reasoning/action, input, decision,
   per-stage logs (from the WS log feed), evidence placeholders, tool-call note.

## 14. Failure / retry / cancel branches

- Node raises → `agent.failed` → `_handle_workflow_error`: FAILED persisted,
  `experiment.failed` event, task retried with countdown
  `min(base·2^retries, cap)` while the experiment's `max_retries` allows; terminal after.
- Verification gate fails with attempts left → graph loops `ml_experiment → verification`.
- `mock_fail_stage` config forces a stage failure for tests.
- Cancel (`POST /experiments/{id}/cancel`): best-effort Celery revoke +
  `CANCELLED` transition; a queued task that was already delivered no-ops on pickup.
- Worker hard/soft time limits: 1800s/1500s. Task-level `max_retries=10` is a backstop.

## 15. Invariants / "no fake progress" guarantees

- Every stage transition originates from the LangGraph node wrapper, which also publishes
  the WS event — the UI cannot show a stage that did not execute.
- `result_summary.stages_completed` is exactly the orchestrator→verification trail,
  appended by each node's `stage_update` (immutable `operator.add` reducer).
- `COMPLETED` is only written after `transition_experiment` validates `RUNNING → COMPLETED`.
- Metric values shown are the raw `ml_result.value` from the heuristic/LLM execution path,
  not fabricated UI constants.

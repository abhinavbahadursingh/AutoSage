"""Fresh verification sessions.

One :class:`VerificationSession` per execution of the Objective Verification
flow. Creating one is the only way to start a verification, and every session
owns a brand-new :class:`Experiment`, so every fact an objective check can read
is scoped to that execution and nothing else.

There is deliberately no "latest run", no experiment picker and no resume path.
A page load starts empty; a submission creates a new session; a run id is
valid only for the session it was issued for and only for its owner.

Read-only by construction once created: this service issues SELECTs against
the session's experiment and never preprocesses a dataset, trains a model, or
re-runs a pipeline.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.engine.metrics import score_from_metrics
from app.engine.objective_verification.runner import run_verification, STAGE_CODE_GEN
from app.models.agent_execution import AgentExecution
from app.engine.objective_verification.definitions import OBJECTIVES_BY_ID
from app.models.artifact import Artifact
from app.models.decision import Decision
from app.models.evidence import EvidenceTrailNode
from app.models.experiment import Experiment, ExperimentStatus
from app.models.memory import ExperienceMemory
from app.models.run import PipelineRun
from app.models.verification import Verification
from app.models.verification_session import SessionStatus, VerificationSession
from app.models.workspace import Workspace
from app.schemas.objective_verification import (
    BriefFramed,
    BriefOutcome,
    BriefRequest,
    BriefStep,
    BriefThinking,
    BriefUnderstanding,
    DecisionRecord,
    ProjectBrief,
    SessionDataset,
    SessionStateResponse,
    StageUpdate,
    VerificationReport,
)

logger = logging.getLogger("autosage.objective_verification")

#: Marker written into the session experiment's config so these experiments
#: are identifiable (and filterable) outside this module.
VERIFICATION_SESSION_MARKER = "objective_verification_session"

# ---------------------------------------------------------------------------
# project-brief interpretation (deterministic; every sentence traces to a
# record — the page must never invent work that was not done)
# ---------------------------------------------------------------------------

#: goal kind -> lowercase keywords matched as whole words in the request.
#: Order matters: the first kind whose keyword appears wins, and the list runs
#: from the most specific narrative to the most generic one.
_GOAL_KEYWORDS: List[tuple] = [
    ("detection", ("detect", "detection", "object detection", "find objects", "identify objects", "recognize", "recognise")),
    ("churn", ("churn", "attrition", "cancel", "retention", "retain", "stop using")),
    ("anomaly", ("fraud", "anomaly", "outlier", "abnormal", "intrusion", "illegitimate")),
    ("forecasting", ("forecast", "time series", "next week", "next month", "next quarter", "tomorrow", "future demand", "in advance")),
    ("estimation", ("predict price", "house price", "price", "cost", "revenue", "eta", "duration", "how many", "how much", "amount", "sales volume", "estimate")),
    ("grouping", ("cluster", "segment", "group similar", "persona", "archetype", "without labels", "no target")),
    ("ranking", ("recommend", "ranking", "rank ", "next best", "top-n", "suggest one", "suggest the best")),
]

#: goal kind -> (one-line reading of the phrase, plain-language sentences).
_GOAL_TEXT: Dict[str, tuple] = {
    "detection": (
        "reads as an object-detection need: spot which objects (or classes) are "
        "present in each example and label them",
        [
            "In machine-learning terms, a detection request asks a model to answer, "
            "for every input record, which of a set of known classes is present — "
            "or whether any object of interest appears at all.",
            "AutoSage builds verified pipelines on tabular data, so to act on this "
            "need it treats the label column of the dataset (for example the class "
            "or presence indicator) as the prediction target and frames a "
            "supervised detection-style classifier on it.",
            "Pixel-level image processing is outside this system's scope today; "
            "the dataset you attach decides what the model can actually see.",
        ],
    ),
    "churn": (
        "reads as a churn problem: predicting which customers are about to leave "
        "before they actually do",
        [
            "Churn work treats each customer as one row and asks for a yes/no "
            "\"will this one leave\" answer — plus how confident the model is in "
            "that answer, so retention effort is spent where it changes things.",
            "The signals matter more than the algorithm here: tenure, contract "
            "shape, usage dips and support contacts usually carry most of the "
            "information, so the pipeline profiles them before modelling.",
        ],
    ),
    "anomaly": (
        "reads as an anomaly-detection need: flagging the records that do not "
        "behave like the rest",
        [
            "Anomaly problems put precision on the small side of the data: the "
            "model must separate the rare, abnormal records from the usual ones "
            "without being flooded by false alarms.",
            "If labelled examples of the abnormal case exist, this is handled as "
            "a supervised rare-class problem; if not, it starts from statistical "
            "profiling of what \"normal\" looks like in the data.",
        ],
    ),
    "forecasting": (
        "reads as a forecasting need: projecting what a value will be at a future "
        "point, not just what it is today",
        [
            "Forecasting adds a direction to prediction — rows are ordered in "
            "time, older data informs newer data, and evaluation must not let the "
            "model peek into the window it is predicting.",
            "On tabular records this is handled as a supervised regression-style "
            "problem with time-aware features; a dedicated sequence model over "
            "raw time series is outside the current pipeline scope.",
        ],
    ),
    "estimation": (
        "reads as an estimation problem: predicting a number for each record — "
        "a price, amount, duration or count",
        [
            "Estimation turns every row into one numeric answer, and the quality "
            "bar is how close that answer lands: how wrong is a typical "
            "prediction, not merely how often is it right.",
            "The pipeline profiles the number first (its range and skewness), "
            "because a skewed target usually changes the preprocessing and the "
            "metric choice more than the model family does.",
        ],
    ),
    "grouping": (
        "reads as a grouping need: finding the natural segments in the data when "
        "no labelled target exists yet",
        [
            "Grouping problems have no \"right answer\" column to learn from — "
            "the goal is structure: which records are actually similar to each "
            "other, and is that similarity stable enough to act on.",
            "This system's strength is verified supervised pipelines; profiling "
            "still runs here, but an unsupervised-only run is outside the current "
            "verification flow.",
        ],
    ),
    "ranking": (
        "reads as a ranking need: putting candidates in order of usefulness for "
        "each context",
        [
            "Ranking problems ask for an ordering, not a single label — which "
            "candidates belong at the top, and how much better the top is than "
            "the next one.",
            "On tabular data this is commonly framed as scoring candidates "
            "independently and sorting by the score; that framing applies here "
            "when the dataset carries candidate-level rows.",
        ],
    ),
    "supervised-prediction": (
        "reads as a supervised prediction task: learning how the other columns "
        "explain the chosen target",
        [
            "This is the core framing the whole pipeline is built around: rows of "
            "examples, one column holding the answer to predict, and a metric "
            "said to judge how well the predictions match reality.",
            "The pipeline discovers the dataset, profiles every column, cleans "
            "and encodes them, trains candidate models on real rows and measures "
            "on a split the models never saw — then reports the numbers as-is.",
        ],
    ),
}

#: pipeline decision_type -> plain-language step title in the brief.
_STEP_TITLES: Dict[str, str] = {
    "data_discovery": "Locate the dataset and size it up",
    "data_profiling": "Profile every column as it actually is",
    "preprocessing": "Decide how each column gets cleaned and encoded",
    "model_selection": "Choose the model family and the evaluation split",
    "training_complete": "Train on the real rows and measure",
    "verification_gate": "Empirically check the trained result",
}


def _word_hit(text: str, keywords: tuple) -> bool:
    lowered = text.lower()
    return any(re.search(rf"(?<!\w){re.escape(k)}", lowered) for k in keywords)


def _interpret_request(
    problem: str, config: Dict[str, Any], dataset_name: str
) -> tuple:
    """Deterministic reading of the request plain for the brief's section 2.

    Returns ``(goal_kind, headline, detail)``. The reading is conservative and
    keyword-driven: when nothing specific matches, it falls back to the
    supervised-prediction framing the system is built around.
    """
    kind = "supervised-prediction"
    for candidate, keywords in _GOAL_KEYWORDS:
        if _word_hit(problem, keywords):
            kind = candidate
            break
    headline, sentences = _GOAL_TEXT[kind]

    detail: List[str] = [f"Your request {headline}."]
    detail.extend(sentences)
    if dataset_name:
        detail.append(
            f"The work below is framed over the dataset you attached "
            f"({dataset_name}); with no dataset attached, this stays a design-time "
            f"plan until the dataset is supplied on the Objectives page."
        )
    task_type = str(config.get("task_type") or "").strip()
    if task_type:
        detail.append(f"The submitted configuration pins the task type to {task_type}.")
    return kind, headline, detail


def _humanize_step_title(decision_type: str) -> str:
    return _STEP_TITLES.get(
        decision_type, f"{decision_type.replace('_', ' ').capitalize()} recorded"
    )


def _compact_dict(values: Any) -> str:
    if not isinstance(values, dict) or not values:
        return ""
    return ", ".join(f"{key}={values[key]}" for key in list(values)[:6])


class FreshVerificationService:
    """Creates, runs and reads fresh objective-verification sessions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -- ownership ----------------------------------------------------------
    async def require_owned_workspace(
        self, workspace_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Workspace:
        """The workspace iff the caller owns it, else KeyError (-> 404)."""
        workspace = await self.session.get(Workspace, workspace_id)
        if workspace is None or workspace.owner_id != owner_id:
            # 404, never 403: do not reveal that a foreign workspace exists.
            raise KeyError("workspace not found")
        return workspace

    async def get_owned_session(
        self, run_id: uuid.UUID, owner_id: uuid.UUID
    ) -> VerificationSession:
        """Load a session iff ``owner_id`` created it, else KeyError (-> 404)."""
        try:
            run_uuid = uuid.UUID(str(run_id))
        except (TypeError, ValueError) as exc:
            raise KeyError("invalid run id") from exc

        row = await self.session.get(VerificationSession, run_uuid)
        if row is None or row.owner_id != owner_id:
            raise KeyError("verification session not found")
        return row

    # -- listing ------------------------------------------------------------
    async def list_sessions(
        self, owner_id: uuid.UUID, limit: int = 20
    ) -> List[VerificationSession]:
        """The caller's recent sessions, newest first.

        Ownership-enforced like every other read. Cheap listing: rows only,
        no frame history or report payload is decoded here — the heavy
        per-run detail still comes from :meth:`get_owned_session`.
        """
        result = await self.session.execute(
            select(VerificationSession)
            .where(VerificationSession.owner_id == owner_id)
            .order_by(VerificationSession.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # -- datasets -----------------------------------------------------------
    async def list_session_datasets(
        self, owner_id: uuid.UUID, workspace_id: Optional[uuid.UUID] = None
    ) -> List[SessionDataset]:
        """Datasets this user may submit for a fresh session.

        Two sources, in the order the worker itself resolves them: files in the
        upload directory, and ``datasets`` rows owned by one of the caller's
        workspaces. Rows belonging to other users are never returned.
        """
        from app.services import dataset_service

        results: List[SessionDataset] = []
        seen: set = set()

        try:
            upload_dir = Path(settings.UPLOAD_DIR)
            if upload_dir.is_dir():
                for path in sorted(upload_dir.iterdir()):
                    if not path.is_file() or path.name in seen:
                        continue
                    seen.add(path.name)
                    results.append(
                        SessionDataset(
                            name=path.name, size_bytes=path.stat().st_size
                        )
                    )
        except OSError:
            logger.warning("objective_verification_upload_dir_unreadable", exc_info=True)

        for row in await dataset_service.list_for_user(self.session, owner_id, workspace_id):
            if row["name"] in seen:
                continue
            seen.add(row["name"])
            results.append(
                SessionDataset(
                    name=str(row["name"]),
                    size_bytes=row.get("size_bytes"),
                    dataset_id=str(row["dataset_id"]) if row.get("dataset_id") else None,
                )
            )
        return results

    # -- session creation ---------------------------------------------------
    async def create_session(
        self,
        *,
        owner_id: uuid.UUID,
        workspace_id: uuid.UUID,
        problem_statement: str,
        dataset_name: str,
        config: Dict[str, Any],
    ) -> VerificationSession:
        """Create a brand-new session plus the isolated experiment it owns.

        Nothing is read from any previous experiment, and no pipeline is
        queued: the new experiment is left in ``CREATED`` so nothing can
        execute against it by accident.
        """
        workspace = await self.require_owned_workspace(workspace_id, owner_id)

        run_id = uuid.uuid4()
        experiment = Experiment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            name=f"Verification session {str(run_id)[:8]}",
            description=problem_statement[:2000],
            status=ExperimentStatus.CREATED.value,
            config={
                VERIFICATION_SESSION_MARKER: True,
                "run_id": str(run_id),
                "dataset_name": dataset_name,
                "task_type": config.get("task_type") or "classification",
                "primary_metric": config.get("primary_metric"),
                "prompt": problem_statement,
            },
            result_summary={},
            max_retries=0,
        )
        self.session.add(experiment)
        await self.session.flush()

        row = VerificationSession(
            id=run_id,
            owner_id=owner_id,
            workspace_id=workspace.id,
            experiment_id=experiment.id,
            problem_statement=problem_statement,
            dataset_name=dataset_name,
            config=config,
            status=SessionStatus.PENDING.value,
            events=[],
        )
        self.session.add(row)
        await self.session.commit()

        # Auto-link the most recent completed pipeline experiment in this
        # workspace so Objective 4 checks have real data to verify against.
        # If no completed experiment exists yet, the session runs without a
        # link and those checks report NOT_VERIFIED (honest, not faked).
        try:
            from sqlalchemy import select, desc

            linked = await self.session.execute(
                select(Experiment)
                .where(
                    Experiment.workspace_id == workspace_id,
                    Experiment.status == ExperimentStatus.COMPLETED.value,
                    # Exclude experiments owned by verification sessions
                    # themselves (they carry the VERIFICATION_SESSION_MARKER).
                    ~Experiment.config.op("@>")(
                        {"VERIFICATION_SESSION_MARKER": True}
                    ),
                )
                .order_by(
                    desc(Experiment.completed_at)
                    .nullslast(),
                    desc(Experiment.created_at),
                )
                .limit(1)
            )
            linked_exp = linked.scalars().first()
            if linked_exp is not None:
                row.linked_experiment_id = linked_exp.id
                await self.session.commit()
        except Exception:  # noqa: BLE001 - auto-link must never fail session creation
            logger.exception(
                "objective_verification_auto_link_failed",
                extra={"run_id": str(run_id)},
            )

        return row

    # -- link experiment ------------------------------------------------------
    async def link_experiment(
        self,
        run_id: uuid.UUID,
        owner_id: uuid.UUID,
        linked_experiment_id: uuid.UUID,
    ) -> VerificationSession:
        """Link a completed pipeline experiment to this verification session.

        Objective checks will then read facts from the linked experiment's
        records (decisions, evidence nodes, metrics, verification status)
        instead of this session's own empty experiment.

        Raises KeyError if the session is not owned by the caller, or if the
        linked experiment does not exist or is not COMPLETED.
        """
        row = await self.get_owned_session(run_id, owner_id)

        linked = await self.session.get(Experiment, linked_experiment_id)
        if linked is None:
            raise KeyError("linked experiment not found")
        if linked.status != ExperimentStatus.COMPLETED.value:
            raise KeyError(
                f"linked experiment is not COMPLETED (status={linked.status!r})"
            )
        if linked.workspace_id != row.workspace_id:
            raise KeyError("linked experiment is not in this session's workspace")

        row.linked_experiment_id = linked_experiment_id
        await self.session.commit()
        return row

    # -- scoped fact loading -----------------------------------------------
    async def _count(self, model: Any, experiment_id: Any) -> int:
        stmt = select(func.count()).select_from(model).where(
            model.experiment_id == experiment_id
        )
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    async def load_facts(self, session: VerificationSession) -> Dict[str, Any]:
        """Collect every fact the checks may reference.

        When ``session.linked_experiment_id`` is set (a completed pipeline
        experiment was linked via ``POST /sessions/{run_id}/link-experiment``),
        facts are read from that experiment's records instead of this
        session's own (empty) experiment. This lets Objective 4 checks
        — which need Decision, EvidenceTrailNode, AgentExecution and
        ExperienceMemory rows — find real evidence to verify against.
        """
        # Resolve which experiment to read facts from: a linked pipeline
        # experiment wins, otherwise fall back to this session's own experiment.
        effective_experiment_id = (
            session.linked_experiment_id or session.experiment_id
        )
        experiment = await self.session.get(Experiment, effective_experiment_id)
        if experiment is None:
            raise KeyError("verification session experiment not found")

        exp_id = experiment.id
        config = dict(experiment.config or {})
        summary = dict(experiment.result_summary or {})
        ml_result = dict(summary.get("ml_result") or {})

        metrics = dict(summary.get("metrics") or ml_result.get("metrics") or {})
        # The session's own config is authoritative for what the *request*
        # asked for; the result summary only exists once something has run.
        session_config = dict(session.config or {})
        primary_metric = str(
            summary.get("primary_metric")
            or ml_result.get("primary_metric")
            or session_config.get("primary_metric")
            or ""
        )
        primary_score = summary.get("primary_score")
        if primary_score is None:
            primary_score = ml_result.get("primary_score")

        baseline = dict(summary.get("baseline") or ml_result.get("baseline") or {})
        baseline_score = baseline.get("score")
        if baseline_score is None:
            baseline_score = score_from_metrics(baseline.get("metrics"), primary_metric)

        task_type = str(
            config.get("task_type")
            or dict(summary.get("profile") or {}).get("task_type")
            or ml_result.get("task_type")
            or session_config.get("task_type")
            or "classification"
        )

        agent_executions = await self._count(AgentExecution, exp_id)
        decisions = await self._count(Decision, exp_id)
        pipeline_runs = await self._count(PipelineRun, exp_id)
        artifacts = await self._count(Artifact, exp_id)
        memory_rows = await self._count(ExperienceMemory, exp_id)

        agent_names = [
            str(n)
            for n in (
                await self.session.execute(
                    select(AgentExecution.agent_name).where(
                        AgentExecution.experiment_id == exp_id
                    )
                )
            )
            .scalars()
            .all()
        ]

        decision_ids = [
            str(d)
            for d in (
                await self.session.execute(
                    select(Decision.id).where(Decision.experiment_id == exp_id)
                )
            )
            .scalars()
            .all()
        ]

        decisions_with_rationale = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(Decision)
                    .where(
                        Decision.experiment_id == exp_id,
                        Decision.rationale.isnot(None),
                        Decision.rationale != "",
                    )
                )
            ).scalar()
            or 0
        )
        decisions_with_confidence = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(Decision)
                    .where(
                        Decision.experiment_id == exp_id,
                        Decision.confidence.isnot(None),
                        Decision.confidence >= 0.0,
                        Decision.confidence <= 1.0,
                    )
                )
            ).scalar()
            or 0
        )

        evidence_nodes = 0
        if pipeline_runs:
            run_ids = [
                r
                for r in (
                    await self.session.execute(
                        select(PipelineRun.id).where(PipelineRun.experiment_id == exp_id)
                    )
                )
                .scalars()
                .all()
            ]
            if run_ids:
                evidence_nodes = int(
                    (
                        await self.session.execute(
                            select(func.count())
                            .select_from(EvidenceTrailNode)
                            .where(EvidenceTrailNode.run_id.in_(run_ids))
                        )
                    ).scalar()
                    or 0
                )

        verification_status: Optional[str] = None
        decision_statuses: Dict[str, Dict[str, Any]] = {}
        ver = (
            await self.session.execute(
                select(Verification).where(Verification.experiment_id == exp_id)
            )
        ).scalars().first()
        if ver is not None:
            verification_status = str(ver.overall_status)
            decision_statuses = dict(ver.decisions or {})

        memory_types = [
            str(m)
            for m in (
                await self.session.execute(
                    select(ExperienceMemory.memory_type).where(
                        ExperienceMemory.experiment_id == exp_id
                    )
                )
            )
            .scalars()
            .all()
        ]

        # The script this session generated, when a run has produced one.
        # Read from the artifact's own URI and only when it is a local file.
        # Absent for a fresh session, which is reported rather than assumed.
        session_script: Optional[str] = None
        script_artifact = (
            await self.session.execute(
                select(Artifact)
                .where(
                    Artifact.experiment_id == exp_id,
                    func.lower(Artifact.kind) == "script",
                )
                .order_by(Artifact.created_at.desc())
                .limit(1)
            )
        ).scalars().first()
        if script_artifact is not None:
            uri = str(script_artifact.uri or "")
            if uri:
                candidate = Path(uri)
                try:
                    if candidate.is_file():
                        session_script = candidate.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    logger.warning(
                        "objective_verification_script_unreadable",
                        extra={"uri": uri},
                    )

        return {
            "problem_statement": session.problem_statement,
            "dataset_name": session.dataset_name,
            "dataset_resolved": bool(config.get("dataset_name")),
            "config": dict(session.config or {}),
            "metrics": metrics,
            "task_type": task_type,
            "primary_metric": primary_metric,
            "primary_score": (
                float(primary_score) if isinstance(primary_score, (int, float)) else None
            ),
            "baseline_score": (
                float(baseline_score) if isinstance(baseline_score, (int, float)) else None
            ),
            "session_script": session_script,
            "agent_executions": agent_executions,
            "agent_names": agent_names,
            "decisions": decisions,
            "decisions_with_rationale": decisions_with_rationale,
            "decisions_with_confidence": decisions_with_confidence,
            "evidence_nodes": evidence_nodes,
            "verification_status": verification_status,
            "decision_statuses": decision_statuses,
            "memory_rows": memory_rows,
            "memory_types": memory_types,
            "pipeline_runs": pipeline_runs,
            "artifacts": artifacts,
            "has_result": bool(summary.get("ml_result") or metrics),
        }

    # -- execution ----------------------------------------------------------
    async def execute_session(self, session_row: VerificationSession) -> VerificationReport:
        """Run the fixed flow for one session and persist its outcome.

        Each frame is committed the moment it is emitted, so the SSE endpoint
        can read progress from the database while the run is still going and a
        client that subscribes late — or after a reconnect — replays every
        stage it missed instead of restarting the run.
        """
        session_row.status = SessionStatus.RUNNING.value
        session_row.started_at = datetime.utcnow()
        session_row.events = []
        await self.session.commit()

        async def _persist(update: StageUpdate) -> None:
            frames = list(session_row.events or [])
            frames.append(update.model_dump(mode="json"))
            session_row.events = frames
            await self.session.commit()

        try:
            facts = await self.load_facts(session_row)
            report = await run_verification(
                run_id=str(session_row.id),
                experiment_id=str(session_row.experiment_id),
                facts=facts,
                progress=_persist,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the client
            logger.exception(
                "objective_verification_run_failed",
                extra={"run_id": str(session_row.id)},
            )
            session_row.status = SessionStatus.FAILED.value
            session_row.error = str(exc)
            session_row.completed_at = datetime.utcnow()
            await self.session.commit()
            raise

        # Persist code-generation artifacts from the SSE event stream so they
        # are available on later state reads (reconnect, state API) without
        # requiring the client to re-parse events.
        codegen_files: List[Dict[str, str]] = []
        codegen_activity: List[str] = []
        codegen_status_val: Optional[str] = None
        codegen_message_val: str = ""
        design_record: Dict[str, Any] = {}
        decision_records: List[Dict[str, Any]] = []
        for ev in (session_row.events or []):
            try:
                upd = StageUpdate.model_validate(ev)
                if upd.stage == STAGE_CODE_GEN and upd.payload:
                    payload = upd.payload or {}
                    codegen_files = payload.get("generated_files", []) or []
                    codegen_activity = payload.get("activity", []) or []
                    codegen_status_val = payload.get("status", codegen_status_val)
                    codegen_message_val = payload.get("message", codegen_message_val) or codegen_message_val
                    design_record = payload.get("design", design_record) or design_record
                    decision_records = payload.get("decisions", decision_records) or decision_records
            except Exception:  # noqa: BLE001 - never corrupt the session on a read
                logger.warning(
                    "objective_verification_bad_codegen_event",
                    extra={"run_id": str(session_row.id)},
                )

        session_row.generated_files = codegen_files
        session_row.activity_log = codegen_activity
        session_row.design_record = design_record
        session_row.decision_records = decision_records
        session_row.code_generation_status = codegen_status_val
        session_row.code_generation_message = codegen_message_val

        session_row.status = SessionStatus.COMPLETED.value
        session_row.report = report.model_dump(mode="json")
        session_row.overall_status = report.overall_status.value
        session_row.overall_confidence = report.overall_confidence
        session_row.completed_at = datetime.utcnow()
        await self.session.commit()
        return report

    async def verify_facts_directly(
        self,
        *,
        run_id: uuid.UUID,
        experiment_id: uuid.UUID,
        problem_statement: str,
        dataset_name: str,
        config: Dict[str, Any],
    ) -> VerificationReport:
        """Run the flow over a caller-supplied fact set, with no session row.

        Exists so the runner's intake gate can be exercised on its own. The
        HTTP path always goes through :meth:`execute_session`, which loads its
        facts from the session's own experiment.
        """
        return await run_verification(
            run_id=str(run_id),
            experiment_id=str(experiment_id),
            facts={
                "problem_statement": problem_statement,
                "dataset_name": dataset_name,
                "config": dict(config),
                "metrics": {},
                "primary_score": None,
                "baseline_score": None,
                "session_script": None,
                "agent_executions": 0,
                "agent_names": [],
                "decisions": 0,
                "decisions_with_rationale": 0,
                "decisions_with_confidence": 0,
                "evidence_nodes": 0,
                "verification_status": None,
                "decision_statuses": {},
                "memory_rows": 0,
                "memory_types": [],
                "pipeline_runs": 0,
                "artifacts": 0,
                "has_result": False,
            },
            progress=None,
        )

    # -- project brief ------------------------------------------------------
    async def build_project_brief(self, row: VerificationSession) -> ProjectBrief:
        """A spoken-word walkthrough of ONE given project, from its records.

        Sections: what was said (verbatim), what the phrase reads as
        (deterministic interpretation), the formal framed problem, the
        pipeline's own recorded requirement-derivation steps, the recorded
        thought process, and the measured outcome. Deliberately NOT an
        objective-verification report — those stay on the Objectives page.
        """
        config = dict(row.config or {})
        dataset_name = row.dataset_name or ""

        # The linked pipeline experiment (if one is linked yet) carries the
        # run's real records: decisions, measured results and its config.
        exp = None
        if row.linked_experiment_id:
            exp = await self.session.get(Experiment, row.linked_experiment_id)
        result_summary = dict(exp.result_summary or {}) if exp is not None else {}

        pipeline_decisions: List[Decision] = []
        if exp is not None:
            try:
                result = await self.session.execute(
                    select(Decision)
                    .where(Decision.experiment_id == exp.id)
                    .order_by(Decision.created_at)
                )
                pipeline_decisions = list(result.scalars().all())
            except Exception:  # noqa: BLE001 - fake session may not support order_by
                result = await self.session.execute(
                    select(Decision).where(Decision.experiment_id == exp.id)
                )
                pipeline_decisions = list(result.scalars().all())

        # -- section 2: what the phrase reads as ------------------------------
        kind, headline, detail = _interpret_request(
            row.problem_statement, config, dataset_name
        )

        # -- what the pipeline discovered, for the framed statement -----------
        discovered: Dict[str, Any] = {}
        for d in pipeline_decisions:
            if d.decision_type == "data_discovery" and isinstance(d.payload, dict):
                discovered = dict(d.payload)
                break
        discovered_rows = discovered.get("rows")
        discovered_target = discovered.get("target")
        discovered_columns = discovered.get("columns")

        if exp is not None and not dataset_name:
            exp_cfg = dict(exp.config or {})
            dataset_name = str(exp_cfg.get("dataset_name") or exp_cfg.get("dataset") or "")

        primary_metric_cfg = config.get("primary_metric")
        result_metric = result_summary.get("primary_metric")
        metric_name = primary_metric_cfg or result_metric

        target_name = (
            config.get("target_column")
            or discovered_target
            or result_summary.get("target")
        )
        problem_type = config.get("task_type") or result_summary.get("task_type")

        validation_strategy = (
            result_summary.get("validation_strategy")
            or dict(row.design_record or {}).get("validation_strategy")
            or "a held-out split the models never saw during training"
        )

        # -- section 3: the formal framed problem -----------------------------
        dataset_bits = []
        if dataset_name:
            dataset_bits.append(f"the records in {dataset_name}")
        else:
            dataset_bits.append("the dataset you will attach")
        if isinstance(discovered_rows, int):
            dataset_bits.append(f"{discovered_rows} rows")
        if isinstance(discovered_columns, (list, tuple)):
            dataset_bits.append(f"{len(discovered_columns)} columns")

        if target_name:
            target_phrase = f"predict the {target_name} column"
        else:
            target_phrase = (
                "predict the target column once the dataset's own schema resolves it"
            )
        metric_word = str(metric_name) if metric_name else "the task-appropriate metric"
        framed_statement = (
            f"Given {dataset_bits[0]}"
            + (f" ({', '.join(dataset_bits[1:])})" if len(dataset_bits) > 1 else "")
            + f", {target_phrase} for each new example "
            + (f"({problem_type}) " if problem_type else "")
            + f"— judged by {metric_word}, evaluated on {validation_strategy}."
        )
        framed_statement = framed_statement.replace("  ", " ")

        # -- section 4: how the system understood exactly what is needed ------
        requirements: List[BriefStep] = []
        if pipeline_decisions:
            index = 0
            for d in pipeline_decisions:
                detail_text = (d.rationale or "").strip() or _compact_dict(d.payload)
                if not detail_text:
                    continue
                index += 1
                requirements.append(
                    BriefStep(
                        step=index,
                        title=_humanize_step_title(d.decision_type),
                        detail=detail_text,
                        confidence=d.confidence,
                        origin=f"pipeline decision: {d.decision_type}",
                    )
                )
        else:
            design_decisions = [
                rec
                for rec in (row.decision_records or [])
                if isinstance(rec, dict) and str(rec.get("decision") or "").strip()
            ]
            for rec in design_decisions:
                detail_text = str(rec.get("rationale") or rec.get("decision") or "").strip()
                if not detail_text:
                    continue
                requirements.append(
                    BriefStep(
                        step=len(requirements) + 1,
                        title=_humanize_step_title(str(rec.get("category") or "design")),
                        detail=detail_text,
                        confidence=(
                            rec.get("confidence")
                            if isinstance(rec.get("confidence"), (int, float))
                            else None
                        ),
                        origin=f"design-time decision: {rec.get('category') or 'general'}",
                    )
                )

        # -- section 5: the recorded thought process --------------------------
        design = dict(row.design_record or {})
        approach: List[str] = []
        algorithm_approval = None
        for d in pipeline_decisions:
            if d.decision_type == "model_selection":
                algorithm_approval = (d.rationale or "").strip()
                break
        if algorithm_approval:
            approach.append(algorithm_approval)
        if design.get("algorithm"):
            hyperparams = _compact_dict(design.get("hyperparameters"))
            line = f"Chosen model family: {design['algorithm']}"
            if hyperparams:
                line += f" ({hyperparams})"
            approach.append(line)

        assumptions: List[str] = []
        alternatives: List[str] = []
        for item in design.get("assumptions") or []:
            text = str(item).strip()
            if text and text not in assumptions:
                assumptions.append(text)
        for item in design.get("alternatives") or []:
            text = str(item).strip()
            if text and text not in alternatives:
                alternatives.append(text)
        for rec in row.decision_records or []:
            if not isinstance(rec, dict):
                continue
            for item in rec.get("assumptions") or []:
                text = str(item).strip()
                if text and text not in assumptions:
                    assumptions.append(text)
            for item in rec.get("alternatives") or []:
                text = str(item).strip()
                if text and text not in alternatives:
                    alternatives.append(text)

        thinking = BriefThinking(
            approach=approach,
            assumptions=assumptions,
            alternatives=alternatives,
            validation_strategy=(
                validation_strategy
                if validation_strategy
                != "a held-out split the models never saw during training"
                else None
            ),
        )

        # -- section 6: what the work actually produced -----------------------
        baseline_summary = result_summary.get("baseline")
        baseline_score = result_summary.get("baseline_score")
        if baseline_score is None and isinstance(baseline_summary, dict):
            baseline_score = baseline_summary.get("score")
        verification_summary = result_summary.get("verification")
        gate_passed: Optional[bool]
        if isinstance(verification_summary, dict):
            gate_passed = verification_summary.get("passed")
            gate_summary = verification_summary.get("summary")
        else:
            gate_passed = result_summary.get("verification_passed")
            gate_summary = None

        outcome = BriefOutcome(
            available=exp is not None,
            algorithm=result_summary.get("selected_model"),
            primary_metric=metric_name if isinstance(metric_name, str) else None,
            primary_score=(
                result_summary.get("primary_score")
                if isinstance(result_summary.get("primary_score"), (int, float))
                else None
            ),
            baseline_score=baseline_score if isinstance(baseline_score, (int, float)) else None,
            gate_passed=gate_passed if isinstance(gate_passed, bool) else None,
            gate_summary=str(gate_summary) if gate_summary else None,
        )

        return ProjectBrief(
            run_id=str(row.id),
            request=BriefRequest(
                problem_statement=row.problem_statement,
                dataset_name=dataset_name,
                config=config,
            ),
            understanding=BriefUnderstanding(
                goal_kind=kind,
                headline=headline,
                detail=detail,
            ),
            framed=BriefFramed(
                statement=framed_statement,
                problem_type=str(problem_type) if problem_type else None,
                target=str(target_name) if target_name else "resolved from the dataset schema",
                metric=str(metric_name) if metric_name else "task-appropriate",
                evaluation=validation_strategy,
            ),
            requirements=requirements,
            thinking=thinking,
            outcome=outcome,
        )

    # -- reads --------------------------------------------------------------
    def to_state(self, row: VerificationSession) -> SessionStateResponse:
        """Wire representation of a session, replaying its stored frames."""
        updates: List[StageUpdate] = []
        for frame in row.events or []:
            try:
                updates.append(StageUpdate.model_validate(frame))
            except Exception:  # noqa: BLE001 - never fail a read on one bad frame
                logger.warning("objective_verification_bad_frame", exc_info=True)
        return SessionStateResponse(
            run_id=str(row.id),
            experiment_id=str(row.experiment_id),
            linked_experiment_id=(
                str(row.linked_experiment_id) if row.linked_experiment_id else None
            ),
            status=row.status,
            problem_statement=row.problem_statement,
            dataset_name=row.dataset_name,
            config=dict(row.config or {}),
            updates=updates,
            report=(
                VerificationReport.model_validate(row.report) if row.report else None
            ),
            generated_files=list(row.generated_files or []),
            activity_log=list(row.activity_log or []),
            design=dict(row.design_record or {}),
            decisions=[
                DecisionRecord.model_validate(d)
                for d in (row.decision_records or [])
                if isinstance(d, dict)
            ],
            code_generation_status=row.code_generation_status,
            code_generation_message=row.code_generation_message,
            overall_status=row.overall_status,
            overall_confidence=row.overall_confidence,
            error=row.error,
            running=row.running,
            created_at=row.created_at,
            completed_at=row.completed_at,
        )
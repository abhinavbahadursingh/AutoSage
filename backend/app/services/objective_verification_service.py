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
    DecisionRecord,
    SessionDataset,
    SessionStateResponse,
    StageUpdate,
    VerificationReport,
)

logger = logging.getLogger("autosage.objective_verification")

#: Marker written into the session experiment's config so these experiments
#: are identifiable (and filterable) outside this module.
VERIFICATION_SESSION_MARKER = "objective_verification_session"


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
        return row

    # -- scoped fact loading -----------------------------------------------
    async def _count(self, model: Any, experiment_id: Any) -> int:
        stmt = select(func.count()).select_from(model).where(
            model.experiment_id == experiment_id
        )
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    async def load_facts(self, session: VerificationSession) -> Dict[str, Any]:
        """Collect every fact the checks may reference, for this session only.

        Every query is keyed on ``session.experiment_id``. There is no path in
        this method that can reach another experiment.
        """
        experiment = await self.session.get(Experiment, session.experiment_id)
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
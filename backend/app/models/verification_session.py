"""Fresh Verification Session SQLAlchemy Model.

One row per execution of the Fresh Experiment Objective Verification flow. A
session is created from scratch on every submission: it owns its own
``Experiment`` row, so every recorded fact an objective check can read
(agent executions, decisions, evidence nodes, artifacts, verifications,
experience memory) is scoped to that execution alone.

Nothing is ever read from a previous session. The row therefore also carries
the verbatim user input the session was created from, which is what the
verifier inspects when a fact is absent.

Fields
------
``id``            the run id handed to the client immediately on POST.
``owner_id``      enforced on every read; a foreign run is a 404, not a 403.
``experiment_id`` the isolated experiment this session created.
``events``        the SSE frame history, appended as the run progresses, so a
                  reconnecting or late-subscribing client replays instead of
                  restarting and the stream works across worker processes.
``report``        the final objective-wise report, written once at the end.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class SessionStatus(str, enum.Enum):
    """Lifecycle of one fresh verification session."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VerificationSession(Base):
    __tablename__ = "verification_sessions"
    __table_args__ = (
        Index("ix_verification_sessions_owner_created", "owner_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    experiment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Optional pipeline experiment whose recorded facts (decisions, evidence
    #: nodes, metrics, verification status) this session's objective checks
    #: will inspect instead of this session's own (empty) experiment.
    linked_experiment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # -- the verbatim input this session was created from -------------------
    problem_statement = Column(Text, nullable=False)
    dataset_name = Column(String(255), nullable=False)
    #: target_column / task_type / primary_metric, echoed for traceability.
    config = Column(JSONB, nullable=False, default=dict)

    # -- run lifecycle ------------------------------------------------------
    status = Column(
        String(20), nullable=False, default=SessionStatus.PENDING.value, index=True
    )
    #: Ordered SSE frames emitted so far (see module docstring).
    events = Column(JSONB, nullable=False, default=list)
    #: Final objective-wise report, or None until the run finishes.
    report = Column(JSONB, nullable=True)
    #: Files produced by code generation, for the editable sandbox.
    generated_files = Column(JSONB, nullable=False, default=list)
    #: Read-only activity log of code-generation events.
    activity_log = Column(JSONB, nullable=False, default=list)
    #: Structured decisions produced with the code (algorithm, hyperparameters,
    #: metrics, validation strategy, assumptions, alternatives — each with its
    #: rationale/confidence/source only when the model actually produced one).
    #: Design-time records only: nothing here was trained or executed.
    decision_records = Column(JSONB, nullable=False, default=list)
    #: The design summary the decisions belong to (algorithm, metrics, ...).
    design_record = Column(JSONB, nullable=False, default=dict)
    code_generation_status = Column(String(40), nullable=True)
    code_generation_message = Column(Text, nullable=True)
    #: Overall verdict, denormalised for cheap listing.
    overall_status = Column(String(20), nullable=True)
    overall_confidence = Column(Float, nullable=True)
    error = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    experiment = relationship("Experiment", lazy="selectin", foreign_keys=[experiment_id])
    workspace = relationship("Workspace", lazy="selectin")
    owner = relationship("User", lazy="selectin")

    @property
    def running(self) -> bool:
        return self.status in (SessionStatus.PENDING.value, SessionStatus.RUNNING.value)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<VerificationSession id={self.id} status={self.status!r} "
            f"experiment_id={self.experiment_id}>"
        )
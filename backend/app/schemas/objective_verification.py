"""Fresh Experiment Objective Verification — wire schemas.

Vocabulary
----------
Checks are one of ``PASS`` / ``FAIL`` / ``NOT_VERIFIED`` / ``BLOCKED``:

``PASS``          the condition was evaluated against real evidence and held.
``FAIL``          the condition was evaluated and did not hold.
``NOT_VERIFIED``  the condition could not be evaluated because the evidence it
                  needs does not exist. Deliberately *not* a pass: a fresh
                  session that never trained has no metrics, no decisions and
                  no artifacts, and those checks must say so.
``BLOCKED``       a prerequisite stage failed, so the check was never attempted.

Stages are one of ``PENDING`` / ``RUNNING`` / ``PASSED`` / ``FAILED`` /
``BLOCKED`` and always run in the fixed order declared by
:mod:`app.engine.objective_verification.runner`. Nothing — not an LLM, not an
agent — chooses that order.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CheckStatus(str, enum.Enum):
    """Terminal state of one deterministic check."""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_VERIFIED = "NOT_VERIFIED"
    BLOCKED = "BLOCKED"


class StageStatus(str, enum.Enum):
    """Lifecycle of one verification stage."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    #: Every check ran but none had the evidence they needed. Distinct from
    #: BLOCKED (never attempted) and from PASSED.
    NOT_VERIFIED = "NOT_VERIFIED"
    BLOCKED = "BLOCKED"


class ObjectiveId(str, enum.Enum):
    """The four canonical objectives, in fixed verification order."""

    OBJECTIVE_1 = "objective_1"
    OBJECTIVE_2 = "objective_2"
    OBJECTIVE_3 = "objective_3"
    OBJECTIVE_4 = "objective_4"


# ---------------------------------------------------------------------------
# Static graph definition (served before any session exists)
# ---------------------------------------------------------------------------

class CheckDefinition(BaseModel):
    """Static description of a check, served before any run starts."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    #: What the check asserts, in the objective's own terms.
    description: str
    #: What must be true for this check to PASS.
    expected: str
    #: What record/artifact backs the verdict when it does.
    evidence_source: str


class ObjectiveDefinition(BaseModel):
    """One canonical objective plus the checks it owns."""

    model_config = ConfigDict(from_attributes=True)

    id: ObjectiveId
    number: int
    title: str
    statement: str
    checks: List[CheckDefinition]


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class DecisionRecord(BaseModel):
    """One design decision produced during code generation.

    Every field except ``category``/``decision`` is optional and is only
    present when the generating model actually produced it — a missing
    rationale or confidence is rendered as absent, never as a default that
    would look like an answer.
    """

    model_config = ConfigDict(extra="ignore")

    #: algorithm | hyperparameter | metric | validation | preprocessing |
    #: architecture | data | evaluation.
    category: str = "architecture"
    decision: str
    rationale: Optional[str] = None
    confidence: Optional[float] = None
    source: Optional[str] = None
    alternatives: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)


class DesignRecord(BaseModel):
    """The structured decision record for one generated pipeline."""

    model_config = ConfigDict(extra="ignore")

    algorithm: Optional[str] = None
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    validation_strategy: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    alternatives: List[str] = Field(default_factory=list)
    decisions: List[DecisionRecord] = Field(default_factory=list)


class CheckResult(BaseModel):
    """Outcome of one executed check."""

    model_config = ConfigDict(from_attributes=True)

    check_id: str
    title: str
    status: CheckStatus
    #: What was actually observed, quoted verbatim.
    evidence: List[str] = Field(default_factory=list)
    #: What the check expected, echoed so the UI can show both sides.
    expected: str = ""
    #: What actually happened, one sentence.
    actual: str = ""
    #: Why the status is what it is.
    reasoning: str = ""
    #: 0..1, derived deterministically from the evidence gathered.
    confidence: float = 0.0
    artifact: str = ""
    checked_at: datetime
    #: How this verdict was established: source-level (source code),
    #: config-level (request inputs), generated-level (products of code
    #: generation, never execution), or runtime-level (requires a real run).
    #: A source/config/generated PASS is not proof of a runtime PASS.
    verification_level: str = "source"
    #: Category of evidence examined: "source" (repository), "probe" (synthetic
    #: in-memory data), "session" (database records), "empirical" (real
    #: training run). Distinguishes what the check actually inspected.
    category: str = "source"


class ObjectiveResult(BaseModel):
    """Aggregate of one objective's checks."""

    model_config = ConfigDict(from_attributes=True)

    id: ObjectiveId
    number: int
    title: str
    statement: str
    status: StageStatus
    confidence: float
    checks: List[CheckResult] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class VerificationReport(BaseModel):
    """The complete objective-wise report for one fresh session."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str
    experiment_id: str
    #: Verbatim problem statement this session was created from.
    problem_statement: str
    dataset_name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    objectives: List[ObjectiveResult] = Field(default_factory=list)
    overall_status: StageStatus = StageStatus.PENDING
    #: What code generation produced (if anything), for the final report.
    code_generation_status: str = "NOT_ATTEMPTED"
    code_generation_message: str = ""
    #: The structured decision record produced with the code (design-time
    #: decisions only — never a claim that anything was trained or verified).
    design: Dict[str, Any] = Field(default_factory=dict)
    #: Individual decisions, for the decision-evidence explorer.
    decisions: List[DecisionRecord] = Field(default_factory=list)
    #: Verification levels present in this run, so consumers know what does
    #: and does not constitute runtime evidence.
    verification_levels: Dict[str, int] = Field(default_factory=dict)
    #: Counts of checks by evidence category (source/probe/session/generated/
    #: empirical) — a source PASS is not proof of a specific generated
    #: decision, and the report says so by keeping them apart.
    evidence_categories: Dict[str, int] = Field(default_factory=dict)
    overall_confidence: float = 0.0
    #: Count of checks by status, so the verdict is auditable at a glance.
    totals: Dict[str, int] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def pass_count(self) -> int:
        return sum(1 for o in self.objectives for c in o.checks if c.status is CheckStatus.PASS)


# ---------------------------------------------------------------------------
# Streamed frames
# ---------------------------------------------------------------------------

class StageUpdate(BaseModel):
    """One streamed progress frame.

    Persisted into ``verification_sessions.events`` as it is emitted, so a late
    or reconnecting client replays the frames it missed instead of restarting.
    """

    model_config = ConfigDict(from_attributes=True)

    run_id: str
    stage: str
    status: StageStatus
    message: str = ""
    #: Populated when a check completes; absent for stage transitions.
    check: Optional[CheckResult] = None
    objective_id: Optional[ObjectiveId] = None
    emitted_at: datetime = Field(default_factory=datetime.utcnow)
    #: Optional payload for stages that produce data, not just status.
    #: For code generation, carries the generated code block(s).
    payload: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Fresh session request / response
# ---------------------------------------------------------------------------

class FreshSessionCreate(BaseModel):
    """Everything one fresh verification execution needs.

    Only ``problem_statement`` is strictly required: the page demonstrates
    code generation + verification from a natural-language ML request, and
    neither a dataset nor a target column is needed to generate and inspect a
    reference pipeline. When a dataset or target is omitted, the generated code
    notes the assumption and configuration-level checks report what would be
    required for a real run.
    """

    model_config = ConfigDict(extra="forbid")

    workspace_id: Optional[uuid.UUID] = None
    problem_statement: str = Field(min_length=8, max_length=4000)
    dataset_name: Optional[str] = Field(default=None, max_length=255)
    task_type: Optional[str] = Field(default=None, max_length=40)
    primary_metric: Optional[str] = Field(default=None, max_length=60)

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type,
            "primary_metric": self.primary_metric,
            "dataset_name": self.dataset_name,
        }


class FreshSessionAccepted(BaseModel):
    """Returned immediately by POST /sessions — never blocks on verification."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str
    experiment_id: str
    status: StageStatus
    stream_url: str


class SessionStateResponse(BaseModel):
    """Current state of a fresh session: status, frames and final report."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str
    experiment_id: str
    linked_experiment_id: Optional[uuid.UUID] = None
    status: str
    problem_statement: str
    dataset_name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    updates: List[StageUpdate] = Field(default_factory=list)
    report: Optional[VerificationReport] = None
    #: Code-generation artifacts, re-read without re-parsing the frame history.
    generated_files: List[Dict[str, str]] = Field(default_factory=list)
    activity_log: List[str] = Field(default_factory=list)
    #: Design summary + the individual decisions behind the generated code.
    design: Dict[str, Any] = Field(default_factory=dict)
    decisions: List[DecisionRecord] = Field(default_factory=list)
    code_generation_status: Optional[str] = None
    code_generation_message: Optional[str] = None
    overall_status: Optional[str] = None
    overall_confidence: Optional[float] = None
    error: Optional[str] = None
    running: bool = False
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SessionSummary(BaseModel):
    """Cheap listing row for one of the caller's verification sessions.

    Discovery only — no frame history or report payload. The heavy per-run
    detail is still read through ``GET /sessions/{run_id}``. The verbatim
    ``problem_statement`` is included so a listing can show *what the caller
    asked* without N detail round trips.
    """

    model_config = ConfigDict(from_attributes=True)

    run_id: str
    experiment_id: str
    linked_experiment_id: Optional[uuid.UUID] = None
    #: What the caller asked, verbatim as submitted.
    problem_statement: str
    dataset_name: str
    config: Dict[str, Any] = Field(default_factory=dict)
    status: str
    overall_status: Optional[str] = None
    overall_confidence: Optional[float] = None
    #: Number of design+code decisions recorded for this run.
    decision_count: int = 0
    #: Number of streamed progress frames persisted so far.
    stage_count: int = 0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class BriefRequest(BaseModel):
    """Section 1 of a project brief — the request exactly as the caller gave it."""

    problem_statement: str
    dataset_name: str
    config: Dict[str, Any] = Field(default_factory=dict)


class BriefUnderstanding(BaseModel):
    """Section 2 — what the system read into the phrase, in plain words."""

    #: One of detection | churn | anomaly | forecasting | estimation |
    #: grouping | ranking | supervised-prediction.
    goal_kind: str
    #: One line: the semantic interpretation of the request.
    headline: str
    #: Plain-language sentences unpacking that interpretation.
    detail: List[str] = Field(default_factory=list)


class BriefFramed(BaseModel):
    """Section 3 — the formal problem statement the analysis framed."""

    statement: str
    problem_type: Optional[str] = None
    target: str
    metric: str
    evaluation: str


class BriefStep(BaseModel):
    """One concrete step the pipeline recorded while understanding the need."""

    step: int
    title: str
    detail: str
    confidence: Optional[float] = None
    #: Which record backs this step ('pipeline decision: data_discovery', ...).
    origin: str


class BriefThinking(BaseModel):
    """Section 5 — the thought process the agents actually recorded."""

    approach: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    alternatives: List[str] = Field(default_factory=list)
    validation_strategy: Optional[str] = None


class BriefOutcome(BaseModel):
    """Section 6 — what the work actually produced, in plain words."""

    available: bool = False
    algorithm: Optional[str] = None
    primary_metric: Optional[str] = None
    primary_score: Optional[float] = None
    baseline_score: Optional[float] = None
    gate_passed: Optional[bool] = None
    gate_summary: Optional[str] = None


class ProjectBrief(BaseModel):
    """A spoken-word walkthrough of ONE given project, built from its records.

    This is deliberately NOT a verification report: the objective checks stay
    on the Objectives page. Every sentence here traces to a stored record
    (the verbatim request, the pipeline's decision rows, the design record or
    the measured result) — nothing is invented.
    """

    model_config = ConfigDict(from_attributes=True)

    run_id: str
    request: BriefRequest
    understanding: BriefUnderstanding
    framed: BriefFramed
    requirements: List[BriefStep] = Field(default_factory=list)
    thinking: BriefThinking
    outcome: BriefOutcome


class SessionDataset(BaseModel):
    """A dataset the caller may submit for a fresh session."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    size_bytes: Optional[int] = None
    dataset_id: Optional[str] = None


class LinkExperimentRequest(BaseModel):
    """Link a completed pipeline experiment to this verification session.

    Objective checks read facts (decisions, evidence nodes, metrics,
    verification status) from the linked experiment instead of this
    session's own empty experiment.
    """

    model_config = ConfigDict(extra="forbid")

    experiment_id: uuid.UUID
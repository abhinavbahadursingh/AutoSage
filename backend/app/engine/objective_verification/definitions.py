"""The four canonical AutoSage objectives and the checks under each.

These are the project's stated objectives, verbatim, and the order is fixed.
It is declared here in source and served by
``GET /objective-verification/objectives`` so the client renders the complete
graph before a session exists and never holds a copy that can drift.

Nothing in this module decides anything at runtime — it is the static graph.
The execution order lives in :mod:`app.engine.objective_verification.runner`
and is likewise fixed; no LLM or agent participates in choosing it.

Three kinds of check appear below:

* **source** — the capability is inspected in the repository's own source, by
  AST parse, never by importing or running it.
* **probe** — a pure helper is called with synthetic in-memory data and the
  result discarded.
* **session** — a fact genuinely recorded for *this* fresh session is read
  back. When the session has no such fact (a fresh session never trains), the
  check is NOT_VERIFIED. It is never PASS.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from app.schemas.objective_verification import (
    CheckDefinition,
    ObjectiveDefinition,
    ObjectiveId,
)


def _check(
    check_id: str,
    title: str,
    description: str,
    expected: str,
    evidence_source: str,
) -> CheckDefinition:
    return CheckDefinition(
        id=check_id,
        title=title,
        description=description,
        expected=expected,
        evidence_source=evidence_source,
    )


# ---------------------------------------------------------------------------
# Objective 1
# ---------------------------------------------------------------------------

OBJ1_CHECKS: Tuple[CheckDefinition, ...] = (
    _check(
        "o1_pipeline_graph",
        "English request drives the full stage chain",
        "The workflow is a declared agent graph covering every stage needed "
        "to turn a request into a pipeline, from orchestration to verification.",
        "app/agents/graph.py declares the complete orchestrator -> discovery "
        "-> profiler -> preprocessor -> model_selector -> ml_experiment -> "
        "verification chain.",
        "app/agents/graph.py",
    ),
    _check(
        "o1_dataset_tools",
        "The system can find or ask for the dataset",
        "Dataset discovery is a capability agents invoke, not a hard-coded "
        "filename: search, download and validate tools are registered.",
        "app/engine/tools/builtins.py registers a search, a download and a "
        "validate dataset tool in BUILTIN_TOOLS.",
        "app/engine/tools/builtins.py",
    ),
    _check(
        "o1_dataset_driven_target",
        "The target column comes from the dataset's own schema",
        "Target resolution is driven by the schema and refuses a column the "
        "file does not contain, rather than trusting the request.",
        "resolve_and_validate() matches a real column across casing "
        "differences and refuses a fabricated column.",
        "app/engine/targeting.py",
    ),
    _check(
        "o1_input_captured",
        "The fresh request and dataset are recorded on the session",
        "The verification is anchored to exactly what the user asked for, so "
        "every later verdict is about this request and this dataset.",
        "The session stores a non-empty problem statement, a dataset name, "
        "and the target column / task type / primary metric given.",
        "verification_sessions.problem_statement / dataset_name / config",
    ),
)


# ---------------------------------------------------------------------------
# Objective 2
# ---------------------------------------------------------------------------

OBJ2_CHECKS: Tuple[CheckDefinition, ...] = (
    _check(
        "o2_specialist_agents",
        "Separate agents study the data, clean it, and pick the model",
        "Data study, cleaning and model choice are distinct specialists, not "
        "one prompt doing everything.",
        "app/agents/ contains separate discovery, profiler, preprocessor and "
        "model_selector modules.",
        "app/agents/{discovery,profiler,preprocessor,model_selector}.py",
    ),
    _check(
        "o2_tool_registry",
        "Agents resolve capabilities through a tool registry",
        "Capabilities are registered and resolvable rather than hard-coded "
        "into an agent body.",
        "app/engine/tools/builtins.py declares a non-empty BUILTIN_TOOLS list "
        "resolvable by agents at runtime.",
        "app/engine/tools/builtins.py",
    ),
    _check(
        "o2_sandbox_isolation",
        "The agents' code runs sandboxed and bounded",
        "Generated code executes with no network, a read-only root and hard "
        "CPU/memory limits.",
        "The sandbox run configuration sets network_mode=\"none\", read_only, "
        "cpu_count and mem_limit.",
        "app/engine/sandbox/manager.py",
    ),
    _check(
        "o2_specialist_executions",
        "This session actually ran the specialist agents",
        "Each specialist is recorded as an execution against this session, so "
        "its work is inspectable rather than narrated.",
        "agent_executions rows exist for this session naming the specialist "
        "agents.",
        "agent_executions",
    ),
)


# ---------------------------------------------------------------------------
# Objective 3
# ---------------------------------------------------------------------------

OBJ3_CHECKS: Tuple[CheckDefinition, ...] = (
    _check(
        "o3_ast_security",
        "The executed script contains no dangerous operations",
        "The code the system chose to run is checked for dynamic execution, "
        "disallowed imports and process spawning before it is trusted.",
        "The AST/security gate passes for the script this session executed.",
        "app/engine/verification/gate_checks.py",
    ),
    _check(
        "o3_data_leakage",
        "The evaluation does not leak the target",
        "Splits happen before fitting and the target stays out of the feature "
        "matrix, so a high score means something.",
        "The data-leakage gate passes for the script this session executed.",
        "app/engine/verification/gate_checks.py",
    ),
    _check(
        "o3_metric_sanity",
        "The reported numbers are plausible for the task",
        "A score is checked against the range a task type can legitimately "
        "produce before it is believed.",
        "Every reported metric falls inside the plausible range for the "
        "session's task type.",
        "experiment.result_summary.metrics",
    ),
    _check(
        "o3_baseline_dominance",
        "The result is better than doing nothing clever",
        "The measured score must beat the measured baseline on the metric the "
        "request actually asked for.",
        "The primary score exceeds the baseline score on the session's "
        "primary metric.",
        "experiment.result_summary.baseline",
    ),
    _check(
        "o3_evidence_sources",
        "Decisions are checked against independent sources, not just internal notes",
        "Evidence can come from outside the system, so a decision is not "
        "vindicated only by the agent that made it.",
        "At least one registered evidence source is an external/knowledge "
        "source (paper, web, literature) rather than internal or mock.",
        "app/engine/evidence/source.py registry",
    ),
    _check(
        "o3_independent_agreement",
        "An independent pass agrees with the claims",
        "Claims are resolved against their evidence by a separate pass and "
        "the verdict recorded, so a doubtful claim is replaced rather than "
        "shipped.",
        "A verification record for this session carries a non-abstaining "
        "overall status (VERIFIED, not ABSTAIN).",
        "verifications",
    ),
)


# ---------------------------------------------------------------------------
# Objective 4
# ---------------------------------------------------------------------------

OBJ4_CHECKS: Tuple[CheckDefinition, ...] = (
    _check(
        "o4_decision_rationale",
        "Every decision records why it was made",
        "Each architectural choice carries a reason a user can read, so the "
        "result is auditable rather than a black box.",
        "Every Decision row for this session has a non-empty rationale.",
        "decisions.rationale",
    ),
    _check(
        "o4_decision_confidence",
        "Every decision records how confident it was",
        "Each choice carries a confidence score, so a shaky decision is "
        "visible as shaky instead of equally trusted.",
        "Every Decision row for this session has a confidence score in 0..1.",
        "decisions.confidence",
    ),
    _check(
        "o4_evidence_nodes",
        "Every claim has supporting evidence",
        "Decisions link to evidence-trail nodes, so each claim can be traced "
        "to what backs it.",
        "Evidence-trail nodes exist for this session's runs, one per recorded "
        "decision.",
        "evidence_trail_nodes",
    ),
    _check(
        "o4_experience_memory",
        "The system learns from what worked",
        "A verified outcome is written to memory so the next session reuses a "
        "proven approach instead of folklore.",
        "Experience-memory rows exist for this session with a recorded type.",
        "experience_memories",
    ),
    _check(
        "o4_audit_chain",
        "The whole chain is walkable end to end",
        "Session -> agent -> decision -> evidence -> result is traversable, so "
        "the verdict can be re-checked by someone else.",
        "Every link in the chain is present for this session: agent "
        "execution, decision, evidence, and a result or verification.",
        "cross-table lineage",
    ),
)


OBJECTIVES: Tuple[ObjectiveDefinition, ...] = (
    ObjectiveDefinition(
        id=ObjectiveId.OBJECTIVE_1,
        number=1,
        title="English Request to Complete Pipeline",
        statement=(
            "To build a system that turns a simple English request, like "
            '"predict house prices," into a complete machine learning '
            "pipeline, including finding or asking for the dataset."
        ),
        checks=list(OBJ1_CHECKS),
    ),
    ObjectiveDefinition(
        id=ObjectiveId.OBJECTIVE_2,
        number=2,
        title="Separate Specialist Agents",
        statement=(
            "To create separate agents that study the data, clean it, and "
            "choose the best model for the task."
        ),
        checks=list(OBJ2_CHECKS),
    ),
    ObjectiveDefinition(
        id=ObjectiveId.OBJECTIVE_3,
        number=3,
        title="Every Decision Checked, Doubtful Choices Replaced",
        statement=(
            "To check every important decision using research papers, tests "
            "on real data, and agreement between independent AI models, and "
            "to replace doubtful choices with safe options."
        ),
        checks=list(OBJ3_CHECKS),
    ),
    ObjectiveDefinition(
        id=ObjectiveId.OBJECTIVE_4,
        number=4,
        title="Every Decision Recorded with Reason and Confidence",
        statement=(
            "To record every decision with its reason and a confidence score, "
            "so users can trust the result, and to help the system learn from "
            "past work over time."
        ),
        checks=list(OBJ4_CHECKS),
    ),
)


OBJECTIVES_BY_ID: Dict[ObjectiveId, ObjectiveDefinition] = {
    objective.id: objective for objective in OBJECTIVES
}


def objective_definitions() -> List[ObjectiveDefinition]:
    """All four canonical objectives, in fixed verification order."""
    return list(OBJECTIVES)
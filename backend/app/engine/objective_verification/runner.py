"""The fixed verification flow.

Stages run in this order, one at a time, and the order is declared here in
source::

    input -> objective_1 -> objective_2 -> objective_3 -> objective_4 -> report

Nothing at runtime chooses it. No LLM, no agent, no request payload: the tuple
below *is* the schedule, and a stage only starts after the previous one has
reached a terminal state.

``input`` is the session-intake gate. If the freshly submitted request is not a
well-formed verification input, it FAILS and all four objectives are emitted
as BLOCKED — the flow reports that it could not verify anything, rather than
producing a partial green report that looks like a result.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence

from app.engine.codegen.generator import generate_async as codegen_generate
from app.engine.objective_verification import checks as C
from app.engine.objective_verification.definitions import OBJECTIVES_BY_ID
from app.schemas.objective_verification import (
    CheckResult,
    ObjectiveId,
    ObjectiveResult,
    StageStatus,
    StageUpdate,
    VerificationReport,
)

logger = logging.getLogger("autosage.objective_verification")

#: The progress sink is async because each frame is persisted as it is
#: emitted, so a live SSE client observes stages while the run is still going.
ProgressCallback = Callable[[StageUpdate], Awaitable[None]]

STAGE_INPUT = "input"
STAGE_CODE_GEN = "code_generation"
STAGE_OBJECTIVE_1 = "objective_1"
STAGE_OBJECTIVE_2 = "objective_2"
STAGE_OBJECTIVE_3 = "objective_3"
STAGE_OBJECTIVE_4 = "objective_4"
STAGE_REPORT = "report"

#: The schedule. Order is fixed and is what the client renders up front.
#: input → code_generation → objective_1 → objective_2 → objective_3 → objective_4 → report
ALL_STAGES: Sequence[str] = (
    STAGE_INPUT,
    STAGE_CODE_GEN,
    STAGE_OBJECTIVE_1,
    STAGE_OBJECTIVE_2,
    STAGE_OBJECTIVE_3,
    STAGE_OBJECTIVE_4,
    STAGE_REPORT,
)

#: Which stage runs which objective.
_OBJECTIVE_STAGES = (
    (ObjectiveId.OBJECTIVE_1, STAGE_OBJECTIVE_1),
    (ObjectiveId.OBJECTIVE_2, STAGE_OBJECTIVE_2),
    (ObjectiveId.OBJECTIVE_3, STAGE_OBJECTIVE_3),
    (ObjectiveId.OBJECTIVE_4, STAGE_OBJECTIVE_4),
)

#: The per-objective check runner, in schedule order.
_OBJECTIVE_RUNNERS = (
    C.run_objective_1_checks,
    C.run_objective_2_checks,
    C.run_objective_3_checks,
    C.run_objective_4_checks,
)


async def _emit(
    run_id: str,
    stage: str,
    status: StageStatus,
    message: str,
    *,
    objective_id: Optional[ObjectiveId] = None,
    check: Optional[CheckResult] = None,
    payload: Optional[Dict[str, Any]] = None,
    callback: Optional[ProgressCallback] = None,
) -> None:
    """Emit one frame. A broken progress sink must never fail a run."""
    if callback is None:
        return
    try:
        await callback(
            StageUpdate(
                run_id=run_id,
                stage=stage,
                status=status,
                message=message,
                check=check,
                objective_id=objective_id,
                payload=payload or {},
            )
        )
    except Exception:  # noqa: BLE001
        logger.warning("objective_verification_progress_sink_failed", exc_info=True)


def _input_gate(facts: Mapping[str, Any]) -> List[str]:
    """Problems that make the freshly submitted request unverifiable.

    Returns an empty list when the session is a well-formed verification input.
    Only a blank problem statement causes rejection; dataset and target column
    are optional — the code generation step will note any assumptions.
    """
    problems: List[str] = []
    problem = str(facts.get("problem_statement") or "").strip()

    if len(problem) < 8:
        problems.append("the problem statement is empty or too short to verify")
    return problems


async def run_verification(
    *,
    run_id: str,
    experiment_id: str,
    facts: Mapping[str, Any],
    progress: Optional[ProgressCallback] = None,
) -> VerificationReport:
    """Run the fixed flow and build the report.

    ``facts`` is everything the checks may read, already scoped to this one
    fresh session. This function inspects; it never trains.
    """
    started = datetime.utcnow()
    problem_statement = str(facts.get("problem_statement") or "")
    dataset_name = str(facts.get("dataset_name") or "")

    # ── stage: input ────────────────────────────────────────────────────
    await _emit(
        run_id,
        STAGE_INPUT,
        StageStatus.RUNNING,
        "Checking the freshly submitted problem and dataset",
        callback=progress,
    )
    problems = _input_gate(facts)
    if problems:
        for problem in problems:
            await _emit(
                run_id,
                STAGE_INPUT,
                StageStatus.RUNNING,
                f"  input problem: {problem}",
                callback=progress,
            )
        await _emit(
            run_id,
            STAGE_INPUT,
            StageStatus.FAILED,
            f"Session input is not verifiable: {'; '.join(problems)}",
            callback=progress,
        )
        return await _blocked_report(
            run_id=run_id,
            experiment_id=experiment_id,
            facts=facts,
            problem_statement=problem_statement,
            dataset_name=dataset_name,
            started=started,
            reason="; ".join(problems),
            progress=progress,
        )
    await _emit(
        run_id,
        STAGE_INPUT,
        StageStatus.PASSED,
        f"Session input accepted: {dataset_name}",
        callback=progress,
    )

    # ── stage: code generation ────────────────────────────────────────
    # Generate task-specific code from the problem statement.
    # This is code generation, never execution: no training, no sandbox run,
    # no preprocessing. Output files are persisted and read-only.
    # Tell the client the stage started before the (real, potentially slow)
    # LLM round trip, so the stream shows progress rather than silence.
    await _emit(
        run_id,
        STAGE_CODE_GEN,
        StageStatus.RUNNING,
        "Generating pipeline code with the configured LLM provider",
        objective_id=None,
        callback=progress,
    )

    codegen_problem = str(facts.get("problem_statement") or "")
    codegen_dataset = str(facts.get("dataset_name") or "")
    codegen_result = await codegen_generate(codegen_problem, codegen_dataset)
    codegen_status = codegen_result.status
    codegen_message = codegen_result.message

    # Persist generated files + activity into session config so checks can read them.
    generated_files_payload = [f.to_dict() for f in codegen_result.files]
    design_payload = codegen_result.design_dict
    decisions_payload = codegen_result.decisions

    facts_copy = dict(facts)
    facts_copy["config"]["generated_files"] = json.dumps(generated_files_payload)
    facts_copy["config"]["code_generation_status"] = codegen_status
    facts_copy["config"]["code_generation_message"] = codegen_message
    facts_copy["config"]["design"] = design_payload
    facts_copy["config"]["decisions"] = decisions_payload

    await _emit(
        run_id,
        STAGE_CODE_GEN,
        StageStatus.PASSED if codegen_status == "OK" else StageStatus.FAILED,
        codegen_message or ("Code generation " + codegen_status),
        objective_id=None,
        payload={
            "generated_files": generated_files_payload,
            "status": codegen_status,
            "message": codegen_message,
            "activity": codegen_result.activity,
            "design": design_payload,
            "decisions": decisions_payload,
            "model": codegen_result.model,
            "provider": codegen_result.provider,
        },
        callback=progress,
    )
    if codegen_status != "OK":
        # If code generation failed, all subsequent objectives are BLOCKED.
        # Emit blocked report similar to _blocked_report but with code-gen reason.
        await _emit(
            run_id,
            STAGE_CODE_GEN,
            StageStatus.BLOCKED,
            f"Code generation failed: {codegen_message}",
            objective_id=None,
            callback=progress,
        )
        return await _blocked_report(
            run_id=run_id,
            experiment_id=experiment_id,
            facts=facts,
            problem_statement=problem_statement,
            dataset_name=dataset_name,
            started=started,
            reason="Code generation failed: " + codegen_message,
            progress=progress,
        )

    # Update facts with the generated code so downstream checks may reference it.
    facts = facts_copy

    # ── stages: the four objectives, strictly in order ──────────────────
    results: List[ObjectiveResult] = []
    for (objective_id, stage), runner in zip(_OBJECTIVE_STAGES, _OBJECTIVE_RUNNERS):
        definition = OBJECTIVES_BY_ID[objective_id]
        await _emit(
            run_id,
            stage,
            StageStatus.RUNNING,
            f"Verifying Objective {definition.number}: {definition.title}",
            objective_id=objective_id,
            callback=progress,
        )

        objective_started = datetime.utcnow()
        checks: List[CheckResult] = runner(facts)
        for check in checks:
            await _emit(
                run_id,
                stage,
                StageStatus.RUNNING,
                f"  {check.title} … {check.status.value}",
                objective_id=objective_id,
                check=check,
                callback=progress,
            )

        result = ObjectiveResult(
            id=objective_id,
            number=definition.number,
            title=definition.title,
            statement=definition.statement,
            status=C.roll_up(checks),
            confidence=C.average_confidence(checks),
            checks=checks,
            started_at=objective_started,
            completed_at=datetime.utcnow(),
        )
        results.append(result)
        await _emit(
            run_id,
            stage,
            result.status,
            f"Objective {definition.number} ({definition.title}): {result.status.value}",
            objective_id=objective_id,
            callback=progress,
        )

    # ── stage: report ───────────────────────────────────────────────────
    all_checks = [c for o in results for c in o.checks]
    overall = C.roll_up(all_checks)
    report = VerificationReport(
        run_id=run_id,
        experiment_id=experiment_id,
        problem_statement=problem_statement,
        dataset_name=dataset_name,
        config=dict(facts.get("config") or {}),
        objectives=results,
        overall_status=overall,
        overall_confidence=C.average_confidence(all_checks),
        totals=C.count_by_status(all_checks),
        evidence_categories=C.count_by_category(all_checks),
        verification_levels=C.count_by_level(all_checks),
        code_generation_status=str(facts.get("config", {}).get("code_generation_status") or "NOT_ATTEMPTED"),
        code_generation_message=str(facts.get("config", {}).get("code_generation_message") or ""),
        design=dict(facts.get("config", {}).get("design") or {}),
        decisions=list(facts.get("config", {}).get("decisions") or []),
        started_at=started,
        completed_at=datetime.utcnow(),
    )
    # The report stage reports whether the *report* was produced, not the
    # verdict it carries. A run that completed and returned a verdict is
    # PASSED even when that verdict is FAILED or NOT_VERIFIED — conflating
    # them would make "finished, nothing verified" look like "never
    # finished", and would colour the stage in the verdict's colour.
    await _emit(
        run_id,
        STAGE_REPORT,
        StageStatus.PASSED,
        f"Verification complete — final verdict: {overall.value}",
        callback=progress,
    )
    return report


async def _blocked_report(
    *,
    run_id: str,
    experiment_id: str,
    facts: Mapping[str, Any],
    problem_statement: str,
    dataset_name: str,
    started: datetime,
    reason: str,
    progress: Optional[ProgressCallback],
) -> VerificationReport:
    """Every objective BLOCKED because session intake failed.

    The report still names all four objectives and still lists every one of
    their checks — as BLOCKED, with the reason. The page can therefore show
    the full fixed sequence and what was needed, instead of an empty verdict.
    """
    results: List[ObjectiveResult] = []
    for objective_id, stage in _OBJECTIVE_STAGES:
        definition = OBJECTIVES_BY_ID[objective_id]
        blocked_checks = [
            C.blocked(c.id, c.title, c.expected, f"session input was rejected: {reason}")
            for c in definition.checks
        ]
        results.append(
            ObjectiveResult(
                id=objective_id,
                number=definition.number,
                title=definition.title,
                statement=definition.statement,
                status=StageStatus.BLOCKED,
                confidence=0.0,
                checks=blocked_checks,
                started_at=started,
                completed_at=datetime.utcnow(),
            )
        )
        await _emit(
            run_id,
            stage,
            StageStatus.BLOCKED,
            f"Objective {definition.number} blocked: session input was rejected",
            objective_id=objective_id,
            callback=progress,
        )

    all_checks = [c for o in results for c in o.checks]
    report = VerificationReport(
        run_id=run_id,
        experiment_id=experiment_id,
        problem_statement=problem_statement,
        dataset_name=dataset_name,
        config=dict(facts.get("config") or {}),
        objectives=results,
        overall_status=StageStatus.BLOCKED,
        overall_confidence=0.0,
        totals=C.count_by_status(all_checks),
        evidence_categories=C.count_by_category(all_checks),
        verification_levels=C.count_by_level(all_checks),
        started_at=started,
        completed_at=datetime.utcnow(),
    )
    await _emit(
        run_id,
        STAGE_REPORT,
        StageStatus.BLOCKED,
        "Final verdict: BLOCKED — the session input was never verifiable",
        callback=progress,
    )
    return report
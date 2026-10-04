"""Static gate checks backing the empirical verification gate.

Every run is checked on four axes before a result can be marked verified:

``ast_security``       the code that executed contains no dynamic execution,
                       no disallowed imports and no process-spawning helpers.
``data_leakage``       the training script splits before it fits and keeps the
                       target out of the feature matrix.
``metric_sanity``      reported metrics are within plausible ranges.
``baseline_dominance`` the measured score beats the measured baseline on the
                       requested metric.

Both gate paths use this module: the in-workflow ``VerificationAgent``
(:mod:`app.agents.verifier`) and the API gate
(:func:`app.services.verification_service.VerificationService.verify_experiment`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.engine.metrics import is_higher_is_better
from app.engine.verification.ast_checker import ASTSecurityChecker
from app.engine.verification.leakage_detector import LeakageDetector
from app.engine.verification.metric_validator import MetricValidator

CHECK_AST_SECURITY = "ast_security"
CHECK_DATA_LEAKAGE = "data_leakage"
CHECK_METRIC_SANITY = "metric_sanity"
CHECK_BASELINE_DOMINANCE = "baseline_dominance"

ALL_CHECKS = (
    CHECK_AST_SECURITY,
    CHECK_DATA_LEAKAGE,
    CHECK_METRIC_SANITY,
    CHECK_BASELINE_DOMINANCE,
)

# Minimum margin over the measured baseline for the gate to pass.
BASELINE_MARGIN = 0.0

# The first-party sandbox runner needs ``os``/``sys`` for env and file IO
# inside the container; process execution stays banned even then.
RUNNER_IO_MODULES = ("os", "sys")

# Default artifact scanned: the script the sandbox actually executes.
RUNNER_ARTIFACT = "app/engine/sandbox/train_script.py"


def executed_training_script() -> Optional[str]:
    """Source of the training script the sandbox executes for every run."""
    path = Path(__file__).resolve().parents[1] / "sandbox" / "train_script.py"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _result(
    name: str,
    passed: bool,
    details: Iterable[str],
    *,
    skipped: bool = False,
    artifact: str = RUNNER_ARTIFACT,
) -> Dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "skipped": bool(skipped),
        "details": [str(d) for d in details],
        "artifact": artifact,
    }


def run_static_gate_checks(
    *,
    metrics: Optional[Dict[str, Any]] = None,
    task_type: str = "classification",
    primary_metric: Optional[str] = None,
    primary_score: Optional[float] = None,
    baseline_score: Optional[float] = None,
    code: Optional[str] = None,
    code_artifact: str = RUNNER_ARTIFACT,
    include: Iterable[str] = ALL_CHECKS,
) -> List[Dict[str, Any]]:
    """Run the static checks and return one result dict per check.

    ``include`` selects a subset (the workflow gate handles baseline dominance
    itself, with abstention semantics). Checks whose inputs are missing are
    reported with ``skipped: true`` instead of silently passing.
    """
    wanted = set(include)
    results: List[Dict[str, Any]] = []

    if CHECK_AST_SECURITY in wanted:
        source = code if code is not None else executed_training_script()
        if source is None:
            results.append(
                _result(
                    CHECK_AST_SECURITY,
                    False,
                    ["training script unavailable for AST/security scan"],
                    artifact=code_artifact,
                )
            )
        else:
            passed, errors = ASTSecurityChecker.check_security(
                source, allow_io_modules=RUNNER_IO_MODULES
            )
            results.append(
                _result(
                    CHECK_AST_SECURITY,
                    passed,
                    errors
                    or ["no disallowed imports, dynamic execution or process spawns"],
                    artifact=code_artifact,
                )
            )

    if CHECK_DATA_LEAKAGE in wanted:
        source = code if code is not None else executed_training_script()
        if source is None:
            results.append(
                _result(
                    CHECK_DATA_LEAKAGE,
                    False,
                    ["training script unavailable for leakage scan"],
                    artifact=code_artifact,
                )
            )
        else:
            passed, errors = LeakageDetector.detect_leakage(source)
            results.append(
                _result(
                    CHECK_DATA_LEAKAGE,
                    passed,
                    errors or ["split-before-fit order confirmed; target excluded from features"],
                    artifact=code_artifact,
                )
            )

    if CHECK_METRIC_SANITY in wanted:
        metric_map = dict(metrics or {})
        if not metric_map:
            results.append(
                _result(
                    CHECK_METRIC_SANITY,
                    True,
                    ["no measured metrics to sanity-check"],
                    skipped=True,
                    artifact="experiment.result_summary.metrics",
                )
            )
        else:
            passed, errors = MetricValidator.validate_metrics(metric_map, task_type)
            results.append(
                _result(
                    CHECK_METRIC_SANITY,
                    passed,
                    errors or ["all reported metrics within plausible ranges"],
                    artifact="experiment.result_summary.metrics",
                )
            )

    if CHECK_BASELINE_DOMINANCE in wanted:
        metric = str(primary_metric or "")
        if primary_score is None or baseline_score is None or not metric:
            results.append(
                _result(
                    CHECK_BASELINE_DOMINANCE,
                    True,
                    ["no measured score/baseline pair to compare"],
                    skipped=True,
                    artifact="experiment.result_summary.baseline",
                )
            )
        else:
            value = float(primary_score)
            baseline = float(baseline_score)
            higher = is_higher_is_better(metric)
            better = (
                (value - baseline) > BASELINE_MARGIN
                if higher
                else (baseline - value) > BASELINE_MARGIN
            )
            direction = "higher is better" if higher else "lower is better"
            results.append(
                _result(
                    CHECK_BASELINE_DOMINANCE,
                    better,
                    [
                        f"{metric}={value:.6f} vs baseline={baseline:.6f} ({direction})"
                    ],
                    artifact="experiment.result_summary.baseline",
                )
            )

    return results


def failed_checks(results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Checks that ran and did not pass (skipped checks never fail the gate)."""
    return [r for r in results if not r.get("skipped") and not r.get("passed")]

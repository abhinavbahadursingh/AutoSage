"""Verification Agent (Phase 7).

Responsibility: run the empirical verification gate decision over the ML
result (sanity checks / pass-fail). Deep AST/leakage tooling remains in the
verification engine (Phase 9+); this agent owns the gate *decision*.

The gate is anchored to the metric the request asked for
(``state["primary_metric"]``): it validates that the measured result is on that
metric, in range, and above the measured baseline for that same metric. It
never re-interprets the objective as accuracy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, VerificationOutput
from app.agents.state import ExperimentWorkflowState
from app.engine.metrics import is_higher_is_better, score_from_metrics
from app.engine.verification.gate_checks import (
    CHECK_AST_SECURITY,
    CHECK_DATA_LEAKAGE,
    CHECK_METRIC_SANITY,
    run_static_gate_checks,
)

STAGE = "verification"

# Minimum margin over the measured baseline for the gate to pass. Keeps a
# trivial "no better than majority class" result from being verified.
BASELINE_MARGIN = 0.0

_SYSTEM = (
    "You are the AutoSage Verification Agent. "
    "Decide whether the measured result passes the empirical gate for the "
    "requested metric. "
    "Return JSON matching the provided schema."
)


class VerificationAgent(BaseAgent):
    """Decides pass/fail/abstain for the verification gate."""

    stage = STAGE
    output_model = VerificationOutput

    def run(self, state: ExperimentWorkflowState) -> AgentOutput:
        """Decide the gate deterministically.

        Pass/fail/abstain is an arithmetic comparison of the measured score
        against the measured baseline, so a completion model must not be the
        one to render it -- :meth:`heuristic` is the authority here.
        """
        return self.heuristic(state)

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        ml_result = state.get("ml_result") or {}
        profile = state.get("profile") or {}
        attempt = int(state.get("attempt") or 1)
        primary_metric = state.get("primary_metric") or ml_result.get("primary_metric") or "accuracy"
        baseline = ml_result.get("baseline") or {}
        direction = "higher" if is_higher_is_better(primary_metric) else "lower"
        user = (
            "Verify this measured result.\n"
            f"REQUESTED METRIC (the gate must use this one): {primary_metric} "
            f"({direction} is better)\n"
            f"measured {primary_metric}={ml_result.get('primary_score')}\n"
            f"baseline {primary_metric}={baseline.get('score') or score_from_metrics(baseline.get('metrics'), primary_metric)}\n"
            f"selected_model={ml_result.get('selected_model')}\n"
            f"models_evaluated={ml_result.get('models_evaluated')}\n"
            f"model_comparison={ml_result.get('model_comparison')}\n"
            f"all_metrics={ml_result.get('metrics')}\n"
            f"profile={profile}\nattempt={attempt}\n"
            "Judge pass/fail on the requested metric versus the baseline. Do not "
            "evaluate a different metric (accuracy included) as the objective."
        )
        return _SYSTEM, user

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        attempt = int(state.get("attempt") or 1)
        ml_result = state.get("ml_result") or {}
        primary_metric = str(state.get("primary_metric") or ml_result.get("primary_metric") or "accuracy")

        # Audit trail lookup (stub store today; shape is stable for later phases).
        self.call_tool(
            "search_evidence",
            query=str(ml_result.get("notes") or primary_metric),
            run_id=state.get("experiment_id"),
            limit=5,
        )

        failures: List[str] = []
        checks = [
            f"Requested metric preserved ({primary_metric})",
            "Primary metric measured",
            "Primary metric within [0, 1]",
            f"Baseline dominance on {primary_metric}",
        ]
        abstained = False

        reported_metric = str(ml_result.get("primary_metric") or ml_result.get("metric") or "")
        if reported_metric and reported_metric != primary_metric:
            failures.append(
                f"reported metric {reported_metric!r} does not match requested {primary_metric!r}"
            )

        # A run that trained nothing reports value=0.0; only a fitted model
        # (selected_model) means something was actually measured.
        measured = bool(ml_result.get("selected_model"))
        value = ml_result.get("primary_score") if measured else None
        if value is None and measured:
            value = ml_result.get("value")
        baseline = ml_result.get("baseline") or {}
        baseline_score = baseline.get("score") if measured else None
        if baseline_score is None and measured:
            baseline_score = score_from_metrics(baseline.get("metrics"), primary_metric)

        if value is None:
            # Nothing was measured -- abstain rather than invent a verdict.
            abstained = True
            failures.append(f"no measured {primary_metric} to verify")
        else:
            value = float(value)
            if not (0.0 <= value <= 1.0):
                failures.append(f"{primary_metric} out of range: {value}")
            elif baseline_score is not None:
                margin = value - float(baseline_score)
                better = margin > BASELINE_MARGIN if is_higher_is_better(primary_metric) else margin < -BASELINE_MARGIN
                if not better:
                    failures.append(
                        f"{primary_metric}={value:.4f} does not beat baseline "
                        f"{float(baseline_score):.4f}"
                    )

        selected = ml_result.get("selected_model")
        compared = int(ml_result.get("models_evaluated") or 0)
        if state.get("compare_models") and compared < 2:
            failures.append(
                f"compare_models requested but only {compared} model(s) evaluated"
            )
        if selected and ml_result.get("model_comparison"):
            best = max(
                (e.get("score") for e in ml_result["model_comparison"] if e.get("score") is not None),
                default=None,
            )
            chosen = score_from_metrics(ml_result.get("metrics"), primary_metric)
            if best is not None and chosen is not None:
                if is_higher_is_better(primary_metric):
                    if chosen < best - 1e-9:
                        failures.append(
                            f"selected model is not the best {primary_metric} "
                            f"({chosen:.4f} < {best:.4f})"
                        )
                elif chosen > best + 1e-9:
                    failures.append(
                        f"selected model is not the best {primary_metric} "
                        f"({chosen:.4f} > {best:.4f})"
                    )

        # Static gate: the code that ran (AST/security, leakage) and the
        # numbers it reported (metric sanity). Baseline dominance is decided
        # above so abstention stays authoritative; these checks never abstain.
        config = state.get("config") or {}
        profile = state.get("profile") or {}
        static_checks = run_static_gate_checks(
            metrics=dict(ml_result.get("metrics") or {}),
            task_type=str(
                config.get("task_type") or profile.get("task_type") or "classification"
            ),
            primary_metric=primary_metric,
            primary_score=float(value) if value is not None else None,
            baseline_score=(
                float(baseline_score) if baseline_score is not None else None
            ),
            include=(CHECK_AST_SECURITY, CHECK_DATA_LEAKAGE, CHECK_METRIC_SANITY),
        )
        for check in static_checks:
            if check.get("skipped"):
                checks.append(f"{check['name']}: skipped ({'; '.join(check['details'])})")
                continue
            checks.append(f"{check['name']}: {'passed' if check['passed'] else 'failed'}")
            if not check["passed"]:
                failures.append(
                    f"{check['name']} failed: " + "; ".join(check["details"])
                )

        passed = not failures and not abstained
        if abstained:
            summary = (
                f"Abstained: no measured {primary_metric} available to verify "
                f"against the baseline."
            )
        elif passed:
            baseline_text = (
                f" vs baseline {float(baseline_score):.4f}"
                if baseline_score is not None
                else ""
            )
            compared_text = f" after comparing {compared} models" if compared > 1 else ""
            summary = (
                f"Result passes empirical gate: {primary_metric}={float(value):.4f}"
                f"{baseline_text}{compared_text}."
            )
        else:
            summary = (
                f"Result fails empirical gate on {primary_metric}: " + "; ".join(failures)
            )

        return VerificationOutput(
            source="heuristic",
            checks=checks,
            passed=passed,
            abstained=abstained,
            failures=failures,
            summary=summary,
            attempt=attempt,
            static_checks=static_checks,
        )

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, VerificationOutput)
        ml_result = state.get("ml_result") or {}
        primary_metric = str(state.get("primary_metric") or ml_result.get("primary_metric") or "accuracy")
        baseline = dict(ml_result.get("baseline") or {})
        update: Dict[str, Any] = {
            "verification": {
                "checks": list(output.checks),
                "passed": output.passed,
                "abstained": output.abstained,
                "failures": list(output.failures),
                "summary": output.summary,
                "attempt": output.attempt,
                # What the gate actually compared, for the audit trail.
                "primary_metric": primary_metric,
                "primary_score": ml_result.get("primary_score"),
                "baseline_score": baseline.get("score"),
                "selected_model": ml_result.get("selected_model"),
                # Static gate evidence (AST/security, leakage, metric sanity).
                "static_checks": list(output.static_checks),
            },
            "verification_passed": output.passed,
            "verification_abstained": output.abstained,
        }
        if output.passed:
            update["status"] = "COMPLETED"
        return update

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        assert isinstance(output, VerificationOutput)
        primary_metric = str(state.get("primary_metric") or "accuracy")
        if output.passed and not output.abstained:
            return f"verification passed on {primary_metric}"
        if output.abstained:
            return "verification abstained: " + "; ".join(output.failures)
        return "verification failed: " + "; ".join(output.failures)


def verifier_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`VerificationAgent`."""
    return VerificationAgent().node_update(state)

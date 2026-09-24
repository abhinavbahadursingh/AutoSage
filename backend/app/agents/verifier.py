"""Verification Agent (Phase 7).

Responsibility: run the empirical verification gate decision over the ML
result (sanity checks / pass-fail). Deep AST/leakage tooling remains in the
verification engine (Phase 9+); this agent owns the gate *decision*.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, VerificationOutput
from app.agents.state import ExperimentWorkflowState

STAGE = "verification"

_SYSTEM = (
    "You are the AutoSage Verification Agent. "
    "Decide whether the ML result passes the empirical gate "
    "(metric sanity, baseline dominance — placeholders until tooling lands). "
    "Return JSON matching the provided schema."
)


class VerificationAgent(BaseAgent):
    """Decides pass/fail for the verification gate."""

    stage = STAGE
    output_model = VerificationOutput

    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        ml_result = state.get("ml_result") or {}
        profile = state.get("profile") or {}
        attempt = int(state.get("attempt") or 1)
        user = (
            "Verify this result.\n"
            f"ml_result={ml_result}\nprofile={profile}\nattempt={attempt}"
        )
        return _SYSTEM, user

    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        attempt = int(state.get("attempt") or 1)
        ml_result = state.get("ml_result") or {}
        value = ml_result.get("value")
        metric = ml_result.get("metric", "accuracy")

        # Audit trail lookup (stub store today; shape is stable for later phases).
        self.call_tool(
            "search_evidence",
            query=str(ml_result.get("notes") or metric),
            run_id=state.get("experiment_id"),
            limit=5,
        )

        failures = []
        if value is None:
            failures.append("missing metric value")
        elif not (0.0 <= float(value) <= 1.0):
            failures.append(f"{metric} out of range: {value}")
        passed = not failures
        return VerificationOutput(
            source="heuristic",
            checks=["metric_sanity"],
            passed=passed,
            failures=failures,
            summary=(
                "Heuristic gate: metric in [0,1]."
                if passed
                else "Heuristic gate failed: " + "; ".join(failures)
            ),
            attempt=attempt,
        )

    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, VerificationOutput)
        update: Dict[str, Any] = {
            "verification": {
                "checks": list(output.checks),
                "passed": output.passed,
                "failures": list(output.failures),
                "summary": output.summary,
                "attempt": output.attempt,
                "source": output.source,
            },
            "verification_passed": output.passed,
        }
        if output.passed:
            update["status"] = "COMPLETED"
        return update

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        assert isinstance(output, VerificationOutput)
        if output.passed:
            return "verification passed"
        return "verification failed: " + "; ".join(output.failures)


def verifier_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`VerificationAgent`."""
    return VerificationAgent().node_update(state)

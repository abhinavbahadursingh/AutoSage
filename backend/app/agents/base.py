"""Base class + shared helpers for AutoSage specialized agents (Phase 7).

Every agent:

- has one clear responsibility and a typed :class:`ExperimentWorkflowState` input
- returns a structured Pydantic output (:class:`app.agents.schemas.AgentOutput`)
- talks to models only through the provider-independent
  :class:`~app.engine.llm.client.LLMClient` (never provider SDKs)
- is independently constructible/testable (``DiscoveryAgent(llm=FakeLLM())``)
- degrades to a deterministic heuristic when no LLM is available (config flag)

LangGraph node wrappers live beside each agent and convert the structured
output into a ``stage_update`` for the shared workflow state.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel

from app.agents.schemas import AgentOutput
from app.agents.state import ExperimentWorkflowState
from app.core.config import settings
from app.engine.llm.client import LLMClient, get_llm_client, run_coro_sync
from app.engine.llm.types import LLMError, LLMUnavailableError
from app.engine.tools import ToolRegistry, ToolResult, get_default_registry

logger = logging.getLogger("autosage.workflow")

OutputT = TypeVar("OutputT", bound=AgentOutput)


def check_fail_stage(state: ExperimentWorkflowState, stage: str) -> None:
    """Raise when this run is configured to fail at ``stage`` (tests/ops)."""
    if state.get("fail_stage") == stage:
        raise RuntimeError(f"mock failure injected at stage '{stage}'")


def stage_update(
    state: ExperimentWorkflowState,
    stage: str,
    event: str,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a node return value: trail event + completion marker + payload."""
    logger.info(
        "workflow_stage",
        extra={"stage": stage, "experiment": state.get("experiment_id")},
    )
    update: Dict[str, Any] = {
        "current_stage": stage,
        "stages_completed": [stage],
        "events": [event],
    }
    update.update(extra)
    return update


class BaseAgent(ABC):
    """Specialized agent: typed state in -> structured Pydantic output out."""

    #: Graph node / stage name (must match STAGE_ORDER entries for pipeline stages).
    stage: str = "agent"
    #: Structured output schema returned by :meth:`run`.
    output_model: Type[AgentOutput]

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        tools: Optional[ToolRegistry] = None,
    ) -> None:
        # None => resolve the process-wide client/registry at call time (DI-friendly).
        self._llm = llm
        self._tools = tools
        self._tool_calls: List[Dict[str, Any]] = []

    # -- tool system (Phase 9) ---------------------------------------------------
    def tool_registry(self) -> ToolRegistry:
        """Resolve the registry used for Agent -> Tool -> Result calls."""
        return self._tools if self._tools is not None else get_default_registry()

    def call_tool(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a registered tool and record a compact audit entry."""
        result = self.tool_registry().execute(name, **kwargs)
        self._tool_calls.append(
            {
                "tool": name,
                "stage": self.stage,
                "success": result.success,
                "error_type": result.error_type,
                "duration_ms": result.duration_ms,
            }
        )
        return result

    # -- hooks -----------------------------------------------------------------
    @abstractmethod
    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        """Return ``(system, user)`` prompts for the LLM path."""

    @abstractmethod
    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        """Deterministic fallback when no LLM provider is available."""

    # -- execution --------------------------------------------------------------
    def _client(self) -> LLMClient:
        return self._llm if self._llm is not None else get_llm_client()

    def run(self, state: ExperimentWorkflowState) -> AgentOutput:
        """Execute the agent: LLM first, heuristic fallback when allowed."""
        from app.core.observability import (
            TimingContext,
            agent_execution_context,
            get_agent_execution_id,
            log_with_context,
            trace_operation,
        )
        
        experiment_id = state.get("experiment_id")
        with agent_execution_context() as agent_exec_id:
            client = self._client()
            use_llm = True
            if not client.has_providers():
                if not settings.LLM_ALLOW_HEURISTIC_FALLBACK:
                    raise LLMUnavailableError(
                        f"{self.stage}: no LLM providers configured and heuristic fallback disabled"
                    )
                use_llm = False

            if use_llm:
                try:
                    system, user = self.build_prompts(state)
                    with TimingContext(
                        "agent_llm_call",
                        extra_fields={
                            "agent": self.stage,
                            "experiment": experiment_id,
                            "agent_execution": agent_exec_id,
                        },
                    ):
                        with trace_operation(
                            f"agent.{self.stage}",
                            attributes={
                                "stage": self.stage,
                                "experiment_id": experiment_id or "",
                                "agent_execution_id": agent_exec_id,
                            },
                        ):
                            output = client.complete_structured_sync(
                                system=system,
                                user=user,
                                response_model=self.output_model,
                                model_tier=self.model_tier(),
                            )
                    log_with_context(
                        logger, logging.INFO, "agent_llm_ok",
                        agent=self.stage, experiment=experiment_id,
                        agent_execution=agent_exec_id
                    )
                    return output
                except LLMError as exc:
                    if not settings.LLM_ALLOW_HEURISTIC_FALLBACK:
                        raise
                    log_with_context(
                        logger, logging.WARNING, "agent_llm_fallback",
                        agent=self.stage, error=str(exc),
                        experiment=experiment_id, agent_execution=agent_exec_id
                    )

            output = self.heuristic(state)
            if not output.source or output.source == "llm":
                output.source = "heuristic"
            return output

    def model_tier(self) -> str:
        """Model tier for this agent (override for reasoning-heavy stages)."""
        return "fast"

    # -- node helper ------------------------------------------------------------
    def node_update(self, state: ExperimentWorkflowState) -> Dict[str, Any]:
        """Run the agent and wrap the structured output as a graph state update.

        Subclasses override :meth:`state_payload` to map the output onto the
        Phase 6 state slots (``dataset_info``, ``profile``, ...).
        """
        check_fail_stage(state, self.stage)
        self._tool_calls = []
        try:
            output = self.run(state)
        finally:
            tool_calls = list(self._tool_calls)
            self._tool_calls = []
        payload = self.state_payload(output, state)
        if tool_calls:
            payload["tool_calls"] = tool_calls
        event = self.event_message(output, state)
        return stage_update(state, self.stage, event, **payload)

    @abstractmethod
    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        """Map structured output -> workflow state slots."""

    def event_message(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> str:
        """Human-readable lifecycle event for the trail."""
        return f"{self.stage} completed"


# Convenience re-export for node modules.
__all__ = [
    "BaseAgent",
    "check_fail_stage",
    "stage_update",
]

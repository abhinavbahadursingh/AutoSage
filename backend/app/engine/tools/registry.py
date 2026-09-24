"""Tool registry: registration, discovery, and safe execution (Phase 9).

Single entry point for the Agent -> Tool -> Result flow::

    registry.execute("search_dataset", query="iris")
    -> ToolResult(success=True, data={...}, duration_ms=...)

Execution never raises: validation failures and tool crashes are captured
as structured :class:`ToolResult`s with ``error_type`` set.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.observability import (
    TimingContext,
    get_experiment_id,
    get_agent_execution_id,
    log_with_context,
    trace_operation,
)
from app.engine.tools.base import BaseTool, ToolResult
from app.engine.tools.errors import (
    ToolNotFoundError,
    ToolRegistrationError,
)

logger = logging.getLogger("autosage.tools")


class ToolRegistry:
    """Named collection of tools with validated, non-throwing execution."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    # -- registration -----------------------------------------------------------
    def register(self, tool: BaseTool, *, overwrite: bool = False) -> BaseTool:
        """Register a tool instance; raises on duplicate/invalid names."""
        if not tool.name:
            raise ToolRegistrationError("tool.name must be a non-empty string")
        if tool.name in self._tools and not overwrite:
            raise ToolRegistrationError(f"tool already registered: {tool.name}")
        if not getattr(tool, "input_model", None):
            raise ToolRegistrationError(f"tool {tool.name!r} missing input_model")
        self._tools[tool.name] = tool
        logger.debug("tool_registered", extra={"tool": tool.name})
        return tool

    def unregister(self, name: str) -> bool:
        """Remove a tool; True if it existed."""
        return self._tools.pop(name, None) is not None

    def clear(self) -> None:
        """Drop all registrations (tests / re-init)."""
        self._tools.clear()

    # -- discovery --------------------------------------------------------------
    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> BaseTool:
        """Fetch a tool or raise :class:`ToolNotFoundError`."""
        try:
            return self._tools[name]
        except KeyError:
            raise ToolNotFoundError(f"tool not found: {name}") from None

    def names(self) -> List[str]:
        """Sorted tool names (stable discovery order)."""
        return sorted(self._tools)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Full specs (name, description, input schema) for every tool."""
        return [self._tools[n].spec() for n in self.names()]

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    # -- execution --------------------------------------------------------------
    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Run ``name`` with ``kwargs``; always returns a ToolResult.

        Unknown tools and validation/exec failures become
        ``success=False`` results (``error_type`` distinguishes them).
        """
        experiment_id = get_experiment_id()
        agent_exec_id = get_agent_execution_id()
        try:
            tool = self.get(name)
        except ToolNotFoundError as exc:
            log_with_context(
                logger, logging.WARNING, "tool_not_found",
                tool=name, experiment=experiment_id, agent_execution=agent_exec_id
            )
            return ToolResult(
                success=False,
                tool_name=name,
                error=str(exc),
                error_type="ToolNotFoundError",
            )
        
        with TimingContext(
            "tool_execution",
            extra_fields={
                "tool": name,
                "experiment": experiment_id,
                "agent_execution": agent_exec_id,
            },
        ):
            with trace_operation(
                "tool.execute",
                attributes={
                    "tool": name,
                    "experiment_id": experiment_id or "",
                    "agent_execution_id": agent_exec_id or "",
                },
            ):
                result = tool.execute(**kwargs)
                if result.success:
                    log_with_context(
                        logger, logging.INFO, "tool_ok",
                        tool=name, duration_ms=result.duration_ms,
                        experiment=experiment_id, agent_execution=agent_exec_id
                    )
                else:
                    log_with_context(
                        logger, logging.WARNING, "tool_failed",
                        tool=name, error_type=result.error_type,
                        experiment=experiment_id, agent_execution=agent_exec_id
                    )
                return result


# -- process-wide default registry -----------------------------------------------
_default_registry: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """Return (lazily build) the process-wide registry with builtins."""
    global _default_registry
    if _default_registry is None:
        from app.engine.tools.builtins import register_builtins

        registry = ToolRegistry()
        register_builtins(registry)
        _default_registry = registry
    return _default_registry


def set_default_registry(registry: Optional[ToolRegistry]) -> None:
    """Replace (or clear) the process-wide registry — used by tests/DI."""
    global _default_registry
    _default_registry = registry

"""Tool-layer errors (Phase 9).

Every failure mode has a dedicated type so the registry can classify
errors into structured :class:`~app.engine.tools.base.ToolResult`s
without leaking raw exceptions to agents.
"""
from __future__ import annotations


class ToolError(Exception):
    """Base class for all tool-system failures."""


class ToolRegistrationError(ToolError):
    """Invalid or duplicate tool registration."""


class ToolNotFoundError(ToolError):
    """Requested tool name is not in the registry."""


class ToolValidationError(ToolError):
    """Tool inputs failed Pydantic validation before execution."""


class ToolExecutionError(ToolError):
    """Tool body raised while running (wrapped by the registry)."""

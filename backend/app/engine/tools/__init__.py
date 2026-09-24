"""Modular agent Tool System (Phase 9).

Agent -> ToolRegistry -> BaseTool -> structured ToolResult.
"""
from app.engine.tools.base import BaseTool, ToolResult
from app.engine.tools.builtins import BUILTIN_TOOLS, register_builtins
from app.engine.tools.errors import (
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolRegistrationError,
    ToolValidationError,
)
from app.engine.tools.registry import (
    ToolRegistry,
    get_default_registry,
    set_default_registry,
)

__all__ = [
    "BUILTIN_TOOLS",
    "BaseTool",
    "ToolError",
    "ToolExecutionError",
    "ToolNotFoundError",
    "ToolRegistrationError",
    "ToolRegistry",
    "ToolResult",
    "ToolValidationError",
    "get_default_registry",
    "register_builtins",
    "set_default_registry",
]

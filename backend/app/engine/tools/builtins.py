"""Built-in tool registration (Phase 9/13).

``register_builtins(registry)`` wires the initial tools. Tests can
build a fresh :class:`~app.engine.tools.registry.ToolRegistry` and call
this to get the production set without touching the process-wide default.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Type

from app.engine.tools.base import BaseTool
from app.engine.tools.datasets import (
    DownloadDatasetTool,
    ProfileDatasetTool,
    SearchDatasetTool,
    ValidateDatasetTool,
)
from app.engine.tools.evidence import SearchEvidenceTool
from app.engine.tools.memory import RetrieveMemoryTool, StoreMemoryTool
from app.engine.tools.ml import ExecuteMLJobTool

if TYPE_CHECKING:
    from app.engine.tools.registry import ToolRegistry

#: Canonical tool classes (registration order = definition order).
BUILTIN_TOOLS: List[Type[BaseTool]] = [
    SearchDatasetTool,
    DownloadDatasetTool,
    ValidateDatasetTool,
    ProfileDatasetTool,
    RetrieveMemoryTool,
    StoreMemoryTool,
    SearchEvidenceTool,
    ExecuteMLJobTool,
]


def register_builtins(registry: "ToolRegistry") -> "ToolRegistry":
    """Instantiate and register every built-in tool on ``registry``."""
    for tool_cls in BUILTIN_TOOLS:
        registry.register(tool_cls())
    return registry

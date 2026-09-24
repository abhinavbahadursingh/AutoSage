"""Tool interface + structured results (Phase 9).

Architecture::

    Agent
      -> ToolRegistry.execute(name, **kwargs)
      -> BaseTool (input validation -> run -> structured result)
      -> concrete tool (search_dataset, profile_dataset, ...)

Tools are modular, independently testable, and must not import provider-
specific LLM code. ML sandbox / MLflow / real verification / memory
backends are intentionally out of scope for Phase 9 — those tools return
deterministic stubs with the correct shape.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.engine.tools.errors import ToolExecutionError, ToolValidationError


class ToolResult(BaseModel):
    """Structured, JSON-safe outcome of one tool execution."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    tool_name: str
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    error_type: Optional[str] = None
    duration_ms: float = 0.0


class BaseTool(ABC):
    """Abstract tool: typed input model in, dict payload out."""

    #: Unique registry key (snake_case, e.g. ``search_dataset``).
    name: str = ""
    #: One-line description for discovery / agent prompts.
    description: str = ""
    #: Pydantic model used to validate ``**kwargs`` before :meth:`run`.
    input_model: Type[BaseModel]

    @abstractmethod
    def run(self, params: BaseModel) -> Dict[str, Any]:
        """Execute the tool with validated ``params``; return JSON-safe data."""

    def validate(self, **kwargs: Any) -> BaseModel:
        """Validate raw kwargs against :attr:`input_model`."""
        try:
            return self.input_model.model_validate(kwargs)
        except ValidationError as exc:
            raise ToolValidationError(f"{self.name}: invalid input: {exc}") from exc

    def execute(self, **kwargs: Any) -> ToolResult:
        """Validate + run + wrap into a :class:`ToolResult` (never raises)."""
        start = perf_counter()
        try:
            params = self.validate(**kwargs)
            data = self.run(params)
            if isinstance(data, BaseModel):
                data = data.model_dump()
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise ToolExecutionError(
                    f"{self.name}: run() must return a dict, got {type(data).__name__}"
                )
            return ToolResult(
                success=True,
                tool_name=self.name,
                data=data,
                duration_ms=round((perf_counter() - start) * 1000, 3),
            )
        except ToolValidationError as exc:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=str(exc),
                error_type="ToolValidationError",
                duration_ms=round((perf_counter() - start) * 1000, 3),
            )
        except Exception as exc:  # noqa: BLE001 — registry boundary
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=f"{type(exc).__name__}: {exc}",
                error_type=type(exc).__name__,
                duration_ms=round((perf_counter() - start) * 1000, 3),
            )

    def spec(self) -> Dict[str, Any]:
        """Discovery payload: name, description, JSON schema for inputs."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }

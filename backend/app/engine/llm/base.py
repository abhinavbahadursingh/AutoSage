"""Provider-independent LLM interface (Phase 8).

Architecture::

    Agent
      -> LLM Interface   (LLMClient / BaseLLMProvider)
      -> Provider Adapter (OpenRouter / Groq / HuggingFace)
      -> LLM Provider     (remote HTTP API)

Adapters implement :class:`BaseLLMProvider` and speak only the normalized
:class:`~app.engine.llm.types.LLMRequest` / ``LLMResponse`` contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.engine.llm.types import LLMRequest, LLMResponse


class BaseLLMProvider(ABC):
    """Abstract provider adapter (one remote LLM API)."""

    #: Stable provider id used in fallback order / model prefixes
    #: (e.g. ``"groq"``, ``"openrouter"``, ``"huggingface"``).
    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool:
        """True when this adapter has credentials and can be called."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Run one completion. Raises LLM* errors on failure."""

    async def aclose(self) -> None:
        """Release HTTP resources (no-op by default)."""
        return None

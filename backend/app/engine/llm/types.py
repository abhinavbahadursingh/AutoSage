"""Shared LLM request/response types and errors (Phase 8).

Provider-agnostic contract used by :class:`app.engine.llm.client.LLMClient`
and every provider adapter. Agents only ever see these types — never
provider SDKs or HTTP details.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LLMMessage:
    """One chat message (system / user / assistant)."""

    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMRequest:
    """Normalized completion request handed to a provider adapter."""

    model: str
    messages: List[LLMMessage]
    temperature: float = 0.0
    max_tokens: int = 2048
    timeout: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Normalized completion result."""

    text: str
    model: str
    provider: str
    usage: Dict[str, Any] = field(default_factory=dict)
    raw: Optional[Dict[str, Any]] = None


class LLMError(Exception):
    """Base class for all LLM-layer failures."""


class LLMTimeoutError(LLMError):
    """Provider request exceeded the configured timeout."""


class LLMRateLimitError(LLMError):
    """Provider returned HTTP 429 (rate limited)."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMProviderError(LLMError):
    """Provider returned an error (auth, 5xx, malformed response, ...)."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMUnavailableError(LLMError):
    """Every eligible provider failed (or none are configured)."""


class LLMParseError(LLMError):
    """Structured output could not be parsed/validated as the target schema."""

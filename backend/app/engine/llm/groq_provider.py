"""Groq provider adapter (Phase 8)."""
from __future__ import annotations

from app.core.config import settings
from app.engine.llm._openai_compat import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    """Groq Cloud chat-completions API (fast inference)."""

    name = "groq"

    def __init__(self, api_key: str = "", client=None, timeout=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(
            api_key=api_key if api_key is not None else "",
            base_url=settings.GROQ_BASE_URL,
            client=client,
            timeout=timeout,
        )
        if not api_key:
            self.api_key = settings.GROQ_API_KEY

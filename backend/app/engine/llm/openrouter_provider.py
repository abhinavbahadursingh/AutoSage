"""OpenRouter provider adapter (Phase 8)."""
from __future__ import annotations

from app.core.config import settings
from app.engine.llm._openai_compat import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter multi-model router (OpenAI-compatible API)."""

    name = "openrouter"

    def __init__(self, api_key: str = "", client=None, timeout=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(
            api_key=api_key if api_key is not None else "",
            base_url=settings.OPENROUTER_BASE_URL,
            extra_headers={
                "HTTP-Referer": settings.SUPABASE_URL or "http://localhost:3000",
                "X-Title": "AutoSage",
            },
            client=client,
            timeout=timeout,
        )
        if not api_key:
            self.api_key = settings.OPENROUTER_API_KEY

    def _model_for_api(self, model: str) -> str:
        from app.engine.llm.config import strip_provider_prefix

        # OpenRouter natively uses "vendor/model" ids; only strip our
        # explicit "openrouter/" qualifier when present.
        return strip_provider_prefix(model, self.name)

"""Shared OpenAI-compatible chat-completions adapter (Phase 8).

OpenRouter, Groq, and HuggingFace's router all expose (or approximate) the
``POST /chat/completions`` shape. Subclasses only supply credentials, base
URL, and model-id normalization.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.engine.llm.base import BaseLLMProvider
from app.engine.llm.types import (
    LLMProviderError,
    LLMRateLimitError,
    LLMRequest,
    LLMResponse,
    LLMTimeoutError,
)

logger = logging.getLogger("autosage.llm")


class OpenAICompatibleProvider(BaseLLMProvider):
    """HTTP adapter for OpenAI-style chat completion APIs."""

    name: str = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_model_prefix: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        client: Optional[httpx.AsyncClient] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model_prefix = default_model_prefix
        self.extra_headers = extra_headers or {}
        self._client = client
        self._owns_client = client is None
        self.timeout = timeout if timeout is not None else settings.LLM_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _model_for_api(self, model: str) -> str:
        """Strip our own provider prefix so the remote API sees a native id."""
        from app.engine.llm.config import strip_provider_prefix

        return strip_provider_prefix(model, self.name)

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.extra_headers)
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def generate(self, request: LLMRequest) -> LLMResponse:
        client = await self._get_client()
        payload: Dict[str, Any] = {
            "model": self._model_for_api(request.model),
            "messages": [m.to_dict() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        payload.update(request.extra)
        timeout = request.timeout if request.timeout is not None else self.timeout
        try:
            response = await client.post(
                "/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"{self.name}: request timed out ({timeout}s)") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self.name}: transport error: {exc}") from exc

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise LLMRateLimitError(
                f"{self.name}: rate limited",
                retry_after=float(retry_after) if retry_after and retry_after.isdigit() else None,
            )
        if response.status_code >= 400:
            body = response.text[:500]
            raise LLMProviderError(
                f"{self.name}: HTTP {response.status_code}: {body}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"{self.name}: malformed response: {exc}") from exc

        return LLMResponse(
            text=text,
            model=payload["model"],
            provider=self.name,
            usage=data.get("usage") or {},
            raw=data,
        )

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

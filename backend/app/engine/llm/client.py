"""Unified LLM client: provider selection, fallback, timeout, rate limits.

Agents talk only to this interface::

    client = get_llm_client()
    text = await client.complete(system=..., user=...)
    obj  = await client.complete_structured(system=..., user=..., response_model=Schema)

Fallback chain (per request):
  1. Provider preferred by the model id prefix (``groq/...`` -> groq).
  2. Remaining providers in ``LLM_FALLBACK_ORDER`` that have API keys.

Rate limits (HTTP 429): wait up to ``LLM_RATE_LIMIT_WAIT_SECONDS`` once,
then fall through to the next provider. Timeouts / provider errors always
fall through. If every provider fails -> ``LLLMUnavailableError``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.observability import (
    TimingContext,
    get_experiment_id,
    get_agent_execution_id,
    log_with_context,
    trace_operation,
)
from app.engine.llm.base import BaseLLMProvider
from app.engine.llm.config import TIER_FAST, provider_for_model, resolve_model
from app.engine.llm.groq_provider import GroqProvider
from app.engine.llm.hf_provider import HuggingFaceProvider
from app.engine.llm.openrouter_provider import OpenRouterProvider
from app.engine.llm.types import (
    LLMParseError,
    LLMError,
    LLMMessage,
    LLMRateLimitError,
    LLMRequest,
    LLMResponse,
    LLMUnavailableError,
)

logger = logging.getLogger("autosage.llm")

T = TypeVar("T", bound=BaseModel)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def build_default_providers() -> Dict[str, BaseLLMProvider]:
    """Instantiate the standard adapter set from environment settings."""
    return {
        "groq": GroqProvider(),
        "openrouter": OpenRouterProvider(),
        "huggingface": HuggingFaceProvider(),
    }


def run_coro_sync(coro):  # type: ignore[no-untyped-def]
    """Drive a coroutine from sync code (handles a pre-existing event loop)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response (fences/prose ok)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned.strip())
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(cleaned)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            raise LLMParseError(f"response is not valid JSON: {exc}") from exc
    raise LLMParseError("no JSON object found in LLM response")


class LLMClient:
    """Provider-independent completion client with ordered fallback."""

    def __init__(
        self,
        providers: Optional[Dict[str, BaseLLMProvider]] = None,
        fallback_order: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        rate_limit_wait: Optional[float] = None,
    ) -> None:
        self.providers: Dict[str, BaseLLMProvider] = (
            dict(providers) if providers is not None else build_default_providers()
        )
        self.fallback_order = list(
            fallback_order
            if fallback_order is not None
            else settings.LLM_FALLBACK_ORDER
        )
        self.timeout = timeout if timeout is not None else settings.LLM_TIMEOUT_SECONDS
        self.rate_limit_wait = (
            rate_limit_wait
            if rate_limit_wait is not None
            else settings.LLM_RATE_LIMIT_WAIT_SECONDS
        )

    def has_providers(self) -> bool:
        """True when at least one configured adapter can serve requests."""
        return any(p.is_configured() for p in self.providers.values())

    def provider_chain(self, model: str) -> List[BaseLLMProvider]:
        """Ordered adapters for this request (preferred first, then fallback)."""
        configured = {
            name: p for name, p in self.providers.items() if p.is_configured()
        }
        chain: List[BaseLLMProvider] = []
        preferred = provider_for_model(model)
        if preferred and preferred in configured:
            chain.append(configured.pop(preferred))
        for name in self.fallback_order:
            if name in configured and configured[name] not in chain:
                chain.append(configured.pop(name))
        chain.extend(configured.values())
        return chain

    async def complete(
        self,
        *,
        system: str = "",
        user: str,
        model: Optional[str] = None,
        model_tier: str = TIER_FAST,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout: Optional[float] = None,
    ) -> LLMResponse:
        """Run one chat completion with provider fallback."""
        resolved = resolve_model(model, model_tier)
        chain = self.provider_chain(resolved)
        if not chain:
            raise LLMUnavailableError("no LLM providers configured (missing API keys)")

        messages: List[LLMMessage] = []
        if system:
            messages.append(LLMMessage(role="system", content=system))
        messages.append(LLMMessage(role="user", content=user))

        request = LLMRequest(
            model=resolved,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout if timeout is not None else self.timeout,
        )

        experiment_id = get_experiment_id()
        agent_exec_id = get_agent_execution_id()

        errors: List[str] = []
        for provider in chain:
            with TimingContext(
                "llm_completion",
                extra_fields={
                    "provider": provider.name,
                    "model": resolved,
                    "model_tier": model_tier,
                    "experiment": experiment_id,
                    "agent_execution": agent_exec_id,
                },
            ):
                with trace_operation(
                    "llm.complete",
                    attributes={
                        "provider": provider.name,
                        "model": resolved,
                        "model_tier": model_tier,
                        "experiment_id": experiment_id or "",
                        "agent_execution_id": agent_exec_id or "",
                    },
                ):
                    try:
                        response = await provider.generate(request)
                        log_with_context(
                            logger, logging.DEBUG, "llm_ok",
                            provider=provider.name, model=response.model,
                            experiment=experiment_id, agent_execution=agent_exec_id
                        )
                        return response
                    except LLMRateLimitError as exc:
                        waited = 0.0
                        if self.rate_limit_wait > 0:
                            waited = exc.retry_after
                            if waited is None or waited > self.rate_limit_wait:
                                waited = self.rate_limit_wait
                            if waited > 0:
                                await asyncio.sleep(waited)
                                try:
                                    response = await provider.generate(request)
                                    return response
                                except LLMError as retry_exc:
                                    errors.append(f"{provider.name}: {retry_exc}")
                                    continue
                        errors.append(f"{provider.name}: rate limited")
                        log_with_context(
                            logger, logging.WARNING, "llm_rate_limited",
                            provider=provider.name, waited=waited,
                            experiment=experiment_id, agent_execution=agent_exec_id
                        )
                        continue
                    except LLMError as exc:
                        errors.append(f"{provider.name}: {exc}")
                        log_with_context(
                            logger, logging.WARNING, "llm_provider_failed",
                            provider=provider.name, error=str(exc),
                            experiment=experiment_id, agent_execution=agent_exec_id
                        )
                        continue
        raise LLMUnavailableError("; ".join(errors) or "all providers failed")

    async def complete_structured(
        self,
        *,
        system: str,
        user: str,
        response_model: Type[T],
        **kwargs: object,
    ) -> T:
        """Complete and validate the reply as ``response_model`` (JSON schema)."""
        schema_prompt = (
            f"{user}\n\n"
            "Respond with ONLY a single JSON object (no markdown, no prose) "
            "matching this JSON schema:\n"
            f"{response_model.model_json_schema()}"
        )
        response = await self.complete(system=system, user=schema_prompt, **kwargs)  # type: ignore[arg-type]
        data = extract_json(response.text)
        try:
            return response_model.model_validate(data)
        except ValidationError as exc:
            raise LLMParseError(
                f"structured output failed validation for {response_model.__name__}: {exc}"
            ) from exc

    def complete_structured_sync(
        self,
        *,
        system: str,
        user: str,
        response_model: Type[T],
        **kwargs: object,
    ) -> T:
        """Sync wrapper around :meth:`complete_structured` (agent nodes)."""
        return run_coro_sync(
            self.complete_structured(
                system=system, user=user, response_model=response_model, **kwargs
            )
        )

    async def aclose(self) -> None:
        for provider in self.providers.values():
            await provider.aclose()


# -- process-wide default client -------------------------------------------------
_default_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Return the process-wide LLMClient (lazily constructed)."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def set_llm_client(client: Optional[LLMClient]) -> None:
    """Replace (or clear) the process-wide client — used by tests/DI."""
    global _default_client
    _default_client = client


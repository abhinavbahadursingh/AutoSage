"""Provider-independent LLM abstraction layer (Phase 8)."""
from app.engine.llm.base import BaseLLMProvider
from app.engine.llm.client import (
    LLMClient,
    build_default_providers,
    extract_json,
    get_llm_client,
    set_llm_client,
)
from app.engine.llm.config import provider_for_model, resolve_model
from app.engine.llm.groq_provider import GroqProvider
from app.engine.llm.hf_provider import HuggingFaceProvider
from app.engine.llm.openrouter_provider import OpenRouterProvider
from app.engine.llm.types import (
    LLMParseError,
    LLMError,
    LLMMessage,
    LLMProviderError,
    LLMRateLimitError,
    LLMRequest,
    LLMResponse,
    LLMTimeoutError,
    LLMUnavailableError,
)

__all__ = [
    "BaseLLMProvider",
    "GroqProvider",
    "HuggingFaceProvider",
    "LLMClient",
    "LLMError",
    "LLMMessage",
    "LLMParseError",
    "LLMProviderError",
    "LLMRateLimitError",
    "LLMRequest",
    "LLMResponse",
    "LLMTimeoutError",
    "LLMUnavailableError",
    "OpenRouterProvider",
    "build_default_providers",
    "extract_json",
    "get_llm_client",
    "provider_for_model",
    "resolve_model",
    "set_llm_client",
]

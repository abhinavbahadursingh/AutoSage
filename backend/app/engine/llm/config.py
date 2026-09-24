"""Central model / provider selection configuration (Phase 8).

Model ids are provider-qualified when possible (``groq/...``,
``openrouter/...``, ``huggingface/...``) so the client can prefer the right
adapter and strip the prefix for the provider's native API.
"""
from __future__ import annotations

from typing import Dict, Optional

from app.core.config import settings

#: Known provider prefixes accepted in model ids.
PROVIDER_ALIASES: Dict[str, str] = {
    "groq": "groq",
    "openrouter": "openrouter",
    "huggingface": "huggingface",
    "hf": "huggingface",
}

TIER_FAST = "fast"
TIER_REASONING = "reasoning"
SUPPORTED_TIERS = (TIER_FAST, TIER_REASONING)


def provider_for_model(model: str) -> Optional[str]:
    """Return the preferred provider id for a model id, if recognizable."""
    if not model or "/" not in model:
        return None
    prefix = model.split("/", 1)[0].lower()
    return PROVIDER_ALIASES.get(prefix)


def strip_provider_prefix(model: str, provider: str) -> str:
    """Remove a provider-qualified prefix (``groq/foo`` -> ``foo``)."""
    prefix = f"{provider}/"
    if model.lower().startswith(prefix):
        return model[len(prefix):]
    # Cross-provider aliases (e.g. hf/ on the huggingface adapter).
    for alias, canonical in PROVIDER_ALIASES.items():
        if canonical == provider and model.lower().startswith(f"{alias}/"):
            return model[len(alias) + 1:]
    return model


def resolve_model(model: Optional[str] = None, model_tier: str = TIER_FAST) -> str:
    """Resolve the concrete model id for a request.

    Priority: explicit ``model`` arg > ``DEFAULT_MODEL`` override >
    tier default (``fast`` / ``reasoning``).
    """
    if model:
        return model
    if settings.DEFAULT_MODEL:
        return settings.DEFAULT_MODEL
    if model_tier == TIER_REASONING:
        return settings.DEFAULT_REASONING_MODEL
    return settings.DEFAULT_FAST_MODEL

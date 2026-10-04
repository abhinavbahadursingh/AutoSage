"""LLM connectivity endpoints.

GET  /llm/status  -> active model config + configured providers
POST /llm/check   -> run one tiny completion against a model id
POST /llm/select  -> pick the model used for subsequent processing
"""
import time
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.config import settings

router = APIRouter()


class CheckRequest(BaseModel):
    model: Optional[str] = None  # provider-qualified, e.g. "groq/openai/gpt-oss-20b"


class CheckResponse(BaseModel):
    ok: bool
    model: str
    provider: Optional[str] = None
    latency_ms: Optional[float] = None
    sample: Optional[str] = None
    error: Optional[str] = None


class SelectRequest(BaseModel):
    model: str  # "" clears the override and restores tier defaults


class StatusResponse(BaseModel):
    fast_model: str
    reasoning_model: str
    default_model: str
    providers: List[str]
    fallback_order: List[str]


@router.get("/status", response_model=StatusResponse, summary="Current LLM configuration")
async def llm_status(user: CurrentUser) -> StatusResponse:
    from app.engine.llm.client import build_default_providers

    providers = [name for name, p in build_default_providers().items() if p.is_configured()]
    return StatusResponse(
        fast_model=settings.DEFAULT_FAST_MODEL,
        reasoning_model=settings.DEFAULT_REASONING_MODEL,
        default_model=settings.DEFAULT_MODEL,
        providers=providers,
        fallback_order=settings.LLM_FALLBACK_ORDER,
    )


@router.post("/check", response_model=CheckResponse, summary="Probe a model with one tiny completion")
async def llm_check(payload: CheckRequest, user: CurrentUser) -> CheckResponse:
    from app.engine.llm.client import get_llm_client
    from app.engine.llm.config import resolve_model
    from app.engine.llm.types import LLMError

    model = resolve_model(payload.model, "fast")
    start = time.perf_counter()
    try:
        client = get_llm_client()
        if not client.has_providers():
            return CheckResponse(ok=False, model=model, error="no LLM providers configured (missing API keys)")
        response = await client.complete(
            system="You are a connectivity probe. Reply with exactly: ok",
            user="ping",
            model=model,
            max_tokens=16,
            temperature=0.0,
        )
        latency = (time.perf_counter() - start) * 1000
        return CheckResponse(
            ok=True,
            model=response.model,
            provider=response.provider,
            latency_ms=round(latency, 1),
            sample=response.text.strip()[:120],
        )
    except LLMError as exc:
        latency = (time.perf_counter() - start) * 1000
        return CheckResponse(ok=False, model=model, latency_ms=round(latency, 1), error=str(exc))
    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
        latency = (time.perf_counter() - start) * 1000
        return CheckResponse(ok=False, model=model, latency_ms=round(latency, 1), error=f"{type(exc).__name__}: {exc}")


@router.post("/select", response_model=StatusResponse, summary="Set the model used for processing")
async def llm_select(payload: SelectRequest, user: CurrentUser) -> StatusResponse:
    settings.DEFAULT_MODEL = payload.model.strip()
    _persist_env("DEFAULT_MODEL", settings.DEFAULT_MODEL)
    return await llm_status(user)


def _persist_env(key: str, value: str) -> None:
    """Update (or append) ``key=value`` in the backend .env file."""
    import os

    env_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".env"
    )
    env_path = os.path.normpath(env_path)
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if line.lstrip().startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
        if not found:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] = lines[-1] + "\n"
            lines.append(f"{key}={value}\n")
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError:
        pass

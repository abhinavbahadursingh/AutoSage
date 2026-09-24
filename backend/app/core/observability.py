"""Observability layer: structured logging, context propagation, timing, and OpenTelemetry.

Provides a cross-cutting layer for request IDs, experiment IDs, agent execution IDs,
error tracing, performance timing, retry tracking, and OpenTelemetry instrumentation.
"""
from __future__ import annotations

import contextvars
import functools
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, Optional, TypeVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, SpanContext, Tracer, get_current_span

from app.core.config import settings

logger = logging.getLogger("autosage.observability")

T = TypeVar("T")

# Context variables for cross-cutting IDs
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)
experiment_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "experiment_id", default=None
)
agent_execution_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agent_execution_id", default=None
)
retry_context_var: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "retry_context", default=None
)

# Tracer
_tracer: Optional[Tracer] = None
_otel_initialized = False


@dataclass
class TimingContext:
    """Context manager for performance timing with structured logging."""

    operation: str
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("autosage.timing"))
    level: int = logging.INFO
    extra_fields: Dict[str, Any] = field(default_factory=dict)
    _start: float = field(default=0.0, init=False)

    def __enter__(self) -> "TimingContext":
        self._start = time.perf_counter()
        self.logger.log(
            self.level,
            f"{self.operation}_start",
            extra={"operation": self.operation, **self.extra_fields, **_get_context_extras()},
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = (time.perf_counter() - self._start) * 1000
        extra = {
            "operation": self.operation,
            "duration_ms": round(duration_ms, 2),
            "success": exc_type is None,
            **self.extra_fields,
            **_get_context_extras(),
        }
        if exc_type:
            extra["error_type"] = exc_type.__name__
            extra["error_message"] = str(exc_val)
            self.logger.error(f"{self.operation}_failed", extra=extra)
        else:
            self.logger.log(self.level, f"{self.operation}_completed", extra=extra)


@dataclass
class RetryContext:
    """Context for tracking retry attempts."""

    operation: str
    max_retries: int
    attempt: int = 0
    last_error: Optional[Exception] = None

    def next_attempt(self, error: Exception) -> bool:
        """Record an attempt. Returns True if should retry."""
        self.attempt += 1
        self.last_error = error
        retry_context_var.set(
            {
                "operation": self.operation,
                "attempt": self.attempt,
                "max_retries": self.max_retries,
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )
        return self.attempt < self.max_retries

    def log_retry(self, logger: logging.Logger, countdown: Optional[float] = None) -> None:
        """Log retry attempt with structured fields."""
        extra = {
            "operation": self.operation,
            "attempt": self.attempt,
            "max_retries": self.max_retries,
            "error_type": type(self.last_error).__name__ if self.last_error else None,
            "error_message": str(self.last_error) if self.last_error else None,
            **_get_context_extras(),
        }
        if countdown is not None:
            extra["retry_countdown_sec"] = countdown
        logger.warning("retry_attempt", extra=extra)


def _get_context_extras() -> Dict[str, Any]:
    """Collect all context variables as extra fields for logging."""
    extras = {}
    if request_id := request_id_var.get():
        extras["request_id"] = request_id
    if experiment_id := experiment_id_var.get():
        extras["experiment_id"] = experiment_id
    if agent_exec_id := agent_execution_id_var.get():
        extras["agent_execution_id"] = agent_exec_id
    if retry_ctx := retry_context_var.get():
        extras["retry_context"] = retry_ctx
    return extras


def get_request_id() -> Optional[str]:
    return request_id_var.get()


def set_request_id(request_id: str) -> contextvars.Token:
    return request_id_var.set(request_id)


def clear_request_id(token: contextvars.Token) -> None:
    request_id_var.reset(token)


def get_experiment_id() -> Optional[str]:
    return experiment_id_var.get()


def set_experiment_id(experiment_id: str) -> contextvars.Token:
    return experiment_id_var.set(experiment_id)


def clear_experiment_id(token: contextvars.Token) -> None:
    experiment_id_var.reset(token)


def get_agent_execution_id() -> Optional[str]:
    return agent_execution_id_var.get()


def set_agent_execution_id(agent_execution_id: str) -> contextvars.Token:
    return agent_execution_id_var.set(agent_execution_id)


def clear_agent_execution_id(token: contextvars.Token) -> None:
    agent_execution_id_var.reset(token)


def generate_request_id() -> str:
    return str(uuid.uuid4())


def generate_experiment_id() -> str:
    return str(uuid.uuid4())


def generate_agent_execution_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def request_context(request_id: Optional[str] = None) -> Generator[str, None, None]:
    """Context manager for request-scoped IDs."""
    rid = request_id or generate_request_id()
    token = set_request_id(rid)
    try:
        yield rid
    finally:
        clear_request_id(token)


@contextmanager
def experiment_context(experiment_id: str) -> Generator[str, None, None]:
    """Context manager for experiment-scoped IDs."""
    token = set_experiment_id(experiment_id)
    try:
        yield experiment_id
    finally:
        clear_experiment_id(token)


@contextmanager
def agent_execution_context(agent_execution_id: Optional[str] = None) -> Generator[str, None, None]:
    """Context manager for agent execution-scoped IDs."""
    aid = agent_execution_id or generate_agent_execution_id()
    token = set_agent_execution_id(aid)
    try:
        yield aid
    finally:
        clear_agent_execution_id(token)


def timed_operation(operation: str, **extra_fields: Any) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for timing synchronous functions with structured logging."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            with TimingContext(operation, extra_fields=extra_fields):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def timed_async_operation(operation: str, **extra_fields: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for timing async functions with structured logging."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            with TimingContext(operation, extra_fields=extra_fields):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# OpenTelemetry setup
def init_opentelemetry(service_name: str = "autosage-backend") -> None:
    """Initialize OpenTelemetry tracing.

    Configures OTLP HTTP exporter if OTEL_EXPORTER_OTLP_ENDPOINT is set.
    Otherwise, tracing is initialized but not exported (useful for local dev).
    """
    global _tracer, _otel_initialized

    if _otel_initialized:
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    # OTLP HTTP exporter (configured via OTEL_EXPORTER_OTLP_ENDPOINT env var)
    try:
        otlp_endpoint = getattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
        if otlp_endpoint:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("opentelemetry_otlp_exporter_configured", extra={"endpoint": otlp_endpoint})
        else:
            logger.info("opentelemetry_initialized_no_exporter")
    except Exception as e:
        logger.warning("opentelemetry_exporter_failed", extra={"error": str(e)})

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(__name__)
    _otel_initialized = True


def get_tracer() -> Optional[Tracer]:
    return _tracer


def get_current_span_context() -> Optional[SpanContext]:
    """Get the current span context for correlation."""
    span = get_current_span()
    if span and span.get_span_context().is_valid:
        return span.get_span_context()
    return None


@contextmanager
def trace_operation(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
) -> Generator[Optional[Span], None, None]:
    """Context manager for creating a traced span."""
    tracer = get_tracer()
    if tracer is None:
        yield None
        return

    with tracer.start_as_current_span(name, kind=kind, attributes=attributes or {}) as span:
        # Add context IDs as attributes
        if request_id := get_request_id():
            span.set_attribute("autosage.request_id", request_id)
        if experiment_id := get_experiment_id():
            span.set_attribute("autosage.experiment_id", experiment_id)
        if agent_exec_id := get_agent_execution_id():
            span.set_attribute("autosage.agent_execution_id", agent_exec_id)
        yield span


def instrument_fastapi(app: Any) -> None:
    """Instrument FastAPI app with OpenTelemetry."""
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("fastapi_instrumented")
    except Exception as e:
        logger.warning("fastapi_instrumentation_failed", extra={"error": str(e)})


def instrument_celery() -> None:
    """Instrument Celery with OpenTelemetry (manual, no auto-instrumentation)."""
    logger.info("celery_instrumentation_placeholder")


def instrument_all() -> None:
    """Instrument all supported libraries."""
    init_opentelemetry()
    try:
        RequestsInstrumentor().instrument()
        RedisInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument()
        logger.info("opentelemetry_libraries_instrumented")
    except Exception as e:
        logger.warning("opentelemetry_library_instrumentation_failed", extra={"error": str(e)})


# Reserved LogRecord attributes that cannot be used as extra fields
_RESERVED_LOG_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


def _sanitize_extra(extra: Dict[str, Any]) -> Dict[str, Any]:
    """Remove reserved attributes from extra dict to avoid LogRecord conflicts."""
    return {k: v for k, v in extra.items() if k not in _RESERVED_LOG_ATTRS}


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **extra: Any,
) -> None:
    """Log a message with all context variables included."""
    combined = {**_get_context_extras(), **_sanitize_extra(extra)}
    logger.log(level, message, extra=combined)


def log_exception_with_context(
    logger: logging.Logger,
    message: str,
    **extra: Any,
) -> None:
    """Log an exception with all context variables included."""
    combined = {**_get_context_extras(), **_sanitize_extra(extra)}
    logger.exception(message, extra=combined)
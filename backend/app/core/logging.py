"""Structured (JSON-lines) logging configuration.

Single entry point: call ``setup_logging()`` once at startup (see
``app.main.lifespan``). All log records are emitted as one JSON object per
line so log aggregators can parse them without extra processing.
"""
import json
import logging
import sys
from datetime import datetime, timezone

from opentelemetry import trace


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as a single JSON object with OpenTelemetry context."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add OpenTelemetry trace context if available
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            ctx = span.get_span_context()
            payload["trace_id"] = format(ctx.trace_id, "032x")
            payload["span_id"] = format(ctx.span_id, "016x")
            payload["trace_flags"] = format(ctx.trace_flags, "02x")

        # Attach structured extras (e.g. logger.info("...", extra={"a": 1})).
        reserved = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "asctime", "taskName",
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in reserved}
        if extras:
            payload["extra"] = extras
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_configured = False


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the root handler once and return the app logger."""
    global _configured
    if not _configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(getattr(logging, level.upper(), logging.INFO))
        # Quiet noisy third-party loggers; keep warnings+.
        for noisy in ("uvicorn.access", "sqlalchemy.engine"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        _configured = True
    return logging.getLogger("autosage")


logger = logging.getLogger("autosage")

"""Runtime diagnostics state (in-memory, per-process).

Captured by the API process during startup and after every experiment run;
surfaced by GET /api/v1/diagnostics.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# Embedded Celery worker lifecycle (set by app.main lifespan).
embedded_worker: Dict[str, Any] = {
    "enabled": False,
    "running": False,
    "queue": None,
    "pool": None,
    "concurrency": None,
    "error": None,
}

# Most recent experiment execution record (set by app.workers.tasks).
last_execution: Dict[str, Any] = {}


def set_embedded_worker(
    *,
    enabled: bool,
    running: bool,
    queue: Optional[str] = None,
    pool: Optional[str] = None,
    concurrency: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    global embedded_worker
    embedded_worker = {
        "enabled": enabled,
        "running": running,
        "queue": queue,
        "pool": pool,
        "concurrency": concurrency,
        "error": error,
    }


def record_execution(info: Dict[str, Any]) -> None:
    global last_execution
    last_execution = dict(info)

"""Backward-compatible re-exports.

The canonical database layer lives in :mod:`app.db`. This module keeps the
old import path (``app.core.database``) working for existing code.
"""
from app.db.session import (  # noqa: F401
    AsyncSessionLocal,
    check_connection,
    close_engine,
    engine,
    get_db,
    init_engine,
)

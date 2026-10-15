"""Objective Verification engine.

Deterministic, read-only verification of the four canonical AutoSage
objectives against one fresh session. No check in this package preprocesses a
dataset, trains a model, or retrains anything.

The stage order is fixed in :mod:`app.engine.objective_verification.runner`
and nothing at runtime chooses it.
"""
from app.engine.objective_verification.definitions import (
    OBJECTIVES,
    OBJECTIVES_BY_ID,
    objective_definitions,
)
from app.engine.objective_verification.runner import ALL_STAGES, run_verification

__all__ = [
    "ALL_STAGES",
    "OBJECTIVES",
    "OBJECTIVES_BY_ID",
    "objective_definitions",
    "run_verification",
]
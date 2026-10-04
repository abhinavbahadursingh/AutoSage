"""Canonical metric handling (metric propagation, scoring, selection).

Every "which metric?" decision in the pipeline goes through this module so the
objective the user asked for survives end to end instead of being replaced by
an accuracy default somewhere downstream:

    request config -> workflow state -> model shortlist -> training
        -> evaluation -> model selection -> verification gate -> result

Key rules encoded here:

- :func:`resolve_primary_metric` reads the *requested* metric from the
  experiment config (``primary_metric``, then ``metric``, then
  ``evaluation_metric``). Only when the request names no metric at all does the
  documented per-task fallback apply -- it is never allowed to override a
  request (see :data:`FALLBACK_METRIC_BY_TASK`).
- :func:`score_from_metrics` resolves a metric name against a measured metrics
  dict (including aliases such as ``f1`` -> ``f1_macro``).
- :func:`is_higher_is_better` makes selection correct for error metrics
  (``mse``/``mae``/``rmse``/``log_loss`` are minimised, everything else
  maximised).
- :func:`secondary_metrics` orders the reported secondary metrics so accuracy
  is reported *after* the requested objective rather than in place of it.
- :func:`canonical_result` builds the canonical result payload.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

# Metrics that make sense for binary/multiclass classification.
CLASSIFICATION_METRICS = frozenset(
    {"accuracy", "precision", "recall", "f1", "roc_auc", "log_loss"}
)
# Metrics that make sense for continuous targets.
REGRESSION_METRICS = frozenset({"mse", "mae", "rmse", "r2"})

# Metrics where a *lower* value is better. Everything else is maximised.
LOWER_IS_BETTER = frozenset({"mse", "mae", "rmse", "log_loss"})

# Accepted spellings for a requested metric, in resolution order.
METRIC_ALIASES: Dict[str, tuple] = {
    "f1": ("f1", "f1_macro", "f1_weighted"),
    "f1_macro": ("f1_macro", "f1", "f1_weighted"),
    "f1_weighted": ("f1_weighted", "f1", "f1_macro"),
}

# Metric names accepted from a request, mapped to their canonical spelling.
REQUEST_METRIC_ALIASES: Dict[str, str] = {
    "f1": "f1",
    "f1_macro": "f1",
    "f1_weighted": "f1",
    "accuracy": "accuracy",
    "precision": "precision",
    "recall": "recall",
    "roc_auc": "roc_auc",
    "auc": "roc_auc",
    "auc_roc": "roc_auc",
    "log_loss": "log_loss",
    "logloss": "log_loss",
    "mse": "mse",
    "mae": "mae",
    "rmse": "rmse",
    "r2": "r2",
}

# Last-resort defaults, used ONLY when a request names no metric at all.
# These are never permitted to override an explicitly requested metric.
FALLBACK_METRIC_BY_TASK: Dict[str, str] = {
    "classification": "accuracy",
    "regression": "r2",
    "": "accuracy",
}

# Config keys that may carry the requested objective, most explicit first.
PRIMARY_METRIC_CONFIG_KEYS = ("primary_metric", "metric", "evaluation_metric")

# Every classification metric reported for a trained model (requirement:
# accuracy, precision, recall and F1 for every compared model).
CLASSIFICATION_REPORT_METRICS = ("accuracy", "precision", "recall", "f1")


def canonical_metric_name(metric: Any) -> str:
    """Normalize a requested metric spelling (``auc`` -> ``roc_auc``)."""
    name = str(metric or "").strip().lower()
    return REQUEST_METRIC_ALIASES.get(name, name)


def resolve_primary_metric(
    config: Optional[Mapping[str, Any]] = None,
    task_type: Optional[str] = None,
) -> str:
    """Resolve the objective metric for a run.

    Precedence: an explicitly requested metric (``primary_metric``, ``metric``
    or ``evaluation_metric`` in the experiment config) always wins; the
    per-task fallback applies only when the request is silent.
    """
    cfg = config or {}
    for key in PRIMARY_METRIC_CONFIG_KEYS:
        if key in cfg and cfg.get(key):
            name = canonical_metric_name(cfg.get(key))
            if name:
                return name
    return FALLBACK_METRIC_BY_TASK.get(str(task_type or "").strip().lower(), "accuracy")


def resolve_compare_models(config: Optional[Mapping[str, Any]] = None) -> bool:
    """Resolve the ``compare_models`` intent (string/bool tolerant)."""
    cfg = config or {}
    for key in ("compare_models", "compare", "compare_multiple_models"):
        if key not in cfg or cfg.get(key) is None:
            continue
        raw = cfg.get(key)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return bool(raw)
        return str(raw).strip().lower() in {"1", "true", "yes", "on", "y"}
    return False


def is_higher_is_better(metric: str) -> bool:
    """Whether a larger value of ``metric`` is a better model."""
    return canonical_metric_name(metric) not in LOWER_IS_BETTER


def score_from_metrics(
    metrics: Optional[Mapping[str, Any]], metric: str
) -> Optional[float]:
    """Pull the score for ``metric`` out of a measured metrics dict."""
    if not metrics:
        return None
    name = canonical_metric_name(metric)
    keys: Iterable[str] = METRIC_ALIASES.get(name, (name,))
    for key in keys:
        if key in metrics:
            try:
                return float(metrics[key])
            except (TypeError, ValueError):
                continue
    return None


def secondary_metrics(
    primary_metric: str, task_type: str = "classification"
) -> List[str]:
    """Ordered secondary metrics to report alongside ``primary_metric``.

    The requested objective always comes first and accuracy is never promoted
    above it -- when recall is requested, accuracy is reported last as a
    secondary metric.
    """
    primary = canonical_metric_name(primary_metric)
    if str(task_type).strip().lower() == "regression":
        pool = [m for m in ("r2", "rmse", "mae", "mse") if m != primary]
    else:
        pool = [m for m in ("recall", "precision", "f1", "accuracy", "roc_auc") if m != primary]
    return pool


def select_best_by_metric(
    scored: Iterable[Mapping[str, Any]], metric: str
) -> Optional[Mapping[str, Any]]:
    """Pick the entry with the best score for ``metric``.

    ``scored`` entries must expose a numeric ``score`` (or a ``metrics`` dict).
    Ties resolve to the first entry, so candidate order stays deterministic.
    """
    entries: List[Mapping[str, Any]] = []
    for entry in scored:
        score = entry.get("score")
        if score is None:
            score = score_from_metrics(entry.get("metrics"), metric)
        if score is None:
            continue
        try:
            entries.append({**entry, "score": float(score)})
        except (TypeError, ValueError):
            continue
    if not entries:
        return None
    reverse = is_higher_is_better(metric)
    best = entries[0]
    for entry in entries[1:]:
        # Strict comparison keeps the first candidate on ties (deterministic).
        better = entry["score"] > best["score"] if reverse else entry["score"] < best["score"]
        if better:
            best = entry
    return best


def canonical_result(
    *,
    primary_metric: str,
    primary_score: Optional[float],
    metrics: Optional[Mapping[str, Any]] = None,
    model_comparison: Optional[List[Dict[str, Any]]] = None,
    selected_model: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Build the canonical experiment result payload.

    Always carries the five canonical keys so consumers never have to guess
    which metric was optimized::

        primary_metric, primary_score, metrics, model_comparison, selected_model
    """
    primary = canonical_metric_name(primary_metric)
    result: Dict[str, Any] = {
        "primary_metric": primary,
        "primary_score": float(primary_score) if primary_score is not None else None,
        "metrics": dict(metrics or {}),
        "model_comparison": list(model_comparison or []),
        "selected_model": selected_model,
    }
    for key, value in extra.items():
        if key not in result:
            result[key] = value
    return result

"""Data Leakage Detector via Static AST Analysis.

Looks for the classic leakage patterns in a training script:

1. fitting anything on the whole dataset with no split / cross-validation,
2. fitting a transformer or estimator on held-out (test/val) data,
3. keeping the target column inside the feature matrix.

Returns ``(clean, errors)`` -- ``clean`` is ``False`` when a pattern matched.
"""
from __future__ import annotations

import ast
from typing import List, Set, Tuple

# Call names that prove the script separates train from evaluation data.
_SPLIT_MARKERS = (
    "split", "cross_val", "cross_validate", "kfold",
    "holdout", "hold_out", "grid_search", "randomized_search",
)
_SPLIT_CLASSES = {
    "KFold", "StratifiedKFold", "GroupKFold", "TimeSeriesSplit",
    "ShuffleSplit", "StratifiedShuffleSplit", "GroupShuffleSplit",
    "RepeatedKFold", "RepeatedStratifiedKFold", "LeaveOneOut", "LeavePOut",
}

# Names that point at held-out data.
_TEST_TOKENS = {
    "test", "tests", "te", "val", "vals", "valid", "eval",
    "holdout", "heldout", "hold", "unseen",
}
_TEST_SUFFIXES = ("_test", "_te", "_val", "_valid", "_eval", "_holdout", "_heldout")
# Names that point at the full (pre-split) feature matrix.
_FULL_DATA_NAMES = {
    "df", "data", "dataset", "full_data", "all_data",
    "X", "features", "X_all", "X_whole", "X_full",
}
# Names that hold the target vector.
_TARGET_NAMES = {"y", "target", "label", "labels", "y_true"}
# Names that hold the feature matrix.
_FEATURE_NAMES = {"X", "features", "X_all", "X_whole", "X_full"}

_FIT_ATTRS = {"fit", "fit_transform", "fit_predict", "partial_fit"}


def _call_name(node: ast.Call) -> str:
    """Dotted-ish name of a call target (``train_test_split``, ``p.fit``)."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_test_like(name: str) -> bool:
    lowered = name.lower()
    if lowered in _TEST_TOKENS:
        return True
    if lowered.endswith(_TEST_SUFFIXES):
        return True
    return any(tok in lowered for tok in ("test", "holdout", "heldout"))


def _root_name(node: ast.AST) -> str:
    """Root identifier of an expression (``df.drop(...)`` -> ``df``)."""
    current = node
    while isinstance(current, (ast.Attribute, ast.Subscript)):
        current = current.value  # type: ignore[attr-defined]
    if isinstance(current, ast.Name):
        return current.id
    return ""


def _targets(node: ast.AST) -> List[str]:
    if isinstance(node, (ast.Tuple, ast.List)):
        names: List[str] = []
        for elt in node.elts:
            names.extend(_targets(elt))
        return names
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Starred):
        return _targets(node.value)
    return []


def _is_copy_of(node: ast.AST) -> str:
    """For ``X = df.copy()`` return ``df``; for ``X = df.drop(...)`` return ``""``."""
    if isinstance(node, ast.Name):
        return node.id
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "copy"
    ):
        return _root_name(node.func.value)
    return ""


class LeakageDetector:
    @staticmethod
    def detect_leakage(code: str) -> Tuple[bool, List[str]]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return False, [f"SyntaxError: {exc}"]

        errors: List[str] = []

        fit_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Attribute) and node.func.attr in _FIT_ATTRS)
                or (isinstance(node.func, ast.Name) and node.func.id in _FIT_ATTRS)
            )
        ]

        split_signals: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                lowered = name.lower()
                if name in _SPLIT_CLASSES or (
                    lowered != "split" and any(m in lowered for m in _SPLIT_MARKERS)
                ):
                    split_signals.add(name)

        # (1) Fit with no separation between train and evaluation data at all.
        if fit_calls and not split_signals:
            errors.append(
                "fit() called with no train/test split or cross-validation detected "
                "(model sees the data it is scored on)"
            )

        # (2) Fit on held-out data, or on the full frame once a split exists.
        for call in fit_calls:
            receiver = ""
            if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
                receiver = call.func.value.id
            operands = ([receiver] if receiver else []) + [
                _root_name(arg) for arg in call.args if isinstance(arg, (ast.Name, ast.Attribute, ast.Subscript))
            ]
            for name in operands:
                if not name:
                    continue
                if _is_test_like(name):
                    errors.append(
                        f"fit() on held-out data: {name} is fitted instead of only transformed"
                    )
                elif split_signals and name in _FULL_DATA_NAMES:
                    errors.append(
                        f"fit() on the full dataset before splitting: {name}"
                    )

        # (3) Target column still inside the feature matrix.
        target_bases: Set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Subscript):
                continue
            names = _targets(node.targets[0]) if node.targets else []
            if any(n in _TARGET_NAMES for n in names) and isinstance(node.value.value, ast.Name):
                target_bases.add(node.value.value.id)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            names = _targets(node.targets[0]) if node.targets else []
            if not any(n in _FEATURE_NAMES for n in names):
                continue
            source = _is_copy_of(node.value)
            if source and source in target_bases:
                errors.append(
                    f"target column may remain in the feature matrix: {names[0]} = {source}"
                    " keeps the target column"
                )

        # De-duplicate while preserving order (nested rules can repeat).
        seen: Set[str] = set()
        unique_errors = [e for e in errors if not (e in seen or seen.add(e))]
        return len(unique_errors) == 0, unique_errors

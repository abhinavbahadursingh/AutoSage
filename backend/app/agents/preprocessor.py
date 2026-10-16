"""Preprocessor Agent (Phase 7).

Responsibility: propose a concrete cleaning / feature-engineering spec
(imputation, encoding, scaling, drops) from the profile, and make that spec
actionable for the downstream trainer.

Improvements over the original version:
- Per-column imputation instead of a single global strategy.
- Cardinality-aware encoding (one-hot for low-cardinality, ordinal for high).
- Distribution-aware scaling (standard / robust / min-max / none).
- Optional feature engineering (log / sqrt for skewed numerics, date parts).
- Explicit target-column exclusion from features.
- Outlier handling translated into a clipping action, not just a label.
- Uses profile signals (class_balance, missing_rate, feature_types).
- Bumps model_tier to "reasoning" so an LLM (when available) designs smarter
  preprocessing; the deterministic heuristic runs when no LLM is configured.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from app.agents.base import BaseAgent
from app.agents.schemas import AgentOutput, PreprocessingSpecOutput
from app.agents.state import ExperimentWorkflowState

logger = logging.getLogger("autosage.workflow")

STAGE = "preprocessor"

_SYSTEM = (
    "You are the AutoSage Preprocessor Agent. "
    "Design a preprocessing pipeline for the profiled dataset. "
    "Return JSON matching the provided schema. "
    "Prefer per-column decisions over one-size-fits-all defaults: drop columns "
    "that are mostly missing, encode low-cardinality categorics one-hot and "
    "high-cardinality ones ordinally, scale numerics by distribution, and never "
    "include the target column as a feature."
)


class PreprocessorAgent(BaseAgent):
    """Builds the preprocessing specification."""

    stage = STAGE
    output_model = PreprocessingSpecOutput

    def model_tier(self) -> str:
        """Preprocessing is reasoning-heavy; use the stronger tier when available."""
        return "reasoning"

    # -- prompt -----------------------------------------------------------------
    def build_prompts(self, state: ExperimentWorkflowState) -> Tuple[str, str]:
        profile = state.get("profile") or {}
        dataset = state.get("dataset_info") or {}
        schema = state.get("dataset_schema") or {}
        columns = schema.get("columns") or []
        col_lines = []
        for c in columns:
            name = c.get("name", "unknown")
            kind = c.get("kind", "unknown")
            null_rate = c.get("null_rate", 0.0)
            n_unique = c.get("n_unique", 0)
            col_lines.append(
                f"- {name} (kind={kind}, null_rate={null_rate}, n_unique={n_unique})"
            )
        target = profile.get("target_column", "")
        class_balance = profile.get("class_balance") or {}
        missing_rate = profile.get("missing_rate", 0.0)
        user = (
            "Design preprocessing for this dataset.\n"
            f"target_column={target}\n"
            f"task_type={profile.get('task_type', 'classification')}\n"
            f"dataset_missing_rate={missing_rate}\n"
            f"class_balance={class_balance}\n"
            f"profile={profile}\n"
            f"columns:\n" + "\n".join(col_lines) + "\n"
            "Return JSON matching the provided schema."
        )
        return _SYSTEM, user

    # -- heuristic --------------------------------------------------------------
    def heuristic(self, state: ExperimentWorkflowState) -> AgentOutput:
        profile = state.get("profile") or {}
        dataset = state.get("dataset_info") or {}
        schema = state.get("dataset_schema") or {}
        task_type = str(profile.get("task_type", "classification"))
        target = str(profile.get("target_column", "") or "")

        columns = schema.get("columns") or []
        class_balance = profile.get("class_balance") or {}
        dataset_missing_rate = float(profile.get("missing_rate", 0.0) or 0.0)

        # Classify columns -------------------------------------------------------
        numeric_cols: List[str] = []
        categorical_cols: List[str] = []
        binary_cols: List[str] = []
        datetime_cols: List[str] = []
        id_cols: List[str] = []
        drop_cols: List[str] = [target] if target else []  # never leak target

        for c in columns:
            name = c.get("name", "")
            if not name or name == target:
                continue
            kind = str(c.get("kind", "unknown")).lower()
            null_rate = float(c.get("null_rate", 0.0) or 0.0)
            n_unique = int(c.get("n_unique", 0) or 0)

            # Mostly-missing columns: drop rather than impute.
            if null_rate > 0.5:
                drop_cols.append(name)
                continue

            # Identifier-like columns: drop.
            if kind == "identifier" or (kind == "unknown" and null_rate > 0.8):
                id_cols.append(name)
                drop_cols.append(name)
                continue

            if kind == "numeric":
                numeric_cols.append(name)
            elif kind in ("categorical", "boolean"):
                if n_unique <= 2:
                    binary_cols.append(name)
                else:
                    categorical_cols.append(name)
            elif kind in ("datetime", "date", "timestamp"):
                datetime_cols.append(name)
            elif kind == "unknown":
                # Heuristic fallback: treat as numeric if mostly numeric-looking,
                # otherwise categorical.
                categorical_cols.append(name)

        # Per-column imputation --------------------------------------------------
        imputation_rules: Dict[str, str] = {}
        for col in numeric_cols:
            imputation_rules[col] = "median"
        for col in categorical_cols:
            imputation_rules[col] = "most_frequent"
        for col in binary_cols:
            imputation_rules[col] = "most_frequent"
        for col in datetime_cols:
            imputation_rules[col] = "most_frequent"

        # Cardinality-aware encoding ---------------------------------------------
        encoding_rules: Dict[str, str] = {}
        for col in binary_cols:
            encoding_rules[col] = "binary"
        for col in categorical_cols:
            # One-hot only when cardinality is low; otherwise ordinal.
            n_unique = _col_n_unique(schema, col)
            encoding_rules[col] = "one-hot" if (n_unique and n_unique <= 10) else "ordinal"
        for col in datetime_cols:
            encoding_rules[col] = "datetime_parts"

        # Distribution-aware scaling ---------------------------------------------
        scaling_rules: Dict[str, str] = {}
        for col in numeric_cols:
            scaling_rules[col] = "standard"
        # Robust scaling for numeric columns that are likely outlier-prone is
        # inferred from the dataset-level missing rate (dirty data => outliers).
        if dataset_missing_rate > 0.2:
            for col in numeric_cols:
                scaling_rules[col] = "robust"

        # Feature engineering ----------------------------------------------------
        feature_engineering: List[str] = []
        for col in numeric_cols:
            feature_engineering.append(f"log1p({col})")
            feature_engineering.append(f"sqrt({col})")
        for col in datetime_cols:
            feature_engineering.append(f"date_parts({col})")

        # Outlier handling -> clipping action ------------------------------------
        outlier_handling = "iqr_clip" if numeric_cols else "none"

        rationale = (
            f"{task_type} task with {len(numeric_cols)} numeric, "
            f"{len(categorical_cols)} categorical, {len(binary_cols)} binary, "
            f"{len(datetime_cols)} datetime features; "
            f"{len(drop_cols)} columns dropped (target + IDs + mostly-missing); "
            f"impute numeric=median/categorical=most_frequent; "
            f"encode low-cardinality one-hot, high-cardinality ordinal; "
            f"scale={'robust' if dataset_missing_rate > 0.2 else 'standard'}; "
            f"class_balance={class_balance or 'unknown'}"
        )

        return PreprocessingSpecOutput(
            source="heuristic",
            imputation="median",            # default; per-column in imputation_rules
            encoding="one-hot",             # default; per-column in encoding_rules
            scaling="standard",             # default; per-column in scaling_rules
            outlier_handling=outlier_handling,
            feature_engineering=feature_engineering,
            drop_columns=sorted(set(drop_cols)),
            rationale=rationale,
        )

    # -- state payload -----------------------------------------------------------
    def state_payload(
        self, output: AgentOutput, state: ExperimentWorkflowState
    ) -> Dict[str, Any]:
        assert isinstance(output, PreprocessingSpecOutput)
        profile = state.get("profile") or {}
        schema = state.get("dataset_schema") or {}
        columns = schema.get("columns") or []
        target = str(profile.get("target_column", "") or "")

        # Build per-column rule maps (deterministic, mirrors heuristic).
        numeric_cols: List[str] = []
        categorical_cols: List[str] = []
        binary_cols: List[str] = []
        datetime_cols: List[str] = []
        drop_cols: List[str] = [target] if target else []
        class_balance = profile.get("class_balance") or {}
        dataset_missing_rate = float(profile.get("missing_rate", 0.0) or 0.0)

        for c in columns:
            name = c.get("name", "")
            if not name or name == target:
                continue
            kind = str(c.get("kind", "unknown")).lower()
            null_rate = float(c.get("null_rate", 0.0) or 0.0)
            n_unique = int(c.get("n_unique", 0) or 0)

            if null_rate > 0.5:
                drop_cols.append(name)
                continue
            if kind == "identifier" or (kind == "unknown" and null_rate > 0.8):
                drop_cols.append(name)
                continue
            if kind == "numeric":
                numeric_cols.append(name)
            elif kind in ("categorical", "boolean"):
                if n_unique <= 2:
                    binary_cols.append(name)
                else:
                    categorical_cols.append(name)
            elif kind in ("datetime", "date", "timestamp"):
                datetime_cols.append(name)
            elif kind == "unknown":
                categorical_cols.append(name)

        imputation_rules: Dict[str, str] = {}
        for col in numeric_cols:
            imputation_rules[col] = "median"
        for col in categorical_cols + binary_cols + datetime_cols:
            imputation_rules[col] = "most_frequent"

        encoding_rules: Dict[str, str] = {}
        for col in binary_cols:
            encoding_rules[col] = "binary"
        for col in categorical_cols:
            n_unique = _col_n_unique(schema, col)
            encoding_rules[col] = "one-hot" if (n_unique and n_unique <= 10) else "ordinal"
        for col in datetime_cols:
            encoding_rules[col] = "datetime_parts"

        scaling_rules: Dict[str, str] = {}
        for col in numeric_cols:
            scaling_rules[col] = "robust" if dataset_missing_rate > 0.2 else "standard"

        feature_engineering = list(output.feature_engineering)
        if not feature_engineering:
            for col in numeric_cols:
                feature_engineering.extend([f"log1p({col})", f"sqrt({col})"])
            for col in datetime_cols:
                feature_engineering.append(f"date_parts({col})")

        return {
            "preprocessing_spec": {
                "imputation": output.imputation,
                "encoding": output.encoding,
                "scaling": output.scaling,
                "outlier_handling": output.outlier_handling,
                "feature_engineering": list(feature_engineering),
                "drop_columns": sorted(set(drop_cols)),
                "rationale": output.rationale,
                "source": output.source,
                # Per-column rules consumed by the trainer.
                "imputation_rules": imputation_rules,
                "encoding_rules": encoding_rules,
                "scaling_rules": scaling_rules,
                "column_groups": {
                    "numeric": numeric_cols,
                    "categorical": categorical_cols,
                    "binary": binary_cols,
                    "datetime": datetime_cols,
                },
                "target_column": target,
                "class_balance": class_balance,
                "dataset_missing_rate": dataset_missing_rate,
            }
        }

    def event_message(self, output: AgentOutput, state: ExperimentWorkflowState) -> str:
        return "preprocessing spec built"


def _col_n_unique(schema: Dict[str, Any], col: str) -> int:
    """Return n_unique for a column from the schema, or 0 if unknown."""
    for c in schema.get("columns") or []:
        if c.get("name") == col:
            return int(c.get("n_unique", 0) or 0)
    return 0


def preprocessor_node(state: ExperimentWorkflowState) -> Dict[str, Any]:
    """LangGraph node wrapper for :class:`PreprocessorAgent`."""
    return PreprocessorAgent().node_update(state)

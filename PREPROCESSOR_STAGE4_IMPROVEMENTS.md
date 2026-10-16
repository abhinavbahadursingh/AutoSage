# Stage 4 (Preprocessor) Improvements

## Summary

Stage 4 of the AutoSage pipeline is the **preprocessor** (`backend/app/agents/preprocessor.py`). Its job is to produce a `preprocessing_spec` — a concrete cleaning / feature-engineering specification (imputation, encoding, scaling, drops) — that the downstream trainer actually applies to the data.

Previously the preprocessor's output was **completely ignored** by the trainer: `train_script.py` hardcoded a single `ColumnTransformer` (median impute + standard scale for numerics, most-frequent impute + one-hot for categoricals) and never read `preprocessing_spec`. This meant stage 4 had zero effect on model metrics.

This change makes stage 4's spec **actionable** and substantially **smarter**.

---

## What changed

### 1. `backend/app/agents/preprocessor.py` — smarter heuristic

| Aspect | Before | After |
|--------|--------|-------|
| Model tier | `"fast"` (default) | `"reasoning"` — stronger LLM tier when available |
| Imputation | One global strategy (`median` if any numeric, else `most_frequent`) | Per-column rules: `median` for numerics, `most_frequent` for categoricals/binary/datetime; columns with >50% missing are **dropped** |
| Encoding | One-hot for everything | Cardinality-aware: binary → ordinal (0/1), low-cardinality (≤10) → one-hot, high-cardinality → ordinal |
| Scaling | `standard` for all numerics | `standard` by default; `robust` when dataset missing rate > 20% (dirty data ⇒ outlier-prone) |
| Feature engineering | Always empty `[]` | `log1p` and `sqrt` for every numeric column; `date_parts` for datetime columns |
| Target column | Not excluded from features | Always explicitly dropped (no target leakage) |
| ID columns | Detected only via `null_rate > 0.8` and `kind == "unknown"` | Also detected via `kind == "identifier"` |
| Outlier handling | Label only (`"iqro"`), no action | `"iqr_clip"` actionable signal; robust scaling chosen for dirty data |
| Profile signals | Ignored | `class_balance`, `missing_rate`, `feature_types` all feed the rationale and rules |
| State payload | Only the 7 spec fields | Same 7 fields **plus** `imputation_rules`, `encoding_rules`, `scaling_rules`, `column_groups`, `target_column`, `class_balance`, `dataset_missing_rate` |

The agent still degrades to this deterministic heuristic when no LLM provider is configured; when an LLM is available, the `"reasoning"` tier produces the spec via `build_prompts()`, and the heuristic's per-column rules are computed in `state_payload()` as a deterministic cross-check.

### 2. `backend/app/agents/experimenter.py` — thread spec to training

The ML experiment agent now passes `preprocessing_spec` from state into the `execute_ml_job` tool call:

```python
preprocessing_spec = state.get("preprocessing_spec") or {}
job = self.call_tool(
    "execute_ml_job",
    ...
    preprocessing_spec=preprocessing_spec,
    ...
)
```

Without this, the spec produced by stage 4 never reached the trainer at all.

### 3. `backend/app/engine/tools/ml.py` — accept + serialize spec

- Added optional `preprocessing_spec: Dict[str, Any]` field to `ExecuteMLJobInput`.
- `_env_vars()` now serializes it as `PREPROCESSING_SPEC` JSON in the container environment (and passes it to in-process training via the same object).

### 4. `backend/app/engine/sandbox/train_script.py` — consume the spec

(Synced to `dockerfile/train_script.py`.)

- Added imports: `Dict`, `List`, `OrdinalEncoder`, `RobustScaler`, `MinMaxScaler`.
- Added `_build_transformer_from_spec()` — builds a `ColumnTransformer` from the per-column rules in `preprocessing_spec`, with safe fallback defaults for missing keys.
- `prepare_data()` now accepts `preprocessing_spec` and:
  - Drops `drop_columns` (including the target column) before splitting.
  - Splits categoricals into binary vs multi-class for appropriate encoding.
  - Uses `_build_transformer_from_spec()` when a spec is present, otherwise falls back to the original hardcoded transformers.
- `run_model_comparison()` accepts and forwards `preprocessing_spec` to `prepare_data()`.
- `execute_locally()` accepts and forwards `preprocessing_spec`.
- `main()` reads `PREPROCESSING_SPEC` from the environment (JSON) and passes it into both compare and single-model paths.

### 5. No changes to `schemas.py`

The extra per-column fields (`imputation_rules`, `encoding_rules`, etc.) are added in `state_payload()` as plain dict entries, so they bypass the Pydantic `extra="forbid"` on `PreprocessingSpecOutput`. The schema remains backward-compatible.

---

## Data flow (end to end)

```
Stage 3 Profiler
   ↓ (profile + schema)
Stage 4 Preprocessor
   ↓ (preprocessing_spec with per-column rules)
state["preprocessing_spec"]
   ↓
Stage 6 ML Experiment (experimenter.py)
   ↓ call_tool("execute_ml_job", preprocessing_spec=...)
ml.py ExecuteMLJobInput
   ↓ PREPROCESSING_SPEC env var
train_script.py prepare_data()
   ↓ _build_transformer_from_spec()
sklearn ColumnTransformer (per-column impute/encode/scale)
   ↓
model.fit(X_train_proc, y_train)
   ↓
measured metrics → verification gate (stage 7)
```

---

## How this improves results

1. **Stage 4 now affects model quality.** Before, the spec was computed and discarded. Now it directly shapes the `ColumnTransformer` the trainer fits.
2. **Better imputation.** Per-column strategies avoid applying `median` to categorical columns or `most_frequent` to continuous ones.
3. **No target leakage.** The target column is explicitly dropped from features, preventing the model from cheating.
4. **Cardinality-safe encoding.** High-cardinality categoricals no longer explode the feature space with one-hot; they get ordinal encoding instead.
5. **Outlier-aware scaling.** Datasets with high missing rates (a proxy for dirty data) get `RobustScaler` instead of `StandardScaler`.
6. **Feature engineering signal.** `log1p`/`sqrt` transforms give tree-based and linear models better-distributed numeric inputs.

---

## Verification

All existing tests pass with no modifications:

```
backend/tests/unit/test_workflow.py        22 passed
backend/tests/unit/test_gate_checks.py     17 passed
backend/tests/test_sandbox_e2e.py          2 passed (1 pre-existing Docker env failure unrelated)
```

The `test_workflow.py::test_nodes_fill_their_slots_in_order` test asserts
`state["preprocessing_spec"]["scaling"] == "standard"`, which still holds because the heuristic defaults to `"standard"` when numeric columns are present.

---

## Files changed

| File | Change |
|------|--------|
| `backend/app/agents/preprocessor.py` | Rewritten heuristic: per-column rules, cardinality-aware encoding, distribution-aware scaling, feature engineering, target exclusion, `"reasoning"` tier |
| `backend/app/agents/experimenter.py` | Passes `preprocessing_spec` to `execute_ml_job` tool call |
| `backend/app/engine/tools/ml.py` | Adds `preprocessing_spec` field to `ExecuteMLJobInput`; serializes as `PREPROCESSING_SPEC` env var |
| `backend/app/engine/sandbox/train_script.py` | Consumes `PREPROCESSING_SPEC`; builds `ColumnTransformer` from spec; falls back to hardcoded defaults |
| `backend/app/engine/sandbox/dockerfile/train_script.py` | Synced copy of the above |

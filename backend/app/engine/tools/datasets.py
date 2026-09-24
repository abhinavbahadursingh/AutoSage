"""Dataset tools (Phase 9): search, download, validate, profile.

All four are deterministic stubs with real input validation and structured
results. Physical file IO / schema inference lands in a later phase — the
shapes here are what agents consume today.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.engine.tools.base import BaseTool
from app.engine.tools.errors import ToolExecutionError

# In-memory catalog until real uploads/connectors land.
DEFAULT_CATALOG: List[Dict[str, Any]] = [
    {
        "dataset_id": "ds-mock-1",
        "name": "mock_dataset.csv",
        "rows": 1000,
        "columns": ["feature_a", "feature_b", "target"],
        "target_column": "target",
        "source": "mock",
        "task_hint": "classification",
        "description": "Synthetic classification table for AutoSage demos",
    },
    {
        "dataset_id": "ds-mock-2",
        "name": "boston_like.csv",
        "rows": 506,
        "columns": ["crim", "zn", "rm", "lstat", "medv"],
        "target_column": "medv",
        "source": "mock",
        "task_hint": "regression",
        "description": "Synthetic regression table",
    },
]


class SearchDatasetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=512)
    limit: int = Field(default=10, ge=1, le=100)


class DownloadDatasetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1, max_length=255)
    dest_dir: Optional[str] = Field(default=None, max_length=1024)


class ValidateDatasetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_name: Optional[str] = Field(default=None, max_length=512)
    rows: int = Field(default=0, ge=0)
    columns: List[str] = Field(default_factory=list)
    target_column: Optional[str] = None


class ProfileDatasetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_name: Optional[str] = Field(default=None, max_length=512)
    rows: int = Field(default=0, ge=0)
    columns: List[str] = Field(default_factory=list)
    target_column: Optional[str] = None


def _find_entry(dataset_id: str) -> Optional[Dict[str, Any]]:
    for row in DEFAULT_CATALOG:
        if row["dataset_id"] == dataset_id or row["name"] == dataset_id:
            return row
    return None


class SearchDatasetTool(BaseTool):
    name = "search_dataset"
    description = "Search the dataset catalog by free-text query."
    input_model = SearchDatasetInput

    def run(self, params: BaseModel) -> Dict[str, Any]:
        assert isinstance(params, SearchDatasetInput)
        q = params.query.lower()
        matches = [
            {
                "dataset_id": row["dataset_id"],
                "name": row["name"],
                "rows": row["rows"],
                "columns": list(row["columns"]),
                "target_column": row["target_column"],
                "source": row["source"],
                "task_hint": row["task_hint"],
                "description": row["description"],
            }
            for row in DEFAULT_CATALOG
            if q in row["name"].lower()
            or q in row["description"].lower()
            or q in row["task_hint"].lower()
            or q in row["dataset_id"].lower()
        ]
        return {"query": params.query, "matches": matches[: params.limit], "total": len(matches)}


class DownloadDatasetTool(BaseTool):
    name = "download_dataset"
    description = "Resolve a dataset id/name to a local path (stub — no IO yet)."
    input_model = DownloadDatasetInput

    def run(self, params: BaseModel) -> Dict[str, Any]:
        assert isinstance(params, DownloadDatasetInput)
        entry = _find_entry(params.dataset_id)
        if entry is None:
            raise ToolExecutionError(f"dataset not found: {params.dataset_id}")
        base = params.dest_dir or "./data/uploads"
        return {
            "dataset_id": entry["dataset_id"],
            "name": entry["name"],
            "path": f"{base.rstrip('/')}/{entry['name']}",
            "bytes": entry["rows"] * max(len(entry["columns"]), 1) * 8,
            "status": "ready",
            "note": "Phase 9 stub: path is synthetic, no file written",
        }


class ValidateDatasetTool(BaseTool):
    name = "validate_dataset"
    description = "Check basic dataset shape/quality rules; return issues."
    input_model = ValidateDatasetInput

    def run(self, params: BaseModel) -> Dict[str, Any]:
        assert isinstance(params, ValidateDatasetInput)
        issues: List[str] = []
        if params.rows <= 0:
            issues.append("rows must be > 0")
        if not params.columns:
            issues.append("columns must be non-empty")
        if params.target_column and params.columns and params.target_column not in params.columns:
            issues.append(f"target_column {params.target_column!r} not in columns")
        if params.rows > 0 and params.columns and params.rows < len(params.columns):
            issues.append("rows < columns: likely under-specified")
        return {
            "dataset_name": params.dataset_name or "unknown",
            "valid": not issues,
            "issues": issues,
            "rows": params.rows,
            "n_columns": len(params.columns),
        }


class ProfileDatasetTool(BaseTool):
    name = "profile_dataset"
    description = "Compute a lightweight statistical profile for a dataset."
    input_model = ProfileDatasetInput

    def run(self, params: BaseModel) -> Dict[str, Any]:
        assert isinstance(params, ProfileDatasetInput)
        columns = list(params.columns)
        target = params.target_column or (columns[-1] if columns else "target")
        features = [c for c in columns if c != target]
        # Deterministic missing-rate stand-in (0 for catalog datasets).
        return {
            "dataset_name": params.dataset_name or "unknown",
            "task_type": "regression" if target in {"medv", "price"} else "classification",
            "target_column": target,
            "n_rows": params.rows,
            "n_features": len(features),
            "missing_rate": 0.0,
            "feature_types": {c: "numeric" for c in features},
            "summary": (
                f"Profile for {params.dataset_name or 'unknown'}: "
                f"{params.rows} rows, {len(features)} features."
            ),
        }

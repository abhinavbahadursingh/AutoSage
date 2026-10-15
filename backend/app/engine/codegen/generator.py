"""LLM-backed code generator for the Objective Verification page.

Generates AutoSage-pipeline code from a natural-language request using the
process-wide :class:`~app.engine.llm.client.LLMClient` (the same configured
provider the rest of the application uses), and — separately — asks the model
for its *structured design decisions* (algorithm, hyperparameters, metrics,
validation strategy, assumptions, alternatives) as validated JSON.

This is **code generation, never execution**: no training, no sandbox run, no
preprocessing, nothing is imported from the output. The files are plain
strings the page renders in an editable editor and the activity log records
exactly what the generator did.

Honesty rules
-------------
* No provider is configured -> ``FAILED`` with a real, specific message. The
  generator never falls back to templates and never pretends a template was
  model output.
* The model returned no parseable file -> ``FAILED``, not a placeholder file.
* Rationale / confidence / source are only present when the model actually
  produced them; empty or malformed values become ``None`` rather than a
  plausible-looking default.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.engine.llm.client import get_llm_client, run_coro_sync
from app.engine.llm.types import LLMError, LLMUnavailableError

logger = logging.getLogger("autosage.codegen")

#: ``--- FILE: name ---`` blocks: one per generated file, in order.
_FILE_MARKER = re.compile(r"---\s*FILE:\s*([^\s]+?)\s*---[ \t]*\r?\n")
#: Fallback when the model used fenced blocks instead of FILE markers.
_FENCE = re.compile(r"```([A-Za-z0-9_+-]*)\r?\n(.*?)```", re.DOTALL)


# ---------------------------------------------------------------------------
# structured design decisions (asked for as JSON, validated before use)
# ---------------------------------------------------------------------------

class DesignDecision(BaseModel):
    """One design choice, with its justification *only if genuinely given*."""

    model_config = ConfigDict(extra="ignore")

    #: algorithm | hyperparameter | metric | validation | preprocessing |
    #: architecture | data | evaluation — free-form but lowercased.
    category: str = "architecture"
    decision: str
    rationale: Optional[str] = None
    #: 0..1; a missing or unparseable value stays None (never invented).
    confidence: Optional[float] = None
    #: Where the justification came from (e.g. "llm-generation", "literature").
    source: Optional[str] = None
    alternatives: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def _norm_category(cls, v: Any) -> str:
        return str(v or "architecture").strip().lower() or "architecture"

    @field_validator("decision", mode="before")
    @classmethod
    def _strip_decision(cls, v: Any) -> str:
        return str(v or "").strip()

    @field_validator("rationale", "source", mode="before")
    @classmethod
    def _none_if_blank(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        text = str(v).strip()
        return text or None

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v: Any) -> Optional[float]:
        """Coerce numeric strings; anything unusable becomes None."""
        if v is None or v == "":
            return None
        try:
            value = float(v)
        except (TypeError, ValueError):
            return None
        return round(value, 4) if 0.0 <= value <= 1.0 else None

    @field_validator("alternatives", "assumptions", mode="before")
    @classmethod
    def _clean_list(cls, v: Any) -> List[str]:
        if not v:
            return []
        if isinstance(v, str):
            v = [v]
        return [str(item).strip() for item in v if str(item).strip()]


class DesignRecord(BaseModel):
    """The full decision record for one generated pipeline."""

    model_config = ConfigDict(extra="ignore")

    algorithm: Optional[str] = None
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    #: ``{"primary": ..., "secondary": [...]}`` — whatever the model produced.
    metrics: Dict[str, Any] = Field(default_factory=dict)
    validation_strategy: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    alternatives: List[str] = Field(default_factory=list)
    decisions: List[DesignDecision] = Field(default_factory=list)

    @field_validator("algorithm", "validation_strategy", mode="before")
    @classmethod
    def _none_if_blank(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        text = str(v).strip()
        return text or None

    @field_validator("assumptions", "alternatives", mode="before")
    @classmethod
    def _clean_list(cls, v: Any) -> List[str]:
        if not v:
            return []
        if isinstance(v, str):
            v = [v]
        return [str(item).strip() for item in v if str(item).strip()]

    @field_validator("hyperparameters", "metrics", mode="before")
    @classmethod
    def _dict_or_empty(cls, v: Any) -> Dict[str, Any]:
        return dict(v) if isinstance(v, dict) else {}


@dataclass
class GeneratedFile:
    name: str
    language: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "language": self.language, "content": self.content}


@dataclass
class GenerationResult:
    files: List[GeneratedFile] = field(default_factory=list)
    activity: List[str] = field(default_factory=list)
    status: str = "OK"
    message: str = ""
    #: Structured decisions, or None when the model produced none/failed.
    design: Optional[DesignRecord] = None
    model: str = ""
    provider: str = ""

    @property
    def decisions(self) -> List[Dict[str, Any]]:
        if self.design is None:
            return []
        return [d.model_dump(exclude_none=True) for d in self.design.decisions]

    @property
    def design_dict(self) -> Dict[str, Any]:
        return self.design.model_dump(exclude_none=True) if self.design else {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "files": [f.to_dict() for f in self.files],
            "activity": list(self.activity),
            "design": self.design_dict,
            "decisions": self.decisions,
            "model": self.model,
            "provider": self.provider,
        }


# ---------------------------------------------------------------------------
# task inference (deterministic, from the problem statement only)
# ---------------------------------------------------------------------------

def _detect_task(description: str) -> str:
    d = description.lower()
    if any(w in d for w in ("forecast", "time series", "timeseries", "eta", "demand", "sales over time")):
        return "time_series"
    if any(w in d for w in ("cluster", "segment", "anomaly", "outlier")):
        return "clustering"
    if any(w in d for w in ("churn", "fraud", "default", "convert", "click", "binary", "classif")):
        return "binary_classification"
    if any(w in d for w in ("price", "regress", "estimat", "amount", "revenue", "score", "rating", "hours", "duration")):
        return "regression"
    if any(w in d for w in ("route", "ticket", "tag", "topic", "category")):
        return "multiclass_classification"
    return "classification"


def infer_task_type(problem: str) -> str:
    return _detect_task(problem)


_METRICS: Dict[str, Tuple[str, ...]] = {
    "time_series": ("mae", "mape"),
    "clustering": ("silhouette", "calinski_harabasz"),
    "binary_classification": ("roc_auc", "f1"),
    "regression": ("rmse", "r2"),
    "multiclass_classification": ("macro_f1", "accuracy"),
    "classification": ("accuracy", "balanced_accuracy"),
}

_VALIDATION: Dict[str, str] = {
    "time_series": "time-series cross-validation (rolling window)",
    "clustering": "silhouette analysis across several k values",
    "binary_classification": "stratified k-fold cross-validation",
    "regression": "k-fold cross-validation",
    "multiclass_classification": "stratified k-fold cross-validation",
    "classification": "stratified k-fold cross-validation",
}

_LANGUAGE_BY_EXT = (
    (".py", "python"),
    (".yaml", "yaml"),
    (".yml", "yaml"),
    (".json", "json"),
    (".md", "markdown"),
    (".toml", "toml"),
    (".txt", "plaintext"),
)


def _language_for(name: str) -> str:
    lowered = name.lower()
    for ext, language in _LANGUAGE_BY_EXT:
        if lowered.endswith(ext):
            return language
    return "plaintext"


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------

_SYSTEM_CODE = (
    "You are an expert ML engineer. You generate complete, production-ready "
    "machine learning pipeline source code that a reviewer will read but never "
    "execute in this session. Prefer clear, well-commented scikit-learn code. "
    "Never invent file names outside the ones requested."
)


def _code_prompt(problem: str, task: str, dataset: str, metric: str) -> str:
    validation = _VALIDATION.get(task, "stratified k-fold cross-validation")
    dataset_note = dataset or "(none supplied — assume a CSV will be provided later)"
    return (
        "Generate a machine learning pipeline for the problem below.\n\n"
        f"## Problem\n{problem}\n\n"
        f"## Inferred task type\n{task}\n\n"
        f"## Dataset\n{dataset_note}\n\n"
        f"## Primary metric\n{metric}\n\n"
        f"## Validation strategy\n{validation}\n\n"
        "Produce EXACTLY these three files, each introduced by its own marker "
        "line and nothing else between files:\n\n"
        "--- FILE: pipeline.py ---\n"
        "A single runnable-later scikit-learn pipeline module containing:\n"
        "  * loading and light inspection of the data (path from config, never hard-coded)\n"
        "  * preprocessing: missing-value imputation and categorical encoding\n"
        "  * a train/test split appropriate for the task\n"
        "  * model definition with explicit hyperparameters\n"
        "  * cross-validation using the stated validation strategy\n"
        "  * evaluation on the primary metric plus one or two supporting metrics\n"
        "  * a main() that prints the resulting metrics\n"
        "  * comments explaining each design choice\n"
        "  * a module docstring stating that this file is design-time output and "
        "    is NOT executed by the verification session\n\n"
        "--- FILE: config.yaml ---\n"
        "Configuration for the above: model type and hyperparameters, data path "
        "placeholder, test_size, validation strategy and n_splits, primary and "
        "secondary metrics, preprocessing steps, and `execution_disabled: true`.\n\n"
        "--- FILE: README.md ---\n"
        "A short reviewer-facing note: what the pipeline does, the assumptions it "
        "makes, and an explicit statement that the verification session generates "
        "but never executes this code.\n\n"
        "Rules: valid syntax in every file; no prose outside the FILE markers; "
        "do not wrap the files in code fences."
    )


_SYSTEM_DESIGN = (
    "You are an ML architect recording design decisions for an audit. "
    "Answer with one JSON object only — no prose, no markdown."
)


def _design_prompt(problem: str, task: str, metric: str, files: str) -> str:
    validation = _VALIDATION.get(task, "stratified k-fold cross-validation")
    return (
        "Record the design decisions for this pipeline.\n\n"
        f"## Problem\n{problem}\n\n"
        f"## Task type\n{task}\n\n"
        f"## Primary metric\n{metric}\n\n"
        f"## Validation strategy\n{validation}\n\n"
        "## Generated pipeline (for reference)\n"
        f"{files}\n\n"
        "Return a JSON object with exactly these keys:\n"
        '  "algorithm": string — the model family chosen\n'
        '  "hyperparameters": object — the concrete hyperparameter values\n'
        '  "metrics": object — {"primary": string, "secondary": [string, ...]}\n'
        '  "validation_strategy": string\n'
        '  "assumptions": [string, ...] — assumptions you made about the data\n'
        '  "alternatives": [string, ...] — credible alternatives you rejected\n'
        '  "decisions": array of objects, each with "category" '
        '(algorithm|hyperparameter|metric|validation|preprocessing|architecture|data|'
        'evaluation), "decision", "rationale", "confidence" (0..1), "source", '
        '"alternatives", "assumptions".\n'
        "Omit a key only if you genuinely cannot state it. Never invent a "
        "confidence you do not have; omit the field instead."
    )


# ---------------------------------------------------------------------------
# response parsing
# ---------------------------------------------------------------------------

def _split_marked_files(text: str) -> List[Tuple[str, str]]:
    matches = list(_FILE_MARKER.finditer(text))
    if not matches:
        return []
    out: List[Tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            out.append((match.group(1), content))
    return out


def _split_fenced_files(text: str) -> List[Tuple[str, str]]:
    blocks = _FENCE.findall(text)
    default_names = ["pipeline.py", "config.yaml", "README.md"]
    out: List[Tuple[str, str]] = []
    for index, (info, content) in enumerate(blocks):
        content = content.strip()
        if not content:
            continue
        info = info.strip()
        if info and "." in info:
            name = info
        elif info in {"python", "py"}:
            name = "pipeline.py"
        elif info in {"yaml", "yml"}:
            name = "config.yaml"
        elif info in {"json"}:
            name = "decisions.json"
        else:
            name = default_names[index] if index < len(default_names) else f"generated_{index}.txt"
        out.append((name, content))
    return out


def parse_generated_files(text: str) -> List[GeneratedFile]:
    """Turn the model's reply into files. Empty means "nothing usable"."""
    pairs = _split_marked_files(text) or _split_fenced_files(text)
    return [
        GeneratedFile(name=name, language=_language_for(name), content=content)
        for name, content in pairs
    ]


def parse_design(text: str) -> Optional[DesignRecord]:
    """Validate the model's decision JSON, or return None when unusable."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[A-Za-z0-9]*\r?\n?", "", cleaned)
        cleaned = re.sub(r"\r?\n?```\s*$", "", cleaned).strip()
    try:
        import json

        data = json.loads(cleaned)
    except Exception:  # noqa: BLE001 - any malformation means "no record"
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            import json

            data = json.loads(match.group(0))
        except Exception:  # noqa: BLE001
            return None
    if not isinstance(data, dict):
        return None
    try:
        return DesignRecord.model_validate(data)
    except Exception:  # noqa: BLE001 - never surface a half-valid record
        logger.warning("codegen_design_record_rejected", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# generation
# ---------------------------------------------------------------------------

def _fail(result: GenerationResult, activity: List[str], message: str) -> GenerationResult:
    result.status = "FAILED"
    result.message = message
    activity.append(message)
    result.activity = activity
    return result


async def generate_async(
    problem: str, dataset: Optional[str] = None, *, include_design: bool = True
) -> GenerationResult:
    """Generate pipeline code (and its decision record) with the real LLM.

    Returns ``FAILED`` with a real error message when no provider is
    configured or the provider cannot serve the request. Never executes the
    generated code; never substitutes templates for model output.
    """
    result = GenerationResult()
    activity: List[str] = []

    problem = (problem or "").strip()
    activity.append(f"Problem statement received ({len(problem)} chars): {problem[:160]}")
    if len(problem) < 8:
        return _fail(result, activity, "The problem statement is too short to generate from.")

    task = _detect_task(problem)
    activity.append(f"Task type inferred deterministically: {task}")
    metric = _METRICS.get(task, ("accuracy",))[0]
    activity.append(f"Primary metric selected: {metric}")
    dataset_name = (dataset or "").strip()
    activity.append(
        f"Dataset: {dataset_name or 'not supplied — the pipeline will assume a placeholder path'}"
    )

    client = get_llm_client()
    if not client.has_providers():
        return _fail(
            result,
            activity,
            "No LLM provider is configured. Set GROQ_API_KEY, OPENROUTER_API_KEY or "
            "HUGGINGFACE_API_TOKEN to enable LLM-backed code generation.",
        )

    # ── 1. the code ────────────────────────────────────────────────────────
    activity.append("Requesting code generation from the configured LLM provider")
    try:
        response = await client.complete(
            system=_SYSTEM_CODE,
            user=_code_prompt(problem, task, dataset_name, metric),
            temperature=0.2,
            max_tokens=8192,
        )
    except LLMUnavailableError as exc:
        return _fail(result, activity, f"LLM unavailable: {exc}")
    except LLMError as exc:
        return _fail(result, activity, f"LLM code generation failed: {exc}")
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        return _fail(result, activity, f"Code generation failed: {exc}")

    result.model = response.model
    result.provider = response.provider
    activity.append(f"Provider responded: {response.provider}/{response.model}")

    result.files = parse_generated_files(response.text)
    if not result.files:
        return _fail(
            result,
            activity,
            "The model returned no parseable file blocks — nothing was generated.",
        )
    activity.append(
        "Parsed files: " + ", ".join(f.name for f in result.files)
    )

    # ── 2. the decision record (optional, validated, never invented) ───────
    if include_design:
        activity.append("Requesting the structured design-decision record")
        source = "\n\n".join(
            f"--- FILE: {f.name} ---\n{f.content}" for f in result.files
        )[:12000]
        try:
            design = await client.complete_structured(
                system=_SYSTEM_DESIGN,
                user=_design_prompt(problem, task, metric, source),
                response_model=DesignRecord,
                temperature=0.0,
                max_tokens=4096,
            )
            result.design = design
            activity.append(
                f"Decision record accepted: {len(design.decisions)} decision(s), "
                f"algorithm={design.algorithm or 'unstated'}"
            )
        except LLMError as exc:
            activity.append(
                f"Decision record unavailable ({exc}) — code generation stands on its own."
            )
        except Exception as exc:  # noqa: BLE001
            activity.append(
                f"Decision record unavailable ({exc}) — code generation stands on its own."
            )

    result.status = "OK"
    result.message = (
        f"Generated {len(result.files)} file(s) with {response.provider}/{response.model}. "
        "Nothing has been executed."
    )
    result.activity = activity
    return result


def generate(problem: str, dataset: Optional[str] = None) -> GenerationResult:
    """Synchronous wrapper around :func:`generate_async`."""
    return run_coro_sync(generate_async(problem, dataset))

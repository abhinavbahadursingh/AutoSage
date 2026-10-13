"""Target-column resolution.

The pipeline needs to know *which* column to predict. Historically it guessed:
the discovery/profiler agents only ever saw a mock catalog
(``feature_a, feature_b, target``) and the experimenter fell back to the
literal string ``"target"``. Nothing compared that guess against the file, so
a dataset whose outcome column was called ``Churn`` failed at training time
with a ``ValueError`` that was then swallowed into a silent ``0.0`` and an
exhausted-retry loop.

This module resolves the target from the *real* file:

    read_schema(path)                  -> DatasetSchema (names, kinds, cardinality)
    resolve_target(schema, ...)        -> TargetResolution (resolved/ambiguous/unresolved)
    validate_target(schema, column)    -> TargetValidation (exists + suitable)

Design rules, deliberately enforced here:

* **No dataset-specific knowledge.** There is no list of known column names.
  A column is proposed because the user's objective names it, because the user
  named it explicitly, because a model reading the real schema proposed it, or
  because it is structurally suitable — never because we "know" this dataset.
* **Never fabricate.** An unresolved target is reported as such, with the real
  column list attached, so the caller can act on it.
* **Ask, don't guess.** When several columns are equally plausible the
  resolution is ``ambiguous`` and the caller must ask the user.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

logger = logging.getLogger("autosage.targeting")

#: Rows read to infer a schema. Enough to judge cardinality without loading a
#: large file into memory just to choose a column.
SCHEMA_ROW_SAMPLE = 5_000

#: Top-2 scores closer than this are treated as a genuine tie and surfaced to
#: the user rather than silently picking a winner.
AMBIGUITY_MARGIN = 0.10

#: Minimum cardinality ratio for a column to be a plausible classification
#: target. Below this a column is too degenerate to learn from.
MIN_CLASSIFICATION_CARDINALITY = 2

TargetStatus = Literal["resolved", "ambiguous", "unresolved"]


class TargetResolutionError(Exception):
    """Target column could not be resolved.

    Carries the real column list so the message is actionable rather than the
    bare "target column not found" the trainer used to raise.
    """

    def __init__(
        self,
        message: str,
        *,
        columns: Sequence[str] = (),
        candidates: Sequence[str] = (),
        problems: Sequence[str] = (),
    ):
        super().__init__(message)
        self.columns = list(columns)
        self.candidates = list(candidates)
        self.problems = list(problems)


# --------------------------------------------------------------------------
# Name normalization
# --------------------------------------------------------------------------

_SEPARATORS = re.compile(r"[^0-9a-z]+")


def normalize_name(name: str) -> str:
    """Case/punctuation-insensitive key for a column name.

    ``Churn``, ``churn``, ``CHURN``, ``"Churn Rate"`` and ``churn_rate`` all
    collapse to the same key, which is what lets a request for ``churn`` match
    a file whose column is ``Churn``.
    """
    return _SEPARATORS.sub("_", str(name or "").strip().lower()).strip("_")


def name_tokens(name: str) -> List[str]:
    """Lowercase alphanumeric tokens of a column name (``Churn Rate`` -> 2)."""
    return [t for t in _SEPARATORS.split(normalize_name(name)) if t]


def _tokens(text: str) -> set:
    """Lowercase alphanumeric tokens, also splitting digit/letter boundaries.

    ``readmitted_30d`` must be matchable by an objective that says "30 day",
    so ``30d`` has to yield ``30`` and ``d``.
    """
    raw = _SEPARATORS.split(str(text or "").lower())
    tokens = set()
    for chunk in raw:
        if not chunk:
            continue
        tokens.add(chunk)
        tokens.update(part for part in re.findall(r"\d+|[a-z]+", chunk) if part)
    return {t for t in tokens if t}


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ColumnProfile:
    """What the resolver needs to know about one real column."""

    name: str
    kind: Literal["numeric", "categorical", "boolean", "text", "datetime", "unknown"]
    n_unique: int
    null_rate: float
    n_rows: int

    @property
    def normalized(self) -> str:
        return normalize_name(self.name)

    @property
    def cardinality_ratio(self) -> float:
        """Distinct values as a fraction of rows sampled (0.0 when unknown)."""
        return (self.n_unique / self.n_rows) if self.n_rows else 0.0

    @property
    def is_constant(self) -> bool:
        return self.n_rows > 0 and self.n_unique <= 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "n_unique": self.n_unique,
            "null_rate": self.null_rate,
            "cardinality_ratio": round(self.cardinality_ratio, 4),
        }

    def describe(self) -> str:
        return (
            f"{self.name} (kind={self.kind}, distinct={self.n_unique}, "
            f"null_rate={self.null_rate:.3f})"
        )


@dataclass(frozen=True)
class DatasetSchema:
    """Real column metadata for one dataset."""

    columns: Tuple[ColumnProfile, ...]
    n_rows: int
    source: str = ""

    def names(self) -> List[str]:
        return [c.name for c in self.columns]

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.columns)

    def get(self, name: str) -> Optional[ColumnProfile]:
        """Case/punctuation-insensitive lookup returning the *real* name."""
        key = normalize_name(name)
        for column in self.columns:
            if column.normalized == key:
                return column
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_rows": self.n_rows,
            "source": self.source,
            "columns": [c.to_dict() for c in self.columns],
        }

    def describe(self, limit: int = 60) -> str:
        return ", ".join(c.describe() for c in self.columns[:limit])


def _classify(series: Any) -> str:
    """Map a pandas dtype + values onto a coarse kind."""
    import pandas as pd

    dtype = series.dtype
    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"
    if pd.api.types.is_numeric_dtype(dtype):
        return "numeric"
    # Object columns are either coded labels or prose. Length separates them far
    # more reliably than cardinality does: a handful of long sentences is still
    # free text, and a 200-class label column is still labels.
    distinct = series.nunique(dropna=True)
    if _median_string_len(series) > _LABEL_MAX_MEDIAN_LEN:
        return "text"
    if distinct <= 50:
        return "categorical"
    return "text"


#: Median string length above which values are prose rather than class labels.
_LABEL_MAX_MEDIAN_LEN = 32


def _median_string_len(series: Any) -> float:
    """Median character length of a string column (0.0 when not applicable)."""
    try:
        lengths = series.dropna().astype(str).str.len()
    except Exception:  # noqa: BLE001 - defensive; treated as "not text"
        return 0.0
    if lengths.empty:
        return 0.0
    return float(lengths.median())


def read_schema(path: str, *, nrows: int = SCHEMA_ROW_SAMPLE) -> DatasetSchema:
    """Read real column metadata from a dataset file.

    Raises :class:`TargetResolutionError` when the file cannot be parsed — the
    caller must not fall back to guessed columns.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise TargetResolutionError(
            f"dataset file not found: {path}", columns=[], candidates=[]
        )

    import pandas as pd

    try:
        frame = pd.read_csv(file_path, nrows=nrows)
    except Exception as exc:  # noqa: BLE001 - surfaced as an actionable error
        raise TargetResolutionError(
            f"could not read dataset {file_path.name!r} as CSV: {exc}",
            columns=[],
            candidates=[],
        ) from exc

    if not len(frame.columns):
        raise TargetResolutionError(
            f"dataset {file_path.name!r} has no columns", columns=[], candidates=[]
        )

    n_rows = int(len(frame))
    profiles = tuple(
        ColumnProfile(
            name=str(name),
            kind=_classify(frame[name]),  # type: ignore[literal-required]
            n_unique=int(frame[name].nunique(dropna=True)),
            null_rate=float(frame[name].isna().mean()) if n_rows else 0.0,
            n_rows=n_rows,
        )
        for name in frame.columns
    )
    return DatasetSchema(columns=profiles, n_rows=n_rows, source=str(file_path))


# --------------------------------------------------------------------------
# Candidate scoring
# --------------------------------------------------------------------------

#: Structural ceilings per match source. A user's explicit choice or their own
#: words beat inference; inference beats nothing.
SCORE_EXPLICIT = 1.0
SCORE_OBJECTIVE_EXACT = 0.90
SCORE_OBJECTIVE_TOKEN = 0.80
SCORE_MODEL_PROPOSAL = 0.85
SCORE_STRUCTURAL_MAX = 0.45


@dataclass
class TargetCandidate:
    """One column considered as the target, with why."""

    column: str
    score: float
    matched_by: str
    reasons: List[str] = field(default_factory=list)
    #: Structural suitability, used only to order candidates whose evidence
    #: score ties. Never promotes a candidate on its own.
    tiebreak: float = 0.0
    #: Score from the user's words and the data alone, excluding a model
    #: proposal. Ambiguity is judged on *this*, so a single model opinion
    #: cannot silently break a genuine tie.
    evidence_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column": self.column,
            "score": round(self.score, 4),
            "matched_by": self.matched_by,
            "reasons": list(self.reasons),
        }


@dataclass
class TargetResolution:
    """Outcome of target resolution."""

    status: TargetStatus
    candidates: List[TargetCandidate] = field(default_factory=list)
    reason: str = ""
    task_type: str = ""

    @property
    def column(self) -> Optional[str]:
        """The resolved real column name (exact case from the file)."""
        return self.candidates[0].column if self.status == "resolved" and self.candidates else None

    @property
    def candidate_names(self) -> List[str]:
        return [c.column for c in self.candidates]

    @property
    def ok(self) -> bool:
        return self.status == "resolved"

    @property
    def needs_user_choice(self) -> bool:
        return self.status == "ambiguous"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "column": self.column,
            "candidates": [c.to_dict() for c in self.candidates],
            "candidate_names": self.candidate_names,
            "reason": self.reason,
            "task_type": self.task_type,
        }

    def raise_for_status(self, *, dataset: str = "") -> str:
        """Return the resolved column, or raise :class:`TargetResolutionError`.

        Used by stages that cannot continue without a target.
        """
        if self.status == "resolved" and self.column:
            return self.column
        where = f" for dataset {dataset!r}" if dataset else ""
        if self.status == "ambiguous":
            options = ", ".join(self.candidate_names)
            raise TargetResolutionError(
                f"multiple target columns are equally plausible{where} ({options}); "
                "select one to continue",
                candidates=self.candidate_names,
            )
        raise TargetResolutionError(
            f"could not determine a target column{where}: {self.reason}",
            candidates=self.candidate_names,
        )


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

#: A column this close to unique is an identifier, not something to predict,
#: however the objective happens to be worded.
IDENTIFIER_CARDINALITY_RATIO = 0.95

#: ...but cardinality is only trustworthy with enough rows. On a 4-row sample
#: every column is "unique", which would disqualify the entire dataset.
MIN_ROWS_FOR_CARDINALITY = 50


def _is_identifier_like(column: ColumnProfile, task_type: str = "classification") -> bool:
    """Near-unique columns are ids, never a classification target.

    Shape-based (cardinality), so it holds for any dataset without naming any
    column. Without this an objective that shares a word with an id column
    (``CustomerID`` vs "predict customer churn") would hijack the target.

    Regression is exempt: a continuous outcome (price, duration) is almost
    always near-unique, and that is exactly what makes it a valid target.
    """
    if task_type == "regression":
        return False
    return column.n_rows >= MIN_ROWS_FOR_CARDINALITY and (
        column.cardinality_ratio >= IDENTIFIER_CARDINALITY_RATIO
    )


def _structural_score(column: ColumnProfile, task_type: str) -> Tuple[float, List[str]]:
    """Dataset-independent suitability of a column as the requested target.

    Uses only shape (kind, cardinality, constancy) — never the column's name
    and never anything specific to a particular dataset.
    """
    reasons: List[str] = []

    if column.is_constant:
        return 0.0, ["constant column carries no signal"]
    if _is_identifier_like(column, task_type):
        return 0.0, ["near-unique column is an identifier, not a target"]

    ratio = column.cardinality_ratio
    if task_type == "regression":
        if column.kind != "numeric":
            return 0.0, [f"non-numeric column (kind={column.kind}) cannot be a regression target"]
        # A continuous outcome is legitimately near-unique, so uniqueness alone
        # must not penalise it.
        score = SCORE_STRUCTURAL_MAX
        if ratio > 0.5 and column.n_rows >= MIN_ROWS_FOR_CARDINALITY:
            score *= 0.6
            reasons.append("near-unique numeric (continuous outcome)")
        else:
            reasons.append("continuous numeric suits regression")
        return score, reasons

    # classification (default)
    if column.kind == "numeric":
        score = SCORE_STRUCTURAL_MAX * 0.6
        reasons.append("numeric column usable as a class label")
    elif column.kind in ("categorical", "boolean"):
        score = SCORE_STRUCTURAL_MAX
        reasons.append("categorical column suits classification")
    else:
        return 0.0, [f"high-cardinality {column.kind} column is not a class label"]

    if column.n_unique < MIN_CLASSIFICATION_CARDINALITY:
        return 0.0, ["column has too few distinct values to classify"]
    if ratio > 0.5:
        score *= 0.4
        reasons.append("near-unique values look like an identifier")
    return score, reasons


#: Tokens shorter than this carry no signal and are ignored when matching
#: ("is", "id"). Prevents a column being named by a stopword alone.
MIN_SIGNIFICANT_TOKEN = 3

#: A token matches an objective token when they share this many leading
#: characters. Lets "readmitted" match "readmission" and "fraud" match
#: "fraudulent" without a stemmer or a hand-written word list.
MIN_TOKEN_PREFIX = 5

#: ...and the shared prefix must cover at least this fraction of the *longer*
#: token. Without it ``monthlycharges`` would match an objective that merely
#: says "month", which manufactures false targets.
MIN_PREFIX_COVERAGE = 0.5


def _significant(tokens: Iterable[str]) -> List[str]:
    return [t for t in tokens if len(t) >= MIN_SIGNIFICANT_TOKEN]


def _common_prefix_len(a: str, b: str) -> int:
    length = 0
    for x, y in zip(a, b):
        if x != y:
            break
        length += 1
    return length


def _tokens_match(token: str, other: str) -> bool:
    """Whether two tokens plausibly name the same thing.

    Equality, or a shared prefix substantial enough relative to the whole word.
    This is deliberately generic — no dataset-specific synonym table — and it
    handles morphology (``readmitted``/``readmission``) that exact matching
    would miss.
    """
    if token == other:
        return True
    shared = _common_prefix_len(token, other)
    if shared < MIN_TOKEN_PREFIX:
        return False
    return shared / max(len(token), len(other)) >= MIN_PREFIX_COVERAGE


def _objective_coverage(column_tokens: Iterable[str], objective_tokens: set) -> Tuple[float, int]:
    """Length-weighted fraction of the column's tokens named by the objective.

    Long tokens dominate so a match on ``readmitted`` counts for more than a
    coincidence on a short one.
    """
    significant = _significant(column_tokens)
    if not significant:
        return 0.0, 0
    total = sum(len(t) for t in significant)
    matched = sum(
        len(t) for t in significant if any(_tokens_match(t, o) for o in objective_tokens)
    )
    return (matched / total if total else 0.0), len(significant)


def _score_objective(column: ColumnProfile, objective: str) -> Tuple[float, str, List[str]]:
    """Does the user's own words name this column? (casing-insensitive)"""
    objective_norm = normalize_name(objective)
    if not objective_norm:
        return 0.0, "", []
    objective_tokens = _tokens(objective)
    if not objective_tokens:
        return 0.0, "", []

    # Whole-name hit: the objective contains the column name verbatim.
    if column.normalized and column.normalized in objective_norm.split("_"):
        return SCORE_OBJECTIVE_EXACT, "objective_exact", [
            f"the objective names {column.name!r}"
        ]

    column_tokens = _tokens(normalize_name(column.name))
    coverage, n_tokens = _objective_coverage(column_tokens, objective_tokens)
    if n_tokens == 0 or coverage <= 0.0:
        return 0.0, "", []
    if coverage >= 1.0:
        return SCORE_OBJECTIVE_EXACT, "objective_exact", [
            f"the objective names every word of {column.name!r}"
        ]
    if coverage >= 0.5:
        return SCORE_OBJECTIVE_TOKEN, "objective_token", [
            f"the objective names {coverage:.0%} of the words in {column.name!r}"
        ]
    return 0.0, "", []


def resolve_target(
    schema: DatasetSchema,
    *,
    objective: str = "",
    hint: Optional[str] = None,
    task_type: str = "",
    proposal: Optional[str] = None,
) -> TargetResolution:
    """Resolve the target column for ``schema``.

    Evidence, strongest first:

    1. ``hint`` — a column the user (or the request config) named explicitly.
    2. the user's natural-language ``objective``.
    3. ``proposal`` — a column a model reading the real schema proposed.
    4. structural suitability for ``task_type``.

    Exact matches (explicit hint, or the objective naming the column verbatim)
    win outright. Otherwise, if the top two structural candidates are within
    :data:`AMBIGUITY_MARGIN`, the result is ``ambiguous`` so the caller can ask
    the user rather than coin-flip.
    """
    task = (task_type or "classification").strip().lower()
    if not schema.columns:
        return TargetResolution(
            status="unresolved",
            reason="the dataset exposes no columns to choose from",
            task_type=task,
        )

    scored: List[Tuple[TargetCandidate, bool]] = []
    hint_matched = False

    def _add(
        column: ColumnProfile,
        score: float,
        matched_by: str,
        reasons: List[str],
        tiebreak: float = 0.0,
        evidence_score: Optional[float] = None,
    ):
        scored.append(
            (
                TargetCandidate(
                    column.name,
                    score,
                    matched_by,
                    reasons,
                    tiebreak,
                    score if evidence_score is None else evidence_score,
                ),
                False,
            )
        )

    hint_key = normalize_name(hint) if hint and str(hint).strip() else ""
    for column in schema.columns:
        obj_score, obj_by, obj_reasons = _score_objective(column, objective)
        struct_score, struct_reasons = _structural_score(column, task)

        # An exact, decisive match short-circuits: a user who typed the column
        # name does not want us to second-guess them with structure.
        if hint_key and column.normalized == hint_key:
            hint_matched = True
            _add(column, SCORE_EXPLICIT, "explicit_hint", [f"requested explicitly as {hint!r}"], 1.0)
            continue

        reasons = list(obj_reasons) + list(struct_reasons)
        score = max(obj_score, struct_score)
        # An identifier-like column cannot become a target just because the
        # objective shares a word with it; structural disqualification wins.
        if _is_identifier_like(column, task):
            if score > 0.0:
                _add(column, 0.0, "disqualified", struct_reasons, 0.0)
            continue
        matched_by = obj_by if obj_score >= struct_score else "structure"
        if score > 0.0:
            _add(column, score, matched_by, reasons, struct_score, evidence_score=score)

        # A model proposal is evidence *about* a column, but it must not manufacture
        # a winner where the data and the user's words produce a tie. Its score
        # is boosted for ranking, while ``evidence_score`` keeps the
        # objective+structure value so ambiguity below can ignore the opinion.
        if proposal and column.normalized == normalize_name(proposal):
            _add(
                column,
                max(score, SCORE_MODEL_PROPOSAL),
                "model_proposal",
                reasons + [f"proposed from the dataset schema as {proposal!r}"],
                struct_score,
                evidence_score=score,
            )

    # A hint that names no real column is an error, not a reason to quietly pick
    # a different one: the user asked for a specific column.
    if hint_key and not hint_matched:
        return TargetResolution(
            status="unresolved",
            reason=(
                f"requested target column {str(hint).strip()!r} is not in the dataset "
                f"(available: {', '.join(schema.names()[:20])})"
            ),
            task_type=task,
        )

    # Keep the strongest evidence per column, preferring the richer tiebreak.
    best: Dict[str, TargetCandidate] = {}
    for candidate, _decisive in scored:
        current = best.get(candidate.column)
        if (
            current is None
            or candidate.score > current.score
            or (candidate.score == current.score and candidate.tiebreak > current.tiebreak)
        ):
            best[candidate.column] = candidate

    # Order by evidence, then by structural suitability. The tiebreak only
    # orders candidates whose wording evidence ties -- it never promotes a
    # candidate on its own.
    ranked = sorted(best.values(), key=lambda c: (-c.score, -c.tiebreak, c.column))
    if not ranked:
        return TargetResolution(
            status="unresolved",
            reason=(
                f"no column in {schema.describe()} is suitable as a {task} target; "
                "the dataset may be empty or entirely constant"
            ),
            task_type=task,
        )

    top = ranked[0]
    if top.score <= 0.0:
        return TargetResolution(
            status="unresolved",
            reason=(
                f"no column is suitable as a {task} target (available: "
                f"{', '.join(schema.names()[:20])})"
            ),
            candidates=ranked[:5],
            task_type=task,
        )

    # A tie between equally-supported columns must go to the user -- unless one is
    # structurally better suited to the task, in which case the evidence and
    # the shape agree and no guess is being made.
    #
    # Ambiguity is judged on ``evidence_score`` (the user's words + the data),
    # never on a model proposal: one model's opinion deciding a coin-flip is
    # exactly the guessing this is meant to replace.
    if len(ranked) > 1:
        runner_up = ranked[1]
        tied_on_evidence = abs(top.evidence_score - runner_up.evidence_score) < 1e-9
        tied_on_shape = abs(top.tiebreak - runner_up.tiebreak) < 1e-9
        if tied_on_evidence and tied_on_shape and top.matched_by != "explicit_hint":
            return TargetResolution(
                status="ambiguous",
                candidates=ranked[:5],
                reason=(
                    f"{top.column!r} and {runner_up.column!r} are equally plausible "
                    f"{task} targets; select one"
                ),
                task_type=task,
            )

    return TargetResolution(
        status="resolved",
        candidates=[top],
        reason=top.reasons[0] if top.reasons else f"selected {top.column!r}",
        task_type=task,
    )


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

@dataclass
class TargetValidation:
    """Whether a chosen target is usable for the requested task."""

    ok: bool
    column: Optional[str] = None
    problems: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "column": self.column, "problems": list(self.problems)}

    def raise_if_invalid(self, *, dataset: str = "") -> str:
        if self.ok and self.column:
            return self.column
        where = f" for dataset {dataset!r}" if dataset else ""
        raise TargetResolutionError(
            f"target column is unusable{where}: {'; '.join(self.problems)}",
            problems=self.problems,
        )


def validate_target(
    schema: DatasetSchema, column: str, *, task_type: str = "classification"
) -> TargetValidation:
    """Verify a target exists in the real schema and suits the requested task.

    Resolves casing/punctuation differences, so validating ``churn`` against a
    file whose column is ``Churn`` succeeds and reports the real name.
    """
    task = (task_type or "classification").strip().lower()
    profile = schema.get(column)

    if profile is None:
        return TargetValidation(
            ok=False,
            column=None,
            problems=[
                f"column {column!r} is not in the dataset (available: "
                f"{', '.join(schema.names()[:20])})"
            ],
        )

    problems: List[str] = []
    if profile.is_constant:
        problems.append(f"{profile.name!r} has a single distinct value")
    elif task == "regression" and profile.kind != "numeric":
        problems.append(
            f"{profile.name!r} is {profile.kind}, which cannot be a regression target"
        )
    elif task != "regression" and profile.kind == "text":
        problems.append(
            f"{profile.name!r} is free text ({profile.n_unique} distinct values) "
            "and is not a class label"
        )

    if problems:
        return TargetValidation(ok=False, column=profile.name, problems=problems)
    return TargetValidation(ok=True, column=profile.name, problems=[])


def resolve_and_validate(
    schema: DatasetSchema,
    *,
    objective: str = "",
    hint: Optional[str] = None,
    task_type: str = "",
    proposal: Optional[str] = None,
) -> TargetResolution:
    """Resolve a target and confirm it against the real schema.

    When the caller supplied a hint we validate *that* column directly: an
    explicit choice is honoured even if it is not the structurally obvious
    pick, and a bad choice surfaces as an actionable error rather than being
    silently replaced.
    """
    if hint and hint.strip():
        task = (task_type or "classification").strip().lower()
        resolved = resolve_target(
            schema, objective=objective, hint=hint, task_type=task, proposal=proposal
        )
        # An explicit hint that does not exist in the file is an error, not a
        # reason to silently pick a different column.
        if resolved.status != "resolved" or not resolved.column:
            return resolved
        checked = validate_target(schema, resolved.column, task_type=task)
        if not checked.ok:
            return TargetResolution(
                status="unresolved",
                candidates=resolved.candidates,
                reason="; ".join(checked.problems),
                task_type=task,
            )
        return resolved

    resolution = resolve_target(
        schema, objective=objective, task_type=task_type, proposal=proposal
    )
    if resolution.status == "resolved" and resolution.column:
        checked = validate_target(schema, resolution.column, task_type=task_type)
        if not checked.ok:
            return TargetResolution(
                status="unresolved",
                candidates=resolution.candidates,
                reason="; ".join(checked.problems),
                task_type=resolution.task_type,
            )
    return resolution
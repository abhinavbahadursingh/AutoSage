"""Shared in-memory AsyncSession fake for API tests (no live database).

Executes the real service/repository SQLAlchemy statements against Python
dicts. Supported query shapes (everything Phase 2-4 services emit):

- ``select(Entity)`` with ``==`` / ``!=`` / ``in_`` filters (AND-combined)
- ``select(func.count()).select_from(Entity)`` with the same filters
- ``order_by`` (single or multiple columns, asc/desc), ``limit`` / ``offset``
- ``session.get/add/delete/commit/refresh/close``

Everything else — routing, JWT verification, auth dependencies, ownership
checks, lifecycle guards, response envelopes — is the real application stack.
"""
import operator
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList
from sqlalchemy.sql.functions import Function

from app.models.agent_execution import AgentExecution
from app.models.artifact import Artifact
from app.models.dataset import Dataset
from app.models.decision import Decision
from app.models.evidence import EvidenceTrailNode
from app.models.experiment import Experiment
from app.models.memory import ExperienceMemory as VerifiedMemory
from app.models.ml_run import MLRun
from app.models.pipeline import Pipeline
from app.models.project import Project
from app.models.run import PipelineRun
from app.models.user import User
from app.models.verification import Verification
from app.models.workspace import Workspace


class _FakeScalars:
    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows

    def all(self) -> List[Any]:
        return list(self._rows)

    def first(self) -> Optional[Any]:
        return self._rows[0] if self._rows else None

    def one_or_none(self) -> Optional[Any]:
        assert len(self._rows) <= 1, f"expected at most one row, got {len(self._rows)}"
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows: List[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)

    def scalar(self) -> Any:
        return self._rows[0] if self._rows else None


def _iter_conditions(whereclause: Any):  # type: ignore[no-untyped-def]
    if whereclause is None:
        return
    if isinstance(whereclause, BooleanClauseList) and whereclause.operator is operator.and_:
        for clause in whereclause.clauses:
            yield from _iter_conditions(clause)
    elif isinstance(whereclause, BinaryExpression):
        yield whereclause
    else:  # pragma: no cover - services only emit == / != / IN / AND filters
        raise AssertionError(f"unsupported filter in fake session: {whereclause!r}")


def _matches(row: Any, condition: BinaryExpression) -> bool:
    column = condition.left
    expected = getattr(condition.right, "value", condition.right)
    actual = getattr(row, column.key)
    if condition.operator is operator.eq:
        return actual == expected
    if condition.operator is operator.ne:
        return actual != expected
    if getattr(condition.operator, "__name__", "") == "in_op":
        return actual in (expected if expected is not None else [])
    raise AssertionError(f"unsupported operator in fake session: {condition.operator!r}")


def _apply_ordering(rows: List[Any], stmt: Any) -> List[Any]:
    clauses = list(getattr(stmt, "_order_by_clauses", ()) or ())
    # Stable successive sorts, last key first.
    for clause in reversed(clauses):
        element = getattr(clause, "element", None)
        key = getattr(element, "key", None)
        if key is None:  # pragma: no cover - services order by plain columns
            raise AssertionError(f"unsupported order-by in fake session: {clause!r}")
        reverse = getattr(getattr(clause, "modifier", None), "__name__", "") == "desc_op"
        rows = sorted(rows, key=lambda row: getattr(row, key), reverse=reverse)
    return rows


def _apply_client_defaults(obj: Any) -> None:
    """Mimic flush-time column defaults (``default=`` is INSERT-time in SQLAlchemy)."""
    mapper = sa_inspect(type(obj))
    for prop in mapper.column_attrs:
        if prop.key == "id":
            continue
        if getattr(obj, prop.key, None) is not None:
            continue
        default = prop.columns[0].default
        if default is None:
            continue
        arg = default.arg
        if not callable(arg):
            setattr(obj, prop.key, arg)
            continue
        # Plain callables (dict, uuid4, datetime.utcnow) evaluate with no
        # args; SQLAlchemy wraps some (e.g. onupdate) as context-sensitive.
        try:
            setattr(obj, prop.key, arg())
        except TypeError:
            setattr(obj, prop.key, arg(None))


class FakeAsyncSession:
    """Minimal in-memory stand-in for AsyncSession."""

    def __init__(self) -> None:
        self._store: Dict[Type, Dict[Any, Any]] = {
            User: {},
            Workspace: {},
            Project: {},
            Dataset: {},
            Experiment: {},
            Pipeline: {},
            PipelineRun: {},
            AgentExecution: {},
            Decision: {},
            EvidenceTrailNode: {},
            Verification: {},
            VerifiedMemory: {},
            MLRun: {},
            Artifact: {},
        }

    def _entity_for_table(self, name: str) -> Type:
        for entity in self._store:
            if getattr(entity, "__tablename__", None) == name:
                return entity
        raise AssertionError(f"unknown table in fake session: {name!r}")

    # -- reads ------------------------------------------------------------
    async def get(self, entity: Type, pk: Any) -> Optional[Any]:
        for obj in self._store[entity].values():
            if obj.id == pk:
                return obj
        return None

    async def execute(self, stmt: Any) -> _FakeResult:
        selected = list(stmt.selected_columns)
        if len(selected) == 1 and isinstance(selected[0], Function):
            # Total-count query: select(func.count()).select_from(Entity)...
            froms = stmt.get_final_froms()
            assert len(froms) == 1, f"unsupported count FROM in fake: {froms!r}"
            entity = self._entity_for_table(froms[0].name)
            rows = list(self._store[entity].values())
            for condition in _iter_conditions(stmt.whereclause):
                rows = [row for row in rows if _matches(row, condition)]
            return _FakeResult([len(rows)])

        entity = stmt.column_descriptions[0]["entity"]
        rows = list(self._store[entity].values())
        for condition in _iter_conditions(stmt.whereclause):
            rows = [row for row in rows if _matches(row, condition)]
        rows = _apply_ordering(rows, stmt)
        offset = getattr(stmt, "_offset", None) or 0
        limit = getattr(stmt, "_limit", None)
        rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        return _FakeResult(rows)

    # -- writes -----------------------------------------------------------
    def add(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        _apply_client_defaults(obj)
        self._store[type(obj)][obj.id] = obj

    async def delete(self, obj: Any) -> None:
        keys = [k for k, v in self._store[type(obj)].items() if v is obj or v.id == obj.id]
        for key in keys:
            del self._store[type(obj)][key]

    async def commit(self) -> None:
        return None

    async def flush(self) -> None:
        """No-op — rows are already applied eagerly in ``add``/``delete``."""
        return None

    async def rollback(self) -> None:
        return None

    async def refresh(self, obj: Any) -> None:
        _apply_client_defaults(obj)

    async def close(self) -> None:
        return None

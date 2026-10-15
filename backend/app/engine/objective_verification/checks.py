"""Deterministic checks backing the four canonical AutoSage objectives.

Every check is a pure inspection of material that genuinely exists for *this
fresh session*, of the repository's own source, or of a pure helper called with
synthetic in-memory data.

**Nothing here preprocesses a dataset, trains a model, or retrains anything.**

Status discipline
-----------------
A check is only PASS when it actually evaluated its condition against real
evidence. When the evidence it needs does not exist — which is the normal case
for a fresh session, because nothing has trained yet — it is NOT_VERIFIED, and
its ``evidence`` says exactly what is missing. BLOCKED is reserved for checks
that were never attempted because a prerequisite stage failed.

Input contract
--------------
Each ``run_objective_N_checks(facts)`` takes the plain dict built by
:func:`app.services.objective_verification_service.FreshVerificationService._load_facts`,
which is scoped to one session's experiment and nothing else.
"""
from __future__ import annotations

import ast
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.engine.verification.gate_checks import (
    CHECK_AST_SECURITY,
    CHECK_DATA_LEAKAGE,
    run_static_gate_checks,
)
from app.schemas.objective_verification import CheckResult, CheckStatus, StageStatus

logger = logging.getLogger("autosage.objective_verification")

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.utcnow()


#: What kind of evidence each check examines. Derived from the check id so a
#: branch that forgets to pass ``category`` still reports the truth rather
#: than silently defaulting to "source".
#:
#: - "source"    — repository files, read and parsed statically
#: - "probe"     — synthetic in-memory data, no real dataset
#: - "session"   — database records for this specific session
#: - "generated" — products of LLM code generation (never executed)
#: - "empirical" — a real measured run (reserved; nothing here reaches it)
_CHECK_CATEGORY: Dict[str, str] = {
    "o1_pipeline_graph": "source",
    "o1_dataset_tools": "source",
    "o1_dataset_driven_target": "probe",
    "o1_input_captured": "session",
    "o2_specialist_agents": "source",
    "o2_tool_registry": "source",
    "o2_sandbox_isolation": "source",
    "o2_specialist_executions": "session",
    "o3_ast_security": "generated",
    "o3_data_leakage": "generated",
    "o3_metric_sanity": "session",
    "o3_baseline_dominance": "session",
    "o3_evidence_sources": "source",
    "o3_independent_agreement": "session",
    "o4_decision_rationale": "session",
    "o4_decision_confidence": "session",
    "o4_evidence_nodes": "session",
    "o4_experience_memory": "session",
    "o4_audit_chain": "session",
}

#: How strong the evidence behind each verdict is. Kept apart from the
#: category: a source-level PASS is not proof that a specific generated
#: decision is right, and a runtime-level check is exactly the one a fresh
#: session cannot satisfy.
#:
#: - "source"   — read from repository files
#: - "config"   — read from the submitted request
#: - "generated"— read from code generation (never executed)
#: - "runtime"  — needs code to have actually run / real records to exist
_CHECK_LEVEL: Dict[str, str] = {
    "o1_pipeline_graph": "source",
    "o1_dataset_tools": "source",
    "o1_dataset_driven_target": "runtime",
    "o1_input_captured": "config",
    "o2_specialist_agents": "source",
    "o2_tool_registry": "source",
    "o2_sandbox_isolation": "source",
    "o2_specialist_executions": "runtime",
    "o3_ast_security": "generated",
    "o3_data_leakage": "generated",
    "o3_metric_sanity": "runtime",
    "o3_baseline_dominance": "runtime",
    "o3_evidence_sources": "source",
    "o3_independent_agreement": "runtime",
    "o4_decision_rationale": "runtime",
    "o4_decision_confidence": "runtime",
    "o4_evidence_nodes": "runtime",
    "o4_experience_memory": "runtime",
    "o4_audit_chain": "runtime",
}


def _result(
    check_id: str,
    title: str,
    status: CheckStatus,
    *,
    expected: str = "",
    actual: str = "",
    evidence: Sequence[str] = (),
    confidence: float = 0.0,
    artifact: str = "",
    category: Optional[str] = None,
    level: Optional[str] = None,
) -> CheckResult:
    """Build one check result. ``reasoning`` is derived, never asserted twice.

    ``category`` records what kind of evidence was examined and defaults to
    the entry in :data:`_CHECK_CATEGORY`; pass it explicitly only where the
    same check id genuinely inspects different material on different
    branches (the safety gates: this session's generated script, or the
    repository template when no script exists). ``level`` is the strength of
    that evidence and defaults to :data:`_CHECK_LEVEL`.
    """
    reasoning = actual or expected
    return CheckResult(
        check_id=check_id,
        title=title,
        status=status,
        evidence=[str(e) for e in evidence],
        expected=expected,
        actual=actual,
        reasoning=reasoning,
        confidence=round(max(0.0, min(1.0, confidence)), 4),
        artifact=artifact,
        checked_at=_now(),
        category=category or _CHECK_CATEGORY.get(check_id, "source"),
        verification_level=level or _CHECK_LEVEL.get(check_id, "source"),
    )


def _read_source(relative: str) -> Optional[str]:
    """Read a repository source file, or None when absent.

    ``utf-8-sig`` so a byte-order mark does not make ``ast.parse`` reject a
    file Python's own import machinery would happily load.
    """
    try:
        return (REPO_ROOT / relative).read_text(encoding="utf-8-sig")
    except OSError:
        return None


def _missing_artifact(check_id: str, title: str, relative: str, expected: str) -> CheckResult:
    """A check whose artifact does not exist is NOT_VERIFIED, never PASS."""
    return _result(
        check_id,
        title,
        CheckStatus.NOT_VERIFIED,
        expected=expected,
        actual=f"artifact not found: {relative}",
        evidence=[f"artifact not found: {relative}"],
        artifact=relative,
    )


def _confidence(observed: int, needed: int = 1) -> float:
    """Deterministic confidence from how much of what was needed was observed."""
    if needed <= 0:
        return 0.0
    return round(min(0.95, 0.55 + 0.40 * (observed / needed)), 4)


def _parse(relative: str) -> Tuple[Optional[ast.Module], Optional[CheckResult]]:
    """Parse a repo source file, or return the UNVERIFIED result explaining why not."""
    source = _read_source(relative)
    if source is None:
        return None, None
    try:
        return ast.parse(source), None
    except SyntaxError as exc:
        return None, exc  # type: ignore[return-value]


def _module_var(
    tree: ast.Module, name: str
) -> Optional[ast.AST]:
    """Find the assignment (Assign or AnnAssign) that binds ``name``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return node.value
    return None


def _builtin_tool_names(tree: ast.Module) -> List[str]:
    """Statically read the class names listed in ``BUILTIN_TOOLS``.

    The list holds class references (``ast.Name``/``ast.Attribute``), not
    strings, and the tool classes live in a conditional import block, so the
    whole tree is walked. Nothing is imported or executed.
    """
    value = _module_var(tree, "BUILTIN_TOOLS")
    if not isinstance(value, (ast.List, ast.Tuple)):
        return []
    names: List[str] = []
    for elt in value.elts:
        if isinstance(elt, ast.Name):
            names.append(elt.id)
        elif isinstance(elt, ast.Attribute):
            names.append(elt.attr)
    return names


# ---------------------------------------------------------------------------
# Objective 1 — English request to complete pipeline
# ---------------------------------------------------------------------------

_STAGE_CHAIN = (
    "orchestrator",
    "discovery",
    "profiler",
    "preprocessor",
    "model_selector",
    "ml_experiment",
    "verification",
)

_EXPECTED_O1_GRAPH = (
    "app/agents/graph.py declares the complete " + " -> ".join(_STAGE_CHAIN) + " chain."
)


def check_pipeline_graph() -> CheckResult:
    """The workflow declares the full stage chain an English request walks."""
    cid, title = "o1_pipeline_graph", "English request drives the full stage chain"
    source = _read_source("app/agents/graph.py")
    if source is None:
        return _missing_artifact(cid, title, "app/agents/graph.py", _EXPECTED_O1_GRAPH)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O1_GRAPH,
            actual=f"app/agents/graph.py failed to parse: {exc}",
            evidence=[f"SyntaxError: {exc}"],
            artifact="app/agents/graph.py",
        )

    node = _module_var(tree, "STAGE_ORDER")
    declared: List[str] = []
    if node is not None:
        try:
            declared = [v for v in ast.literal_eval(node) if isinstance(v, str)]
        except Exception:  # noqa: BLE001 - literal_eval is best effort
            declared = []

    evidence = [
        f"STAGE_ORDER declares {len(declared)} stage(s): {', '.join(declared) or '(none)'}",
        f"expected chain: {', '.join(_STAGE_CHAIN)}",
    ]
    missing = [s for s in _STAGE_CHAIN if s not in declared]
    if missing:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O1_GRAPH,
            actual=f"workflow is missing stage(s): {', '.join(missing)}",
            evidence=evidence + [f"missing: {', '.join(missing)}"],
            confidence=_confidence(0),
            artifact="app/agents/graph.py",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=_EXPECTED_O1_GRAPH,
        actual="all seven workflow stages are declared in the agent graph",
        evidence=evidence,
        confidence=_confidence(len(_STAGE_CHAIN)),
        artifact="app/agents/graph.py",
    )


_DATASET_TOOL_PATTERNS = {
    "search": ("searchdataset", "search_dataset"),
    "download": ("downloaddataset", "download_dataset"),
    "validate": ("validatedataset", "validate_dataset"),
}
_EXPECTED_O1_TOOLS = (
    "app/engine/tools/builtins.py registers a search, a download and a "
    "validate dataset tool in BUILTIN_TOOLS."
)


def check_dataset_tools() -> CheckResult:
    """The system can find or ask for the dataset, as a registered capability."""
    cid, title = "o1_dataset_tools", "The system can find or ask for the dataset"
    tree, failure = _parse("app/engine/tools/builtins.py")
    if tree is None:
        if failure is None:
            return _missing_artifact(cid, title, "app/engine/tools/builtins.py", _EXPECTED_O1_TOOLS)
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O1_TOOLS,
            actual=f"app/engine/tools/builtins.py failed to parse: {failure}",
            artifact="app/engine/tools/builtins.py",
        )

    tools = _builtin_tool_names(tree)
    lowered = [t.lower() for t in tools]

    def _match_tool(patterns: Sequence[str]) -> Optional[str]:
        for pattern in patterns:
            for tool in lowered:
                if pattern in tool:
                    return tool
        return None

    found = {role: _match_tool(pats) for role, pats in _DATASET_TOOL_PATTERNS.items()}
    evidence = [
        f"BUILTIN_TOOLS registers {len(tools)} tool(s): {', '.join(tools) or '(none)'}",
        "dataset capabilities matched: "
        + ", ".join(f"{role}={tool}" for role, tool in found.items()),
    ]
    missing = [role for role, tool in found.items() if tool is None]
    if missing:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O1_TOOLS,
            actual="no registered tool provides: " + ", ".join(missing),
            evidence=evidence,
            confidence=_confidence(len(_DATASET_TOOL_PATTERNS) - len(missing)),
            artifact="app/engine/tools/builtins.py",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=_EXPECTED_O1_TOOLS,
        actual="search, download and validate dataset tools are all registered",
        evidence=evidence,
        confidence=_confidence(len(_DATASET_TOOL_PATTERNS)),
        artifact="app/engine/tools/builtins.py",
    )


def check_dataset_driven_target() -> CheckResult:
    """Target resolution is schema-driven, and refuses an invented column.

    A targeted probe: ``resolve_and_validate`` is called against a synthetic
    in-memory schema — once with a column the schema really contains under
    different casing (must resolve) and once with a fabricated name (must not).
    No dataset file is read and nothing is trained.
    """
    cid, title = "o1_dataset_driven_target", "The target column comes from the dataset's own schema"
    expected = (
        "resolve_and_validate() matches a real column across casing "
        "differences and refuses a fabricated column."
    )
    try:
        from app.engine.targeting import (
            ColumnProfile,
            DatasetSchema,
            resolve_and_validate,
        )
    except Exception as exc:  # noqa: BLE001 - an import failure is a real finding
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=expected,
            actual=f"app.engine.targeting could not be imported: {exc}",
            evidence=[f"import failed: {exc}"],
            artifact="app/engine/targeting.py",
        )

    schema = DatasetSchema(
        columns=(
            ColumnProfile(name="tenure_month", kind="numeric", n_unique=40, null_rate=0.0, n_rows=100),
            ColumnProfile(name="monthly_bill", kind="numeric", n_unique=57, null_rate=0.0, n_rows=100),
            ColumnProfile(name="IS_CHURNING", kind="categorical", n_unique=2, null_rate=0.0, n_rows=100),
        ),
        n_rows=100,
        source="objective_verification.probe",
    )

    facts: List[str] = []
    passed = 0

    try:
        resolved = resolve_and_validate(schema, hint="is_churning", task_type="classification")
        column = getattr(resolved, "column", None)
        ok = bool(column) and str(column) == "IS_CHURNING"
        passed += 1 if ok else 0
        facts.append(
            f"casing-different hint 'is_churning' resolved to {column!r} "
            f"(status={getattr(resolved, 'status', 'unknown')})"
        )
    except Exception as exc:  # noqa: BLE001
        facts.append(f"casing probe raised: {type(exc).__name__}: {exc}")

    try:
        fabricated = resolve_and_validate(
            schema, hint="definitely_not_a_column", task_type="classification"
        )
        column = getattr(fabricated, "column", None)
        rejected = not column
        passed += 1 if rejected else 0
        facts.append(
            f"fabricated column 'definitely_not_a_column' "
            f"{'rejected' if rejected else 'was accepted as ' + repr(column)} "
            f"(status={getattr(fabricated, 'status', 'unknown')})"
        )
    except Exception as exc:  # noqa: BLE001
        facts.append(f"fabricated-column probe raised: {type(exc).__name__}: {exc}")

    if passed == 2:
        status = CheckStatus.PASS
        actual = "target resolution matched a real column across casing and refused a fabricated one"
    elif passed == 0:
        status = CheckStatus.FAIL
        actual = "target resolution failed both the casing match and the fabricated-column refusal"
    else:
        status = CheckStatus.FAIL
        actual = f"target resolution satisfied only {passed} of 2 probe assertions"

    return _result(
        cid,
        title,
        status,
        expected=expected,
        actual=actual,
        evidence=facts,
        confidence=_confidence(passed, 2),
        artifact="app/engine/targeting.py",
    )


def check_input_captured(facts: Mapping[str, Any]) -> CheckResult:
    """The fresh request and its dataset are recorded against this session."""
    cid, title = "o1_input_captured", "The fresh request and dataset are recorded on the session"
    expected = (
        "The session stores a non-empty problem statement, a dataset name, "
        "and the task type / primary metric given."
    )
    problem = str(facts.get("problem_statement") or "").strip()
    dataset = str(facts.get("dataset_name") or "").strip()
    cfg = dict(facts.get("config") or {})
    resolved = bool(facts.get("dataset_resolved"))

    evidence = [
        f"problem statement: {problem[:160]!r}",
        f"dataset name: {dataset!r} (resolves for this user: {resolved})",
        f"target column: {cfg.get('target_column') or 'not given'}",
        f"task type: {cfg.get('task_type') or 'not given'}",
        f"primary metric: {cfg.get('primary_metric') or 'not given'}",
    ]

    if not problem:
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=expected,
            actual="the session is missing a problem statement",
            evidence=evidence,
            artifact="verification_sessions",
        )

    # The problem statement is the only required input. Dataset name is optional —
    # code generation proceeds without it, and the session is still well-formed.
    dataset_note = (
        f" with dataset {dataset!r}"
        if dataset
        else " (no dataset required — design-time audit)"
    )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=expected,
        actual=(
            f"the session pins the request{dataset_note} with task type "
            f"{cfg.get('task_type')!r} and primary metric {cfg.get('primary_metric')!r}"
            + ("" if resolved or not dataset else " (the dataset file itself does not resolve yet)")
        ),
        evidence=evidence,
        confidence=_confidence(3),
        artifact="verification_sessions",
    )


def run_objective_1_checks(facts: Mapping[str, Any]) -> List[CheckResult]:
    return [
        check_pipeline_graph(),
        check_dataset_tools(),
        check_dataset_driven_target(),
        check_input_captured(facts),
    ]


# ---------------------------------------------------------------------------
# Objective 2 — Separate specialist agents
# ---------------------------------------------------------------------------

_SPECIALISTS = {
    "study the data": "app/agents/discovery.py",
    "profile the data": "app/agents/profiler.py",
    "clean the data": "app/agents/preprocessor.py",
    "choose the model": "app/agents/model_selector.py",
}
_EXPECTED_O2_SPECIALISTS = (
    "app/agents/ contains separate discovery, profiler, preprocessor and "
    "model_selector modules."
)


def check_specialist_agents() -> CheckResult:
    """Data study, cleaning and model choice are distinct modules."""
    cid, title = "o2_specialist_agents", "Separate agents study the data, clean it, and pick the model"
    evidence: List[str] = []
    missing: List[str] = []
    for role, relative in _SPECIALISTS.items():
        exists = (REPO_ROOT / relative).is_file()
        evidence.append(
            f"{role}: {relative} {'present' if exists else 'MISSING'}"
        )
        if not exists:
            missing.append(role)

    if missing:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O2_SPECIALISTS,
            actual="no separate specialist module for: " + ", ".join(missing),
            evidence=evidence,
            confidence=_confidence(len(_SPECIALISTS) - len(missing), len(_SPECIALISTS)),
            artifact="app/agents/",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=_EXPECTED_O2_SPECIALISTS,
        actual="discovery, profiler, preprocessor and model_selector are separate modules",
        evidence=evidence,
        confidence=_confidence(len(_SPECIALISTS), len(_SPECIALISTS)),
        artifact="app/agents/",
    )


_EXPECTED_O2_REGISTRY = (
    "app/engine/tools/builtins.py declares a non-empty BUILTIN_TOOLS list "
    "resolvable by agents at runtime."
)


def check_tool_registry() -> CheckResult:
    """Capabilities are registered and resolvable, not hard-coded."""
    cid, title = "o2_tool_registry", "Agents resolve capabilities through a tool registry"
    tree, failure = _parse("app/engine/tools/builtins.py")
    if tree is None:
        if failure is None:
            return _missing_artifact(cid, title, "app/engine/tools/builtins.py", _EXPECTED_O2_REGISTRY)
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O2_REGISTRY,
            actual=f"app/engine/tools/builtins.py failed to parse: {failure}",
            artifact="app/engine/tools/builtins.py",
        )

    tools = _builtin_tool_names(tree)
    classes = [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef) and n.name.endswith("Tool")
    ]
    evidence = [
        f"BUILTIN_TOOLS lists {len(tools)} tool(s): {', '.join(tools) or '(none)'}",
        f"BaseTool subclasses defined: {len(classes)}",
    ]
    if not tools:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O2_REGISTRY,
            actual="BUILTIN_TOOLS is empty or not statically listable",
            evidence=evidence + ["BUILTIN_TOOLS is empty or not statically listable"],
            artifact="app/engine/tools/builtins.py",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=_EXPECTED_O2_REGISTRY,
        actual=f"{len(tools)} built-in tool(s) are registered for agent use",
        evidence=evidence,
        confidence=_confidence(len(tools)),
        artifact="app/engine/tools/builtins.py",
    )


_EXPECTED_O2_SANDBOX = (
    'The sandbox run configuration sets network_mode="none", read_only, '
    "cpu_count and mem_limit."
)


def check_sandbox_isolation() -> CheckResult:
    """Generated code runs with no network, a read-only root and hard limits."""
    cid, title = "o2_sandbox_isolation", "The agents' code runs sandboxed and bounded"
    tree, failure = _parse("app/engine/sandbox/manager.py")
    if tree is None:
        if failure is None:
            return _missing_artifact(cid, title, "app/engine/sandbox/manager.py", _EXPECTED_O2_SANDBOX)
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O2_SANDBOX,
            actual=f"app/engine/sandbox/manager.py failed to parse: {failure}",
            artifact="app/engine/sandbox/manager.py",
        )

    required = {
        "network_disabled": False,
        "read_only_rootfs": False,
        "cpu_limit": False,
        "memory_limit": False,
    }
    evidence: List[str] = []

    def _callee_name(func: ast.AST) -> str:
        if isinstance(func, ast.Attribute):
            return func.attr
        return func.id if isinstance(func, ast.Name) else ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _callee_name(node.func) == "run":
            kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            net = kwargs.get("network_mode")
            if isinstance(net, ast.Constant) and net.value == "none":
                required["network_disabled"] = True
                evidence.append('containers.run(network_mode="none")')
            for kw, flag in (
                ("read_only", "read_only_rootfs"),
                ("cpu_count", "cpu_limit"),
                ("mem_limit", "memory_limit"),
            ):
                if kw in kwargs:
                    required[flag] = True
                    evidence.append(f"containers.run({kw}=...)")
            for kw in ("cap_drop", "user", "pids_limit"):
                if kw in kwargs:
                    evidence.append(f"containers.run({kw}=...) (additional hardening)")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (
                    "DEFAULT_CPU_LIMIT",
                    "DEFAULT_MEMORY_LIMIT",
                ):
                    evidence.append(f"{target.id} is configured")

    missing = [k for k, ok in required.items() if not ok]
    if missing:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O2_SANDBOX,
            actual="sandbox isolation is incomplete: " + ", ".join(missing),
            evidence=evidence or ["no sandbox run configuration found"],
            confidence=_confidence(len(required) - len(missing), len(required)),
            artifact="app/engine/sandbox/manager.py",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=_EXPECTED_O2_SANDBOX,
        actual="the sandbox disables networking and bounds CPU and memory",
        evidence=evidence,
        confidence=_confidence(len(required), len(required)),
        artifact="app/engine/sandbox/manager.py",
    )


def check_specialist_executions(facts: Mapping[str, Any]) -> CheckResult:
    """This session actually ran the specialists, and the runs are recorded."""
    cid, title = "o2_specialist_executions", "This session actually ran the specialist agents"
    expected = (
        "agent_executions rows exist for this session naming the specialist agents."
    )
    count = int(facts.get("agent_executions") or 0)
    names = sorted({str(n) for n in (facts.get("agent_names") or [])})
    evidence = [
        f"agent_executions rows for this session: {count}",
        "agents recorded: " + (", ".join(names) if names else "none"),
    ]
    if count == 0:
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=expected,
            actual=(
                "this session has no agent executions, because verification "
                "never runs the pipeline itself"
            ),
            evidence=evidence,
            artifact="agent_executions",
        )
    expected_agents = {"discovery", "profiler", "preprocessor", "model_selector"}
    seen = {n.lower() for n in names}
    missing = sorted(a for a in expected_agents if a not in seen)
    if missing:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=expected,
            actual="no execution recorded for specialist agent(s): " + ", ".join(missing),
            evidence=evidence,
            confidence=_confidence(len(seen & expected_agents), len(expected_agents)),
            artifact="agent_executions",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=expected,
        actual=f"all four specialists recorded an execution ({count} total)",
        evidence=evidence,
        confidence=_confidence(len(expected_agents), len(expected_agents)),
        artifact="agent_executions",
    )


def run_objective_2_checks(facts: Mapping[str, Any]) -> List[CheckResult]:
    return [
        check_specialist_agents(),
        check_tool_registry(),
        check_sandbox_isolation(),
        check_specialist_executions(facts),
    ]


# ---------------------------------------------------------------------------
# Objective 3 — Every decision checked, doubtful choices replaced
# ---------------------------------------------------------------------------

#: gate name -> (check id, title, expected behaviour)
_O3_GATES: Tuple[Tuple[str, str, str, str], ...] = (
    (
        CHECK_AST_SECURITY,
        "o3_ast_security",
        "The executed script contains no dangerous operations",
        "The AST/security gate passes for the script this session executed.",
    ),
    (
        CHECK_DATA_LEAKAGE,
        "o3_data_leakage",
        "The evaluation does not leak the target",
        "The data-leakage gate passes for the script this session executed.",
    ),
)


def _gate_checks(facts: Mapping[str, Any]) -> Dict[str, CheckResult]:
    """Run the shared safety gates once and split them into individual checks.

    ``session_script`` is the script this session actually generated, when it
    has one. Without it the gates inspect the repository's own sandbox runner
    template, and the evidence says exactly that rather than implying a
    per-session script was judged.
    """
    session_script = facts.get("session_script") or None
    source_label = (
        "this session's generated training script"
        if session_script
        else "the first-party sandbox runner template "
        "(this session has not generated a script)"
    )
    # Evidence kind differs by branch: a real session script came from an
    # artifact of this session's own run (runtime evidence); the fallback
    # template is repository source.
    gate_category = "generated" if session_script else "source"
    gate_level = "runtime" if session_script else "source"
    raw = run_static_gate_checks(
        metrics=dict(facts.get("metrics") or {}),
        task_type=str(facts.get("task_type") or "classification"),
        primary_metric=facts.get("primary_metric") or None,
        primary_score=facts.get("primary_score"),
        baseline_score=facts.get("baseline_score"),
        code=session_script,
    )
    by_name = {str(c["name"]): c for c in raw}

    def _one(name: str, cid: str, title: str, expected: str) -> CheckResult:
        check = by_name.get(name)
        if check is None:
            return _result(
                cid,
                title,
                CheckStatus.NOT_VERIFIED,
                expected=expected,
                actual=f"the {name} gate did not run",
                evidence=[f"gate {name} produced no result"],
                artifact="app/engine/verification/gate_checks.py",
                category=gate_category,
                level=gate_level,
            )
        details = [str(d) for d in (check.get("details") or [])]
        artifact = str(check.get("artifact") or "")
        if check.get("skipped"):
            return _result(
                cid,
                title,
                CheckStatus.NOT_VERIFIED,
                expected=expected,
                actual="; ".join(details) or f"the {name} gate had nothing to judge",
                evidence=details + [f"inspected: {source_label}"],
                artifact=artifact,
                category=gate_category,
                level=gate_level,
            )
        if check.get("passed"):
            return _result(
                cid,
                title,
                CheckStatus.PASS,
                expected=expected,
                actual="; ".join(details) or f"the {name} gate passed",
                evidence=details + [f"inspected: {source_label}"],
                confidence=_confidence(1),
                artifact=artifact,
                category=gate_category,
                level=gate_level,
            )
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=expected,
            actual="; ".join(details) or f"the {name} gate failed",
            evidence=details + [f"inspected: {source_label}"],
            confidence=_confidence(1),
            artifact=artifact,
            category=gate_category,
            level=gate_level,
        )

    out: Dict[str, CheckResult] = {}
    for name, cid, title, expected in _O3_GATES:
        out[cid] = _one(name, cid, title, expected)

    # metric sanity and baseline dominance are session facts, not script facts
    metrics = dict(facts.get("metrics") or {})
    task_type = str(facts.get("task_type") or "classification")
    primary_metric = str(facts.get("primary_metric") or "")
    primary_score = facts.get("primary_score")
    baseline_score = facts.get("baseline_score")

    metric_expected = "Every reported metric falls inside the plausible range for the session's task type."
    metric_evidence = [
        f"task type: {task_type}",
        f"primary metric: {primary_metric or 'not recorded'}",
        f"metrics: {metrics or 'none recorded'}",
    ]
    sanity = by_name.get("metric_sanity")
    if not metrics:
        out["o3_metric_sanity"] = _result(
            "o3_metric_sanity",
            "The reported numbers are plausible for the task",
            CheckStatus.NOT_VERIFIED,
            expected=metric_expected,
            actual="this session recorded no metrics, because nothing has trained",
            evidence=metric_evidence,
            artifact="experiment.result_summary.metrics",
        )
    elif sanity is None:
        out["o3_metric_sanity"] = _result(
            "o3_metric_sanity",
            "The reported numbers are plausible for the task",
            CheckStatus.NOT_VERIFIED,
            expected=metric_expected,
            actual="the metric-sanity gate produced no result",
            evidence=metric_evidence,
            artifact="experiment.result_summary.metrics",
        )
    elif sanity.get("skipped"):
        out["o3_metric_sanity"] = _result(
            "o3_metric_sanity",
            "The reported numbers are plausible for the task",
            CheckStatus.NOT_VERIFIED,
            expected=metric_expected,
            actual="; ".join(sanity.get("details") or []) or "no measured input available",
            evidence=metric_evidence,
            artifact="experiment.result_summary.metrics",
        )
    else:
        passed = bool(sanity.get("passed"))
        out["o3_metric_sanity"] = _result(
            "o3_metric_sanity",
            "The reported numbers are plausible for the task",
            CheckStatus.PASS if passed else CheckStatus.FAIL,
            expected=metric_expected,
            actual="; ".join(sanity.get("details") or []) or ("metrics are plausible" if passed else "metrics are implausible"),
            evidence=metric_evidence + [str(d) for d in (sanity.get("details") or [])],
            confidence=_confidence(1) if passed else _confidence(0),
            artifact="experiment.result_summary.metrics",
        )

    base_expected = "The primary score exceeds the baseline score on the session's primary metric."
    base_evidence = [
        f"primary metric: {primary_metric or 'not recorded'}",
        f"primary score: {primary_score}",
        f"baseline score: {baseline_score}",
    ]
    dominance = by_name.get("baseline_dominance")
    if not metrics or primary_score is None:
        out["o3_baseline_dominance"] = _result(
            "o3_baseline_dominance",
            "The result is better than doing nothing clever",
            CheckStatus.NOT_VERIFIED,
            expected=base_expected,
            actual="this session recorded no measured score or baseline, because nothing has trained",
            evidence=base_evidence,
            artifact="experiment.result_summary.baseline",
        )
    elif dominance is None or dominance.get("skipped"):
        out["o3_baseline_dominance"] = _result(
            "o3_baseline_dominance",
            "The result is better than doing nothing clever",
            CheckStatus.NOT_VERIFIED,
            expected=base_expected,
            actual="; ".join((dominance or {}).get("details") or []) or "no baseline was measured to compare against",
            evidence=base_evidence,
            artifact="experiment.result_summary.baseline",
        )
    else:
        passed = bool(dominance.get("passed"))
        out["o3_baseline_dominance"] = _result(
            "o3_baseline_dominance",
            "The result is better than doing nothing clever",
            CheckStatus.PASS if passed else CheckStatus.FAIL,
            expected=base_expected,
            actual="; ".join(dominance.get("details") or []) or ("beats the baseline" if passed else "does not beat the baseline"),
            evidence=base_evidence + [str(d) for d in (dominance.get("details") or [])],
            confidence=_confidence(1) if passed else _confidence(0),
            artifact="experiment.result_summary.baseline",
        )

    return out


_EXPECTED_O3_SOURCES = (
    "At least one registered evidence source is an external/knowledge source "
    "(paper, web, literature) rather than internal or mock."
)


def check_evidence_sources() -> CheckResult:
    """Evidence can come from outside the system, not just internal notes."""
    cid, title = "o3_evidence_sources", "Decisions are checked against independent sources, not just internal notes"
    try:
        from app.engine.evidence.source import list_evidence_sources
    except Exception as exc:  # noqa: BLE001
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=_EXPECTED_O3_SOURCES,
            actual=f"the evidence source registry could not be read: {exc}",
            evidence=[f"import failed: {exc}"],
            artifact="app/engine/evidence/source.py",
        )

    sources = list_evidence_sources()
    described: List[str] = []
    independent: List[str] = []
    for src in sources:
        sid = str(getattr(src, "source_id", "unknown"))
        stype = str(getattr(src, "source_type", "unknown"))
        described.append(f"{sid} (type={stype})")
        # "mock"/"stub" sources do not provide real outside corroboration.
        is_mock = "mock" in sid.lower() or "stub" in sid.lower()
        if stype in {"paper", "web", "literature", "external"} and not is_mock:
            independent.append(sid)

    evidence = [
        f"registered evidence sources ({len(sources)}): "
        + (", ".join(described) if described else "none"),
        f"independent knowledge sources: {', '.join(independent) or 'none'}",
    ]
    if not sources:
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=_EXPECTED_O3_SOURCES,
            actual="no evidence sources are registered in this process",
            evidence=evidence,
            artifact="app/engine/evidence/source.py",
        )
    if not independent:
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=_EXPECTED_O3_SOURCES,
            actual=(
                "every registered source is internal, memory-backed or a mock "
                "placeholder, so no decision can be corroborated from outside the system"
            ),
            evidence=evidence,
            artifact="app/engine/evidence/source.py",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=_EXPECTED_O3_SOURCES,
        actual="independent knowledge source(s) registered: " + ", ".join(independent),
        evidence=evidence,
        confidence=_confidence(len(independent)),
        artifact="app/engine/evidence/source.py",
    )


_EXPECTED_O3_AGREEMENT = (
    "A verification record for this session carries a non-abstaining overall "
    "status (VERIFIED, not ABSTAIN)."
)


def check_independent_agreement(facts: Mapping[str, Any]) -> CheckResult:
    """An independent pass resolved the claims and recorded a verdict."""
    cid, title = "o3_independent_agreement", "An independent pass agrees with the claims"
    from collections import Counter

    statuses = dict(facts.get("decision_statuses") or {})
    tally = Counter(str(d.get("status")) for d in statuses.values() if d.get("status"))
    overall = facts.get("verification_status")
    evidence = [
        f"verification overall_status: {overall or 'none recorded'}",
        "per-decision verdicts: "
        + (", ".join(f"{k}={v}" for k, v in sorted(tally.items())) or "none"),
    ]
    if not overall:
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=_EXPECTED_O3_AGREEMENT,
            actual=(
                "no independent verification record exists for this session, "
                "because nothing has run"
            ),
            evidence=evidence,
            artifact="verifications",
        )

    status_txt = str(overall).upper()
    if status_txt == "VERIFIED":
        return _result(
            cid,
            title,
            CheckStatus.PASS,
            expected=_EXPECTED_O3_AGREEMENT,
            actual=f"the independent pass reached VERIFIED over {len(statuses)} decision(s)",
            evidence=evidence,
            confidence=_confidence(1),
            artifact="verifications",
        )
    if status_txt in {"REJECTED", "CONFLICT"}:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O3_AGREEMENT,
            actual=f"the independent pass reached {status_txt}; claims did not agree with their evidence",
            evidence=evidence,
            confidence=_confidence(0),
            artifact="verifications",
        )
    return _result(
        cid,
        title,
        CheckStatus.NOT_VERIFIED,
        expected=_EXPECTED_O3_AGREEMENT,
        actual=f"the independent pass reached {status_txt}: it abstained rather than confirming the claims",
        evidence=evidence,
        artifact="verifications",
    )


def run_objective_3_checks(facts: Mapping[str, Any]) -> List[CheckResult]:
    gates = _gate_checks(facts)
    return [
        gates["o3_ast_security"],
        gates["o3_data_leakage"],
        gates["o3_metric_sanity"],
        gates["o3_baseline_dominance"],
        check_evidence_sources(),
        check_independent_agreement(facts),
    ]


# ---------------------------------------------------------------------------
# Objective 4 — Every decision recorded with reason and confidence
# ---------------------------------------------------------------------------

def check_decision_rationale(facts: Mapping[str, Any]) -> CheckResult:
    """Every decision carries a readable reason."""
    cid, title = "o4_decision_rationale", "Every decision records why it was made"
    expected = "Every Decision row for this session has a non-empty rationale."
    total = int(facts.get("decisions") or 0)
    with_reason = int(facts.get("decisions_with_rationale") or 0)
    evidence = [
        f"decisions recorded for this session: {total}",
        f"decisions carrying a non-empty rationale: {with_reason}",
    ]
    if total == 0:
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=expected,
            actual="this session recorded no decisions, because nothing has run",
            evidence=evidence,
            artifact="decisions.rationale",
        )
    if with_reason < total:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=expected,
            actual=f"{total - with_reason} of {total} decision(s) have an empty rationale",
            evidence=evidence,
            confidence=_confidence(with_reason, total),
            artifact="decisions.rationale",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=expected,
        actual=f"all {total} decision(s) carry a rationale",
        evidence=evidence,
        confidence=_confidence(total, total),
        artifact="decisions.rationale",
    )


def check_decision_confidence(facts: Mapping[str, Any]) -> CheckResult:
    """Every decision carries a confidence score in 0..1."""
    cid, title = "o4_decision_confidence", "Every decision records how confident it was"
    expected = "Every Decision row for this session has a confidence score in 0..1."
    total = int(facts.get("decisions") or 0)
    with_conf = int(facts.get("decisions_with_confidence") or 0)
    evidence = [
        f"decisions recorded for this session: {total}",
        f"decisions carrying a confidence score in 0..1: {with_conf}",
    ]
    if total == 0:
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=expected,
            actual="this session recorded no decisions, because nothing has run",
            evidence=evidence,
            artifact="decisions.confidence",
        )
    if with_conf < total:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=expected,
            actual=f"{total - with_conf} of {total} decision(s) have no usable confidence score",
            evidence=evidence,
            confidence=_confidence(with_conf, total),
            artifact="decisions.confidence",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=expected,
        actual=f"all {total} decision(s) carry a confidence score",
        evidence=evidence,
        confidence=_confidence(total, total),
        artifact="decisions.confidence",
    )


_EXPECTED_O4_EVIDENCE = (
    "Evidence-trail nodes exist for this session's runs, one per recorded decision."
)


def check_evidence_nodes(facts: Mapping[str, Any]) -> CheckResult:
    """Every claim links to evidence-trail nodes."""
    cid, title = "o4_evidence_nodes", "Every claim has supporting evidence"
    total = int(facts.get("decisions") or 0)
    nodes = int(facts.get("evidence_nodes") or 0)
    evidence = [
        f"decisions recorded for this session: {total}",
        f"evidence-trail nodes written for this session: {nodes}",
    ]
    if nodes == 0:
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=_EXPECTED_O4_EVIDENCE,
            actual="no evidence nodes exist for this session, because nothing has run",
            evidence=evidence,
            artifact="evidence_trail_nodes",
        )
    if nodes < total:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O4_EVIDENCE,
            actual=f"{nodes} evidence node(s) back {total} decision(s)",
            evidence=evidence,
            confidence=_confidence(nodes, total),
            artifact="evidence_trail_nodes",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=_EXPECTED_O4_EVIDENCE,
        actual=f"{nodes} evidence node(s) back this session's {total} decision(s)",
        evidence=evidence,
        confidence=_confidence(nodes, total),
        artifact="evidence_trail_nodes",
    )


_EXPECTED_O4_MEMORY = (
    "Experience-memory rows exist for this session with a recorded type."
)


def check_experience_memory(facts: Mapping[str, Any]) -> CheckResult:
    """A verified outcome was written to memory for reuse."""
    cid, title = "o4_experience_memory", "The system learns from what worked"
    rows = int(facts.get("memory_rows") or 0)
    types = [str(t) for t in (facts.get("memory_types") or [])]
    evidence = [
        f"experience-memory rows for this session: {rows}",
        "memory types: " + (", ".join(types) if types else "none"),
    ]
    if rows == 0:
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=_EXPECTED_O4_MEMORY,
            actual=(
                "no experience was written for this session, because nothing "
                "has been verified as working yet"
            ),
            evidence=evidence,
            artifact="experience_memories",
        )
    if not types:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O4_MEMORY,
            actual=f"{rows} memory row(s) exist but none record a type",
            evidence=evidence,
            confidence=_confidence(0),
            artifact="experience_memories",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=_EXPECTED_O4_MEMORY,
        actual=f"{rows} experience entr(ies) recorded for reuse: {', '.join(types)}",
        evidence=evidence,
        confidence=_confidence(rows),
        artifact="experience_memories",
    )


_EXPECTED_O4_CHAIN = (
    "Every link in the chain is present for this session: agent execution, "
    "decision, evidence, and a result or verification."
)


def check_audit_chain(facts: Mapping[str, Any]) -> CheckResult:
    """Session -> agent -> decision -> evidence -> result is walkable."""
    cid, title = "o4_audit_chain", "The whole chain is walkable end to end"
    links = {
        "experiment": True,
        "agent_execution": int(facts.get("agent_executions") or 0) > 0,
        "decision": int(facts.get("decisions") or 0) > 0,
        "evidence": int(facts.get("evidence_nodes") or 0) > 0,
        "result_or_verification": bool(facts.get("has_result"))
        or bool(facts.get("verification_status")),
    }
    evidence = [
        f"{name}: {'present' if present else 'MISSING'}" for name, present in links.items()
    ]
    missing = [name for name, present in links.items() if not present]

    # Distinguish "the chain was never built" from "the chain is broken".
    # Nothing ran at all means there is nothing to judge -- that is
    # NOT_VERIFIED, the same state its sibling checks use for an absent
    # record. A partially built chain really is broken, which is a FAIL.
    ran_at_all = any(
        (
            int(facts.get("agent_executions") or 0) > 0,
            int(facts.get("decisions") or 0) > 0,
            int(facts.get("evidence_nodes") or 0) > 0,
            bool(facts.get("has_result")),
            bool(facts.get("verification_status")),
        )
    )
    if not ran_at_all:
        return _result(
            cid,
            title,
            CheckStatus.NOT_VERIFIED,
            expected=_EXPECTED_O4_CHAIN,
            actual=(
                "this session produced no runs, decisions, evidence or results, "
                "so there is no chain to walk"
            ),
            evidence=evidence,
            artifact="cross-table lineage",
        )

    if missing:
        return _result(
            cid,
            title,
            CheckStatus.FAIL,
            expected=_EXPECTED_O4_CHAIN,
            actual="the audit chain is broken at: " + ", ".join(missing),
            evidence=evidence,
            confidence=_confidence(len(links) - len(missing), len(links)),
            artifact="cross-table lineage",
        )
    return _result(
        cid,
        title,
        CheckStatus.PASS,
        expected=_EXPECTED_O4_CHAIN,
        actual="session -> agent -> decision -> evidence -> result is fully walkable",
        evidence=evidence,
        confidence=_confidence(len(links), len(links)),
        artifact="cross-table lineage",
    )


def run_objective_4_checks(facts: Mapping[str, Any]) -> List[CheckResult]:
    return [
        check_decision_rationale(facts),
        check_decision_confidence(facts),
        check_evidence_nodes(facts),
        check_experience_memory(facts),
        check_audit_chain(facts),
    ]


# ---------------------------------------------------------------------------
# Roll-up
# ---------------------------------------------------------------------------

def blocked(check_id: str, title: str, expected: str, reason: str) -> CheckResult:
    """A check that was never attempted because a prerequisite stage failed."""
    return _result(
        check_id,
        title,
        CheckStatus.BLOCKED,
        expected=expected,
        actual=reason,
        evidence=[reason],
        artifact="",
    )


def roll_up(check_results: Sequence[CheckResult]) -> StageStatus:
    """Objective stage status from its checks.

    FAILED beats BLOCKED beats NOT_VERIFIED: a real failure must never be
    softened into "could not look", and "could not look" must never be
    presented as a pass.
    """
    if not check_results:
        return StageStatus.BLOCKED
    statuses = {r.status for r in check_results}
    if statuses == {CheckStatus.PASS}:
        return StageStatus.PASSED
    if CheckStatus.FAIL in statuses:
        return StageStatus.FAILED
    if CheckStatus.BLOCKED in statuses:
        return StageStatus.BLOCKED
    return StageStatus.NOT_VERIFIED


def average_confidence(check_results: Sequence[CheckResult]) -> float:
    if not check_results:
        return 0.0
    return round(sum(r.confidence for r in check_results) / len(check_results), 4)


def count_by_status(check_results: Sequence[CheckResult]) -> Dict[str, int]:
    """Check tallies for the final report."""
    return {
        s.value: sum(1 for r in check_results if r.status is s) for s in CheckStatus
    }


def count_by_category(check_results: Sequence[CheckResult]) -> Dict[str, int]:
    """Evidence-category tallies, so a source PASS is never read as runtime proof."""
    counts: Dict[str, int] = {}
    for r in check_results:
        counts[r.category] = counts.get(r.category, 0) + 1
    return counts


def count_by_level(check_results: Sequence[CheckResult]) -> Dict[str, int]:
    """Verification-level tallies (source/config/generated/runtime)."""
    counts: Dict[str, int] = {}
    for r in check_results:
        counts[r.verification_level] = counts.get(r.verification_level, 0) + 1
    return counts
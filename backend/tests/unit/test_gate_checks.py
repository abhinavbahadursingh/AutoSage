"""Unit tests for static gate checks (AST/security, leakage, metric sanity, baseline)."""
from __future__ import annotations

from app.engine.verification.gate_checks import (
    CHECK_AST_SECURITY,
    CHECK_DATA_LEAKAGE,
    CHECK_METRIC_SANITY,
    CHECK_BASELINE_DOMINANCE,
    run_static_gate_checks,
    failed_checks,
)
from app.engine.verification.ast_checker import ASTSecurityChecker
from app.engine.verification.leakage_detector import LeakageDetector as L


def test_ast_checker_rejects_subprocess():
    malicious = "import subprocess\nsubprocess.run(['ls'])"
    passed, errors = ASTSecurityChecker.check_security(malicious, allow_io_modules=("os", "sys"))
    assert passed is False
    assert any("subprocess" in e for e in errors)


def test_ast_checker_allows_os_when_allowed():
    code = "import os\nx = os.environ.get('PATH')\nprint(x)"
    passed, errors = ASTSecurityChecker.check_security(code, allow_io_modules=("os", "sys"))
    assert passed is True
    assert len(errors) == 0


def test_ast_checker_blocks_os_system_even_when_allowed():
    code = "import os\nos.system('rm -rf /')"
    passed, errors = ASTSecurityChecker.check_security(code, allow_io_modules=("os", "sys"))
    assert passed is False
    assert any("os.system" in e for e in errors)


def test_leakage_detector_flags_no_split():
    leak = """
import pandas as pd
from sklearn.linear_model import LogisticRegression
df = pd.read_csv("x.csv")
y = df["t"]
X = df
m = LogisticRegression()
m.fit(X, y)
"""
    passed, errors = L.detect_leakage(leak)
    assert passed is False
    assert any("no train/test split" in e for e in errors)


def test_leakage_detector_flags_fit_on_test():
    leak = """
from sklearn.model_selection import train_test_split
X_tr, X_te, y_tr, y_te = train_test_split(X, y)
p.fit_transform(X_te)
m.fit(X_te, y_te)
"""
    passed, errors = L.detect_leakage(leak)
    assert passed is False
    assert any("held-out data" in e for e in errors)


def test_leakage_detector_flags_fit_full_before_split():
    leak = """
from sklearn.model_selection import train_test_split
X_tr, X_te = train_test_split(X)
p.fit(X)
"""
    passed, errors = L.detect_leakage(leak)
    assert passed is False
    assert any("full dataset before splitting" in e for e in errors)


def test_leakage_detector_passes_clean_script():
    # Our actual train_script.py passes
    import pathlib
    script = pathlib.Path(__file__).resolve().parents[2] / "app" / "engine" / "sandbox" / "train_script.py"
    code = script.read_text(encoding="utf-8")
    passed, errors = L.detect_leakage(code)
    assert passed is True
    assert len(errors) == 0


def test_gate_ast_security_passes_runner():
    results = run_static_gate_checks(
        metrics={},
        task_type="classification",
        include=[CHECK_AST_SECURITY],
    )
    check = next(r for r in results if r["name"] == CHECK_AST_SECURITY)
    assert check["passed"] is True
    assert check["skipped"] is False


def test_gate_leakage_passes_runner():
    results = run_static_gate_checks(
        metrics={},
        task_type="classification",
        include=[CHECK_DATA_LEAKAGE],
    )
    check = next(r for r in results if r["name"] == CHECK_DATA_LEAKAGE)
    assert check["passed"] is True
    assert check["skipped"] is False


def test_gate_metric_sanity_skipped_when_no_metrics():
    results = run_static_gate_checks(
        metrics={},
        task_type="classification",
        include=[CHECK_METRIC_SANITY],
    )
    check = next(r for r in results if r["name"] == CHECK_METRIC_SANITY)
    assert check["passed"] is True
    assert check["skipped"] is True


def test_gate_metric_sanity_flags_perfect_accuracy():
    results = run_static_gate_checks(
        metrics={"accuracy": 1.0, "f1": 0.9},
        task_type="classification",
        include=[CHECK_METRIC_SANITY],
    )
    check = next(r for r in results if r["name"] == CHECK_METRIC_SANITY)
    assert check["passed"] is False
    assert any("1.0" in d for d in check["details"])


def test_gate_baseline_dominance_passes_when_beats():
    results = run_static_gate_checks(
        metrics={},
        task_type="classification",
        primary_metric="accuracy",
        primary_score=0.91,
        baseline_score=0.72,
        include=[CHECK_BASELINE_DOMINANCE],
    )
    check = next(r for r in results if r["name"] == CHECK_BASELINE_DOMINANCE)
    assert check["passed"] is True
    assert "higher is better" in check["details"][0]


def test_gate_baseline_dominance_fails_when_loses():
    results = run_static_gate_checks(
        metrics={},
        task_type="classification",
        primary_metric="accuracy",
        primary_score=0.72,
        baseline_score=0.91,
        include=[CHECK_BASELINE_DOMINANCE],
    )
    check = next(r for r in results if r["name"] == CHECK_BASELINE_DOMINANCE)
    assert check["passed"] is False


def test_gate_baseline_dominance_skipped_when_missing():
    results = run_static_gate_checks(
        metrics={},
        task_type="classification",
        primary_metric="accuracy",
        primary_score=None,
        baseline_score=0.72,
        include=[CHECK_BASELINE_DOMINANCE],
    )
    check = next(r for r in results if r["name"] == CHECK_BASELINE_DOMINANCE)
    assert check["passed"] is True
    assert check["skipped"] is True


def test_failed_checks_filters_correctly():
    r = [
        {"name": "a", "passed": True, "skipped": False},
        {"name": "b", "passed": False, "skipped": False},
        {"name": "c", "passed": False, "skipped": True},
    ]
    assert [c["name"] for c in failed_checks(r)] == ["b"]


def test_gate_all_four_checks_run():
    results = run_static_gate_checks(
        metrics={"accuracy": 0.91},
        task_type="classification",
        primary_metric="accuracy",
        primary_score=0.91,
        baseline_score=0.72,
    )
    names = {r["name"] for r in results}
    assert names == {
        CHECK_AST_SECURITY,
        CHECK_DATA_LEAKAGE,
        CHECK_METRIC_SANITY,
        CHECK_BASELINE_DOMINANCE,
    }


def test_gate_includes_artifact_names():
    results = run_static_gate_checks(
        metrics={"accuracy": 0.91},
        task_type="classification",
        primary_metric="accuracy",
        primary_score=0.91,
        baseline_score=0.72,
    )
    for r in results:
        assert "artifact" in r and isinstance(r["artifact"], str)
        assert r["artifact"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
"""Unit tests for AST Security Checker."""
from app.engine.verification.ast_checker import ASTSecurityChecker

def test_ast_checker_rejects_os_import():
    malicious_code = "import os\nos.system('rm -rf /')"
    passed, errors = ASTSecurityChecker.check_security(malicious_code)
    assert passed is False
    assert any("Illegal import detected: os" in err for err in errors)

def test_ast_checker_rejects_eval():
    malicious_code = "x = '1+1'\ny = eval(x)"
    passed, errors = ASTSecurityChecker.check_security(malicious_code)
    assert passed is False
    assert any("Illegal dynamic execution call: eval()" in err for err in errors)

def test_ast_checker_allows_safe_ml_code():
    safe_code = """
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

clf = RandomForestClassifier(n_estimators=100)
"""
    passed, errors = ASTSecurityChecker.check_security(safe_code)
    assert passed is True
    assert len(errors) == 0

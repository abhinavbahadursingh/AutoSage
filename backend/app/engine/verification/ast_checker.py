"""AST Code Syntax and Security Checker."""
import ast
from typing import List, Tuple

DISALLOWED_MODULES = {"os", "sys", "subprocess", "socket", "shutil", "pty", "requests", "urllib"}

class ASTSecurityChecker:
    @staticmethod
    def check_security(code: str) -> Tuple[bool, List[str]]:
        errors = []
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, [f"SyntaxError: {str(e)}"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in DISALLOWED_MODULES:
                        errors.append(f"Illegal import detected: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in DISALLOWED_MODULES:
                    errors.append(f"Illegal from-import detected: {node.module}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "__import__"}:
                    errors.append(f"Illegal dynamic execution call: {node.func.id}()")

        return len(errors) == 0, errors

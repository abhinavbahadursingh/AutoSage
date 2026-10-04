"""AST Code Syntax and Security Checker."""
import ast
from typing import Iterable, List, Tuple

DISALLOWED_MODULES = {"os", "sys", "subprocess", "socket", "shutil", "pty", "requests", "urllib"}

# Process-execution / shell entry points on otherwise legitimate IO modules.
# Allowed IO modules (see ``allow_io_modules``) may still not start processes.
DANGEROUS_ATTRS = {
    "system", "popen", "startfile",
    "execv", "execve", "execvp", "execvpe",
    "execl", "execle", "execlp", "execlpe",
    "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "spawnl", "spawnle", "spawnlp", "spawnlpe",
}

class ASTSecurityChecker:
    @staticmethod
    def check_security(
        code: str,
        allow_io_modules: Iterable[str] = (),
    ) -> Tuple[bool, List[str]]:
        """Static security scan of ``code``.

        ``allow_io_modules`` lifts the module-level import ban for trusted
        first-party code (the sandbox runner needs ``os``/``sys`` for env and
        file IO inside the container). Dynamic execution stays banned for
        everyone, and process-spawning helpers on allowed modules are still
        reported.
        """
        allowed = {str(m).split(".")[0] for m in allow_io_modules}
        errors = []
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, [f"SyntaxError: {str(e)}"]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split('.')[0]
                    if root in DISALLOWED_MODULES and root not in allowed:
                        errors.append(f"Illegal import detected: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split('.')[0]
                    if root in DISALLOWED_MODULES and root not in allowed:
                        errors.append(f"Illegal from-import detected: {node.module}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "__import__"}:
                    errors.append(f"Illegal dynamic execution call: {node.func.id}()")
                elif (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in allowed
                    and node.func.attr in DANGEROUS_ATTRS
                ):
                    errors.append(
                        f"Illegal process execution call: {node.func.value.id}.{node.func.attr}()"
                    )

        return len(errors) == 0, errors

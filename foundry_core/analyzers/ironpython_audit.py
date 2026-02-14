"""IronPython 2.7 compatibility audit: f-strings, type hints, walrus, etc."""

import ast
from pathlib import Path
from typing import Any


# IronPython 2.7 incompatible constructs
IPY_INCOMPATIBLE = {
    "f_string": (ast.JoinedStr, "f-strings (use .format() or %% for IronPython 2.7)"),
    "type_annotation": (ast.FunctionDef, "type hints (remove for IronPython 2.7)"),
    "walrus": (ast.NamedExpr, ":="),
    "match": (ast.Match, "match statement (Python 3.10+)"),
    "union_syntax": (None, "X | Y union syntax (use Optional/Union from typing)"),
}


def _has_union_annotation(n: ast.AST) -> bool:
    """True if node is BinOp with BitOr (X | Y union syntax)."""
    return isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr)


def _check_union_in_annotations(tree: ast.AST) -> list[tuple[int, str]]:
    """Find X | Y union syntax in type annotations via AST. Returns [(line, msg)]."""
    findings = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.FunctionDef):
            if node.returns and _has_union_annotation(node.returns):
                findings.append((node.lineno, "Return type uses X | Y union (use Optional/Union)"))
            for arg in node.args.args:
                if arg.annotation and _has_union_annotation(arg.annotation):
                    findings.append((arg.lineno or node.lineno, "Arg type uses X | Y union (use Optional/Union)"))
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return findings


def _audit_script(script_path: Path) -> list[dict[str, Any]]:
    findings = []
    try:
        text = script_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        tree = ast.parse(text)

        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                findings.append({
                    "type": "f_string",
                    "line": node.lineno,
                    "message": "f-string (use .format() or %% for IronPython 2.7)",
                    "confidence": "high",
                })
            elif isinstance(node, ast.NamedExpr):
                findings.append({
                    "type": "walrus",
                    "line": node.lineno,
                    "message": "Walrus operator := (Python 3.8+)",
                    "confidence": "high",
                })
            elif isinstance(node, ast.Match):
                findings.append({
                    "type": "match",
                    "line": node.lineno,
                    "message": "match statement (Python 3.10+)",
                    "confidence": "high",
                })
            elif isinstance(node, ast.FunctionDef):
                if node.returns:
                    findings.append({
                        "type": "return_annotation",
                        "line": node.lineno,
                        "message": "Return type annotation",
                        "confidence": "high",
                    })
                for arg in node.args.args:
                    if arg.annotation:
                        findings.append({
                            "type": "arg_annotation",
                            "line": arg.lineno or node.lineno,
                            "message": "Argument type annotation",
                            "confidence": "high",
                        })

        for line_no, msg in _check_union_in_annotations(tree):
            findings.append({
                "type": "union_syntax",
                "line": line_no,
                "message": msg,
                "confidence": "high",
            })

    except (SyntaxError, OSError):
        pass
    return findings


class IronPythonAuditAnalyzer:
    """Finds IronPython 2.7 incompatible constructs."""

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()

    def audit(self, script_paths: list[str]) -> list[dict[str, Any]]:
        """Return findings for each script."""
        results = []
        for sp in script_paths:
            path = self.repo_root / sp
            for f in _audit_script(path):
                results.append({"script": sp, **f})
        return results

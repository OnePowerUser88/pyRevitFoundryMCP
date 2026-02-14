"""Audits imports: unused, raw RevitAPI, wrapper suggestions."""

import ast
from pathlib import Path
from typing import Any


def _get_used_names(tree: ast.AST) -> set[str]:
    """Collect names used in the AST (not in imports)."""
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
    return used


def _audit_script(script_path: Path, core_symbols: dict[str, str] | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        text = script_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
        used = _get_used_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    base = alias.name.split(".")[0]
                    if name not in used and base not in used:
                        findings.append({
                            "type": "unused_import",
                            "line": node.lineno,
                            "name": alias.name,
                            "confidence": "high",
                        })
                    if alias.name.startswith("Autodesk.Revit") or alias.name in (
                        "RevitAPI",
                        "RevitAPIUI",
                    ):
                        findings.append({
                            "type": "raw_revit_import",
                            "line": node.lineno,
                            "name": alias.name,
                            "confidence": "medium" if core_symbols else "low",
                        })
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names or []:
                        name = alias.asname or alias.name
                        if name not in used:
                            findings.append({
                                "type": "unused_import",
                                "line": node.lineno,
                                "name": "%s.%s" % (node.module, alias.name),
                                "confidence": "high",
                            })
    except (SyntaxError, OSError):
        pass
    return findings


class ImportAuditAnalyzer:
    """Finds unused imports and raw Revit API usage."""

    def __init__(self, repo_root: str | Path, core_root: str | Path | None = None):
        self.repo_root = Path(repo_root).resolve()
        self.core_index = None
        if core_root:
            from foundry_core.indexers.core_indexer import CoreIndexer

            self.core_index = CoreIndexer(core_root).index()

    def audit(self, script_paths: list[str]) -> list[dict[str, Any]]:
        """Return findings for each script."""
        findings: list[dict[str, Any]] = []
        core_symbols = self.core_index.get("symbols") if self.core_index else None
        for sp in script_paths:
            path = self.repo_root / sp
            for f in _audit_script(path, core_symbols):
                f["script"] = sp
                findings.append(f)
        return findings

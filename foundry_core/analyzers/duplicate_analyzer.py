"""Function-level duplicate code detection."""

import ast
import hashlib
from pathlib import Path
from typing import Any

from foundry_core.indexers.repo_indexer import RepoIndexer


def _normalize_ast(node: ast.AST) -> str:
    """Normalize AST to string for hashing (strip identifiers/literals)."""
    if isinstance(node, ast.FunctionDef):
        body_str = "".join(_normalize_ast(n) for n in node.body)
        return "def(%s):%s" % (len(node.args.args), body_str)
    if isinstance(node, ast.Assign):
        return "assign"
    if isinstance(node, ast.Expr):
        return "expr"
    if isinstance(node, ast.Return):
        return "return"
    if isinstance(node, ast.If):
        return "if" + "".join(_normalize_ast(n) for n in node.body)
    return ""


def _hash_body(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _extract_functions(script_path: Path) -> list[tuple[int, str, str]]:
    """Return (line, name, normalized_body) for each function."""
    result: list[tuple[int, str, str]] = []
    try:
        tree = ast.parse(script_path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                body = _normalize_ast(node)
                result.append((node.lineno, node.name, body))
    except (SyntaxError, OSError):
        pass
    return result


class DuplicateCodeAnalyzer:
    """Finds duplicate/near-duplicate functions across scripts."""

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()

    def analyze(
        self,
        script_paths: list[str] | None = None,
        limit: int | None = None,
        same_name_only: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Returns (clusters, findings).
        clusters: list of { hash, locations: [{script, line, name}] }
        limit: max clusters to return (by duplicate count desc).
        same_name_only: only cluster when all locations have the same function name (for safe extract).
        """
        if not script_paths:
            inv = RepoIndexer(self.repo_root).scan()
            script_paths = inv.get("py_files", [])
        hash_to_locs: dict[str, list[dict[str, str | int]]] = {}
        for sp in script_paths:
            path = self.repo_root / sp
            for line, name, body in _extract_functions(path):
                if len(body) < 20:
                    continue
                h = _hash_body(body)
                key = (h, name) if same_name_only else h
                loc = {"script": sp, "line": line, "name": name}
                hash_to_locs.setdefault(key, []).append(loc)
        clusters = []
        for key, locs in hash_to_locs.items():
            if len(locs) <= 1:
                continue
            h = key[0] if same_name_only else key
            clusters.append({"hash": h, "locations": locs})
        clusters.sort(key=lambda c: len(c["locations"]), reverse=True)
        if limit is not None and limit > 0:
            clusters = clusters[:limit]
        findings = [
            {"type": "duplicate", "cluster": c, "count": len(c["locations"])}
            for c in clusters
        ]
        return clusters, findings

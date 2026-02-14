"""Indexes pyRevit core clone for wrapper/import suggestions."""

import ast
import subprocess
from pathlib import Path
from typing import Any


def _get_git_sha(core_root: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=core_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _index_pyrevit_packages(core_root: Path) -> dict[str, list[str]]:
    """Build module -> exported symbols from pyrevitlib."""
    result: dict[str, list[str]] = {}
    pyrevit_path = core_root / "pyrevitlib" / "pyrevit"
    if not pyrevit_path.exists():
        return result
    for py_file in pyrevit_path.rglob("*.py"):
        rel = py_file.relative_to(pyrevit_path.parent)
        mod = str(rel.with_suffix("")).replace("\\", ".")
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
            symbols: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if not node.name.startswith("_"):
                        symbols.append(node.name)
            if symbols:
                result[mod] = symbols
        except (SyntaxError, OSError):
            pass
    return result


class CoreIndexer:
    """Indexes pyRevit core clone for wrapper availability."""

    def __init__(self, core_root: str | Path | None):
        self.core_root = Path(core_root).resolve() if core_root else None

    def index(self) -> dict[str, Any]:
        """Return { git_sha, modules, symbols } or empty if no core."""
        if not self.core_root or not self.core_root.exists():
            return {"git_sha": None, "modules": {}, "symbols": {}}
        modules = _index_pyrevit_packages(self.core_root)
        symbols: dict[str, str] = {}
        for mod, syms in modules.items():
            for s in syms:
                symbols[s] = mod
        return {
            "git_sha": _get_git_sha(self.core_root),
            "modules": modules,
            "symbols": symbols,
        }

"""Extract duplicate functions to lib/ modules and patch scripts."""

import ast
from pathlib import Path
from typing import Any

from foundry_core.analyzers.duplicate_analyzer import DuplicateCodeAnalyzer
from foundry_core.analyzers.lib_structure import LibStructureSuggester
from foundry_core.engine.patch_engine import PatchEngine
from foundry_core.indexers.repo_indexer import RepoIndexer


def _get_function_source(path: Path, func_name: str, func_line: int) -> str | None:
    """Extract function source by name and line. Returns None if not found."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name and node.lineno == func_line:
                lines = text.splitlines()
                start = node.lineno - 1
                end = getattr(node, "end_lineno", node.lineno + 1)
                return "\n".join(lines[start:end])
    except (SyntaxError, OSError):
        pass
    return None


def _remove_function_from_source(text: str, func_name: str, func_line: int) -> str:
    """Remove a function definition from source. Returns new source."""
    try:
        tree = ast.parse(text)
        lines = text.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name and node.lineno == func_line:
                start = node.lineno - 1
                end = getattr(node, "end_lineno", len(lines))
                new_lines = lines[:start] + lines[end:]
                return "\n".join(new_lines) + ("\n" if new_lines else "")
    except (SyntaxError, OSError):
        pass
    return text


def _ensure_import(lines: list[str], import_line: str) -> list[str]:
    """Add import_line after last import if not present."""
    import_line_stripped = import_line.strip()
    last_import_idx = -1
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("import ") or s.startswith("from "):
            last_import_idx = i
        if import_line_stripped in line:
            return lines
    if last_import_idx >= 0:
        return lines[: last_import_idx + 1] + [import_line] + lines[last_import_idx + 1 :]
    return [import_line] + lines


class ExtractToLibEngine:
    """Extracts duplicate functions to lib/ and patches scripts."""

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()
        self.patch_engine = PatchEngine(self.repo_root)

    def extract(
        self,
        clusters: list[dict[str, Any]] | None = None,
        cluster_indices: list[int] | None = None,
        mode: str = "dry_run",
        same_name_only: bool = True,
    ) -> dict[str, Any]:
        """
        Extract duplicate functions to lib/. mode: dry_run | write.
        cluster_indices: optional list of cluster indices to extract (0-based).
        same_name_only: when clusters is None, use only same-name clusters (default True, safe for extract).
        Returns { patches, extracted, errors }.
        """
        if clusters is None:
            clusters, _ = DuplicateCodeAnalyzer(self.repo_root).analyze(same_name_only=same_name_only)
        suggester = LibStructureSuggester(self.repo_root)
        proposal = suggester.propose(clusters, None)
        mapping = {m["function"]: m["suggested_module"] for m in proposal.get("mapping", [])}

        script_patches = []
        lib_patches = []
        extracted = []
        errors = []

        lib_contents: dict[str, list[str]] = {}

        for idx, cluster in enumerate(clusters):
            if cluster_indices is not None and idx not in cluster_indices:
                continue
            locs = cluster.get("locations", [])
            if len(locs) < 2:
                continue
            names = {loc.get("name") for loc in locs}
            if len(names) > 1:
                errors.append("Cluster %d: mixed function names %s (extract only same-name clusters)" % (idx, sorted(names)))
                continue
            first = locs[0]
            script_path = first.get("script")
            func_line = first.get("line")
            func_name = first.get("name", "?")
            if not script_path or not func_line:
                errors.append("Cluster %d: missing script/line" % idx)
                continue

            full_path = self.repo_root / script_path
            source = _get_function_source(full_path, func_name, func_line)
            if not source:
                errors.append("Cluster %d: could not extract %s from %s" % (idx, func_name, script_path))
                continue

            mod = mapping.get(func_name, "lib/utils.py")
            lib_contents.setdefault(mod, []).append(source)

            for loc in locs:
                sp = loc.get("script")
                ln = loc.get("line")
                name = loc.get("name")
                if not sp:
                    continue
                path = self.repo_root / sp
                if not path.exists():
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                new_text = _remove_function_from_source(text, name, ln)
                if new_text == text:
                    continue
                mod_import = mod.replace("/", ".").replace(".py", "")
                import_line = "from %s import %s" % (mod_import, name)
                new_lines = _ensure_import(new_text.splitlines(), import_line)
                new_text = "\n".join(new_lines) + ("\n" if new_lines else "")
                patch = self.patch_engine.create_edit_patch(sp, text, new_text, risk="high")
                script_patches.append(patch)
                extracted.append({"function": name, "script": sp, "module": mod})

        for mod, func_sources in lib_contents.items():
            content = "\n\n".join(fs for fs in func_sources if fs.strip())
            if not content:
                continue
            lib_path = self.repo_root / mod
            if lib_path.exists():
                old = lib_path.read_text(encoding="utf-8", errors="replace")
                content = old.rstrip() + "\n\n" + content
                patch = self.patch_engine.create_edit_patch(mod, old, content, risk="medium")
            else:
                patch = self.patch_engine.create_add_file_patch(mod, content, risk="medium")
            lib_patches.append(patch)

        patches = lib_patches + script_patches

        if mode == "write":
            applied, apply_errors = self.patch_engine.apply_patches(patches, mode="write")
            errors.extend(apply_errors)

        return {
            "patches": patches,
            "extracted": extracted,
            "errors": errors,
        }

"""Proposes lib/ module structure from duplicate clusters."""

from pathlib import Path
from typing import Any


class LibStructureSuggester:
    """Proposes lib module tree from duplicate clusters. Report-only in V1."""

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()

    def propose(
        self,
        clusters: list[dict[str, Any]] | None = None,
        preferences: dict[str, Any] | None = None,
        same_name_only: bool = False,
    ) -> dict[str, Any]:
        """
        Returns { suggested_tree, mapping, findings }.
        suggested_tree: { lib/utils.py: [...], lib/io.py: [...] }
        mapping: [{ function, from_scripts, suggested_module, same_name }]
        same_name_only: only include clusters where all locations have the same function name.
        """
        if not clusters:
            from foundry_core.analyzers.duplicate_analyzer import DuplicateCodeAnalyzer

            clusters, _ = DuplicateCodeAnalyzer(self.repo_root).analyze(same_name_only=same_name_only)
        suggested: dict[str, list[str]] = {
            "lib/utils.py": [],
            "lib/io.py": [],
            "lib/ui.py": [],
        }
        mapping: list[dict[str, Any]] = []
        for c in clusters:
            locs = c.get("locations", [])
            if len(locs) < 2:
                continue
            names = [loc.get("name", "?") for loc in locs]
            unique_names = set(names)
            same_name = len(unique_names) == 1
            if same_name_only and not same_name:
                continue
            scripts = [loc.get("script", "?") for loc in locs]
            mod = "lib/utils.py"
            if any("ui" in s.lower() or "form" in s.lower() for s in scripts):
                mod = "lib/ui.py"
            elif any("io" in s.lower() or "file" in s.lower() for s in scripts):
                mod = "lib/io.py"
            suggested.setdefault(mod, []).extend(names)
            mapping.append({
                "function": names[0] if names else "?",
                "from_scripts": scripts,
                "suggested_module": mod,
                "same_name": same_name,
                "mixed_names": sorted(unique_names) if not same_name else None,
            })
        return {
            "suggested_tree": suggested,
            "mapping": mapping,
            "findings": [{"type": "proposal", "mapping": m} for m in mapping],
        }

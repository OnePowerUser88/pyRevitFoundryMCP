"""Infers and generates bundle.yaml for pyRevit bundles missing it."""

import ast
import re
from pathlib import Path
from typing import Any

from foundry_core.indexers.repo_indexer import _find_bundle_entry_script


def _extract_title_from_script(script_path: Path) -> str | None:
    """Extract __title__ or docstring from script.py."""
    if not script_path.exists():
        return None
    try:
        text = script_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__title__":
                        if isinstance(node.value, ast.Constant):
                            return str(node.value.value)
                        break
        if ast.get_docstring(tree):
            first_line = ast.get_docstring(tree).split("\n")[0].strip()
            if first_line:
                return first_line[:80]
    except (SyntaxError, OSError):
        pass
    return None


def _infer_tooltip_from_folder(bundle_name: str) -> str:
    """Infer tooltip from bundle folder name (e.g. MyTool.pushbutton -> My Tool)."""
    base = bundle_name.split(".")[0] if "." in bundle_name else bundle_name
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)
    return spaced.strip() or base


class BundleYamlAnalyzer:
    """Generates bundle.yaml content for bundles that lack it."""

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()

    def infer_bundle_yaml(self, bundle_path: str, bundle_name: str) -> dict[str, Any]:
        """
        Infer title/tooltip for a bundle. Returns {title, tooltip, confidence}.
        """
        bundle_full = self.repo_root / bundle_path
        script_path = _find_bundle_entry_script(bundle_full)
        title = _extract_title_from_script(script_path) if script_path else None
        tooltip = _infer_tooltip_from_folder(bundle_name)
        if title:
            return {"title": title, "tooltip": tooltip or title, "confidence": "high"}
        return {
            "title": tooltip or bundle_name,
            "tooltip": tooltip or bundle_name,
            "confidence": "low",
        }

    def generate_yaml_content(self, inferred: dict[str, Any]) -> str:
        """Produce deterministic bundle.yaml content."""
        title = inferred.get("title", "Untitled")
        tooltip = inferred.get("tooltip", title)
        return 'title: "%s"\ntooltip: >-\n  %s\nhelp_url: ""\n#context: [revit]\n' % (
            title.replace('"', '\\"'),
            (tooltip or title).replace('"', '\\"'),
        )

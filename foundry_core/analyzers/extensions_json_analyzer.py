"""Validates and suggests improvements for extensions.json."""

import json
import re
from pathlib import Path
from typing import Any

# Expected keys per pyRevit extension manifest
EXPECTED_KEYS = {"name", "description", "author", "type", "builtin", "default_enabled"}
OPTIONAL_KEYS = {"author_profile", "url", "website", "image", "templates", "dependencies", "rocket_mode_compatible"}


def _validate_schema(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate extensions.json schema and values."""
    findings = []
    if not manifest:
        return [{"type": "error", "message": "extensions.json is empty or missing"}]

    for key in EXPECTED_KEYS:
        if key not in manifest:
            findings.append({"type": "missing_key", "key": key, "message": "Missing required key: %s" % key})

    if manifest.get("type") and manifest["type"] not in ("extension", "library"):
        findings.append({"type": "invalid_value", "key": "type", "message": "type should be 'extension' or 'library'"})

    if "dependencies" in manifest and not isinstance(manifest["dependencies"], list):
        findings.append({"type": "invalid_value", "key": "dependencies", "message": "dependencies must be a list"})

    if "name" in manifest and not manifest["name"].strip():
        findings.append({"type": "invalid_value", "key": "name", "message": "name cannot be empty"})

    return findings


def _suggest_dependencies_from_imports(repo_root: Path, py_files: list[str]) -> list[str]:
    """Suggest extension dependencies based on import patterns."""
    suggested = set()
    external_prefixes = ("pyrevit", "AVSnippets", "AVStandard", "revitron")
    for sp in py_files:
        path = repo_root / sp
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    for prefix in external_prefixes:
                        if prefix in line:
                            suggested.add(prefix)
        except (OSError, UnicodeDecodeError):
            pass
    return sorted(suggested)


class ExtensionsJsonAnalyzer:
    """Validates extensions.json and suggests dependencies."""

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()

    def validate(self, manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Validate extensions.json. Pass manifest or read from repo."""
        if manifest is None:
            path = self.repo_root / "extensions.json"
            if not path.exists():
                return [{"type": "missing", "message": "extensions.json not found"}]
            try:
                manifest = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except json.JSONDecodeError as e:
                return [{"type": "parse_error", "message": str(e)}]
        return _validate_schema(manifest or {})

    def suggest_dependencies(self, py_files: list[str], current_deps: list[str] | None = None) -> dict[str, Any]:
        """Suggest dependencies based on imports. Returns {suggested, current, to_add}."""
        current = set(current_deps or [])
        suggested = set(_suggest_dependencies_from_imports(self.repo_root, py_files))
        to_add = suggested - current
        return {
            "suggested": sorted(suggested),
            "current": sorted(current),
            "to_add": sorted(to_add),
        }

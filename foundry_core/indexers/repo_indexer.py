"""Indexes pyRevit extension repo layout: bundles, scripts, bundle.yaml locations."""

import os
from pathlib import Path
from typing import Any

# pyRevit bundle folder patterns
BUNDLE_PATTERNS = (".tab", ".panel", ".pushbutton", ".pulldown", ".splitbutton", ".stack", ".smartbutton")


def _is_bundle_folder(name: str) -> bool:
    return any(name.endswith(suffix) for suffix in BUNDLE_PATTERNS)


def _find_extension_roots(repo_root: Path) -> list[Path]:
    """Find .extension directories (pyRevit extension roots)."""
    roots: list[Path] = []
    for item in repo_root.rglob("*"):
        if item.is_dir() and item.name.endswith(".extension"):
            roots.append(item)
    return sorted(roots)


def _find_bundle_entry_script(bundle_path: Path) -> Path | None:
    """Find entry script in bundle: script.py, *_script.py, or first *.py."""
    sp = bundle_path / "script.py"
    if sp.exists():
        return sp
    for p in sorted(bundle_path.glob("*_script.py")):
        return p
    for p in sorted(bundle_path.glob("*.py")):
        return p
    return None


def _scan_bundle(bundle_path: Path, repo_root: Path) -> dict[str, Any]:
    """Scan a single bundle folder for entry script and bundle.yaml."""
    result: dict[str, Any] = {
        "path": str(bundle_path.relative_to(repo_root)),
        "name": bundle_path.name,
        "script": None,
        "bundle_yaml": None,
        "bundle_yaml_path": None,
    }
    for item in bundle_path.iterdir():
        if item.is_file() and item.name == "bundle.yaml":
            result["bundle_yaml"] = True
            result["bundle_yaml_path"] = str(item.relative_to(repo_root))
    entry = _find_bundle_entry_script(bundle_path)
    if entry:
        result["script"] = str(entry.relative_to(repo_root))
    return result


class RepoIndexer:
    """Detects .extension roots and parses pyRevit bundle structure."""

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()

    def scan(self) -> dict[str, Any]:
        """
        Scan repo and return inventory JSON.
        Returns: { extensions: [...], inventory: {...}, diagnostics: [...] }
        """
        diagnostics: list[str] = []
        extensions: list[dict[str, Any]] = []
        all_bundles: list[dict[str, Any]] = []
        py_files: list[str] = []

        ext_roots = _find_extension_roots(self.repo_root)
        if not ext_roots:
            diagnostics.append("No .extension marker found; scanning repo_root as single extension")

        roots_to_scan = ext_roots if ext_roots else [self.repo_root]

        def collect_bundles(parent: Path) -> list[dict[str, Any]]:
            found: list[dict[str, Any]] = []
            for item in parent.iterdir():
                if item.is_dir() and _is_bundle_folder(item.name):
                    bundle_data = _scan_bundle(item, self.repo_root)
                    found.append(bundle_data)
                    all_bundles.append(bundle_data)
                    if bundle_data.get("script"):
                        py_files.append(bundle_data["script"])
                    found.extend(collect_bundles(item))
            return found

        for ext_root in roots_to_scan:
            ext_rel = str(ext_root.relative_to(self.repo_root)) if ext_root != self.repo_root else "."
            ext_data: dict[str, Any] = {
                "root": ext_rel,
                "bundles": collect_bundles(ext_root),
            }
            extensions.append(ext_data)

        ext_manifest = self.repo_root / "extensions.json"
        manifest = None
        if ext_manifest.exists():
            try:
                import json
                manifest = json.loads(ext_manifest.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass

        bundles_sorted = all_bundles
        py_files_sorted = sorted(py_files)
        missing_yaml = [b["path"] for b in all_bundles if not b.get("bundle_yaml")]

        return {
            "repo_root": str(self.repo_root),
            "extensions": extensions,
            "bundles": bundles_sorted,
            "py_files": py_files_sorted,
            "extensions_json": manifest,
            "diagnostics": diagnostics,
            "_summary": {
                "bundles_count": len(bundles_sorted),
                "py_files_count": len(py_files_sorted),
                "bundles_without_yaml_count": len(missing_yaml),
                "bundles_without_yaml": missing_yaml,
                "_note": "bundle.yaml is optional (script can use __title__/docstring) but recommended for consistency",
            },
        }

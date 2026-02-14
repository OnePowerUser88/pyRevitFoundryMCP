"""MCP server for pyRevit Foundry - tools and resources."""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from foundry_core.analyzers.bundle_yaml_analyzer import BundleYamlAnalyzer
from foundry_core.analyzers.duplicate_analyzer import DuplicateCodeAnalyzer
from foundry_core.analyzers.extensions_json_analyzer import ExtensionsJsonAnalyzer
from foundry_core.analyzers.extract_to_lib import ExtractToLibEngine
from foundry_core.analyzers.import_audit import ImportAuditAnalyzer
from foundry_core.analyzers.ironpython_audit import IronPythonAuditAnalyzer
from foundry_core.analyzers.lib_structure import LibStructureSuggester
from foundry_core.config import load_config
from foundry_core.engine.extension_creator import (
    add_button as add_button_engine,
    create_extension as create_extension_engine,
    create_extension_config,
    get_extension_config_template,
    load_extension_config,
)
from foundry_core.engine.patch_engine import PatchEngine
from foundry_core.indexers.core_indexer import CoreIndexer
from foundry_core.indexers.repo_indexer import RepoIndexer

mcp = FastMCP("pyRevit Foundry", json_response=True)


def _get_repo_root(repo_root: str | None = None) -> Path:
    if repo_root:
        return Path(repo_root).resolve()
    return Path.cwd()


def _get_core_path(repo_root: Path) -> str | None:
    cfg = load_config(repo_root)
    return cfg.get("pyrevit_core_path")


# --- Resources ---


@mcp.resource("foundry://repo/tree")
def repo_tree() -> str:
    """Inventory JSON of extension layout (bundles, scripts, bundle.yaml)."""
    root = _get_repo_root(None)
    inv = RepoIndexer(root).scan()
    return json.dumps(inv, indent=2)


@mcp.resource("foundry://repo/py_files")
def repo_py_files() -> str:
    """List of Python files in the extension."""
    root = _get_repo_root(None)
    inv = RepoIndexer(root).scan()
    return json.dumps(inv.get("py_files", []), indent=2)


@mcp.resource("foundry://repo/file/{path}")
def repo_file(path: str) -> str:
    """File content by path (relative to repo_root / cwd)."""
    root = _get_repo_root(None)
    full = (root / path).resolve()
    if not str(full).startswith(str(root)):
        return json.dumps({"error": "Path outside repo"})
    if not full.exists():
        return json.dumps({"error": "File not found"})
    return full.read_text(encoding="utf-8", errors="replace")


@mcp.resource("foundry://core/version_info")
def core_version_info() -> str:
    """Core git sha/version if .pyrevit-foundry.toml has pyrevit_core_path."""
    root = _get_repo_root(None)
    path = _get_core_path(root)
    if not path:
        return json.dumps({"git_sha": None, "available": False})
    idx = CoreIndexer(path).index()
    return json.dumps({"git_sha": idx["git_sha"], "available": True})


@mcp.resource("foundry://core/index")
def core_index() -> str:
    """Summary of core module/symbol index."""
    root = _get_repo_root(None)
    path = _get_core_path(root)
    if not path:
        return json.dumps({"modules": {}, "symbols": {}})
    idx = CoreIndexer(path).index()
    return json.dumps({"modules": idx["modules"], "symbols": idx["symbols"]})


@mcp.resource("foundry://repo/health")
def repo_health() -> str:
    """Quick health check summary. Use when you need a one-shot overview."""
    root = _get_repo_root(None)
    inv = RepoIndexer(root).scan()
    summary = inv.get("_summary", {})
    missing = summary.get("bundles_without_yaml_count", summary.get("missing_bundle_yaml_count", 0))
    ext_json = inv.get("extensions_json") or {}
    ext_validator = ExtensionsJsonAnalyzer(root)
    ext_issues = ext_validator.validate(ext_json)
    return json.dumps({
        "bundles": summary.get("bundles_count", 0),
        "py_files": summary.get("py_files_count", 0),
        "bundles_without_yaml": missing,
        "bundle_yaml_note": "Optional (script __title__); recommended",
        "extensions_json_issues": len(ext_issues),
        "diagnostics": inv.get("diagnostics", []),
    }, indent=2)


# --- Tools ---


@mcp.tool()
def run_health_check(
    repo_root: str = "",
    script_paths: list[str] | None = None,
    include_import_audit: bool = True,
    include_duplicates: bool = True,
    include_ironpython: bool = True,
    duplicate_limit: int = 20,
    import_audit_limit: int = 50,
) -> dict:
    """Run full health check: scan, bundle.yaml (optional but recommended), extensions.json, import audit, duplicates, IronPython. Returns summary + counts. script_paths: override discovered scripts (paths relative to repo_root) when discovery misses non-standard names (e.g. *_script.py)."""
    root = _get_repo_root(repo_root or None)
    inv = RepoIndexer(root).scan()
    summary = inv.get("_summary", {})
    result = {
        "repo_root": str(root),
        "scan": {
            "bundles_count": summary.get("bundles_count", 0),
            "py_files_count": summary.get("py_files_count", 0),
            "bundles_without_yaml_count": summary.get("bundles_without_yaml_count", summary.get("missing_bundle_yaml_count", 0)),
            "bundle_yaml_note": "Optional for pushbuttons (use __title__ in script); recommended for consistency",
            "diagnostics": inv.get("diagnostics", []),
        },
        "extensions_json": {"valid": True, "issues": []},
        "import_audit": {"count": 0, "sample": []},
        "duplicates": {"clusters_count": 0, "total_duplicates": 0},
        "ironpython": {"count": 0, "sample": []},
    }

    ext_json = inv.get("extensions_json")
    ext_validator = ExtensionsJsonAnalyzer(root)
    ext_issues = ext_validator.validate(ext_json)
    result["extensions_json"] = {"valid": len(ext_issues) == 0, "issues": ext_issues}

    py_files = script_paths if script_paths else inv.get("py_files", [])

    if include_import_audit and py_files:
        imp_analyzer = ImportAuditAnalyzer(root, _get_core_path(root))
        imp_findings = imp_analyzer.audit(py_files)
        result["import_audit"]["count"] = len(imp_findings)
        result["import_audit"]["sample"] = imp_findings[:import_audit_limit]

    if include_duplicates and py_files:
        dup_analyzer = DuplicateCodeAnalyzer(root)
        clusters, _ = dup_analyzer.analyze(script_paths=py_files, limit=duplicate_limit)
        result["duplicates"]["clusters_count"] = len(clusters)
        result["duplicates"]["total_duplicates"] = sum(len(c.get("locations", [])) for c in clusters)

    if include_ironpython and py_files:
        ipy_analyzer = IronPythonAuditAnalyzer(root)
        ipy_findings = ipy_analyzer.audit(py_files)
        result["ironpython"]["count"] = len(ipy_findings)
        result["ironpython"]["sample"] = ipy_findings[:30]

    return result


@mcp.tool()
def scan_extension_layout(
    repo_root: str = "",
    summary_only: bool = False,
    limit_bundles: int = 0,
    limit_py_files: int = 0,
) -> dict:
    """Scan pyRevit extension repo. summary_only: return counts only. limit_bundles/limit_py_files: cap lists (0=no limit)."""
    root = _get_repo_root(repo_root or None)
    inv = RepoIndexer(root).scan()
    if summary_only:
        return {
            "summary": inv.get("_summary", {}),
            "extensions_json": inv.get("extensions_json"),
            "diagnostics": inv.get("diagnostics", []),
        }
    out = dict(inv)
    if limit_bundles > 0 and out.get("bundles"):
        out["bundles"] = out["bundles"][:limit_bundles]
    if limit_py_files > 0 and out.get("py_files"):
        out["py_files"] = out["py_files"][:limit_py_files]
    if limit_bundles > 0 or limit_py_files > 0:
        out["extensions"] = [
            {"root": e["root"], "bundles_count": len(e.get("bundles", []))}
            for e in out.get("extensions", [])
        ]
    if "_summary" in out:
        del out["_summary"]
    return {"inventory": out, "diagnostics": inv.get("diagnostics", [])}


@mcp.tool()
def list_missing_bundle_yaml(repo_root: str = "", bundle_paths: list[str] | None = None) -> dict:
    """List bundles without bundle.yaml. Optional for pushbuttons (use __title__ in script); recommended for consistency."""
    root = _get_repo_root(repo_root or None)
    inv = RepoIndexer(root).scan()
    bundles = bundle_paths or [b["path"] for b in inv.get("bundles", [])]
    missing = [
        b["path"]
        for b in inv.get("bundles", [])
        if b["path"] in bundles and not b.get("bundle_yaml")
    ]
    return {"missing": missing}


@mcp.tool()
def generate_bundle_yaml(
    repo_root: str = "",
    bundle_paths: list[str] | None = None,
    mode: str = "dry_run",
) -> dict:
    """Generate bundle.yaml for bundles that lack it. Optional (script __title__ works) but recommended. mode: dry_run | write."""
    root = _get_repo_root(repo_root or None)
    inv = RepoIndexer(root).scan()
    analyzer = BundleYamlAnalyzer(root)
    engine = PatchEngine(root)
    patches = []
    findings = []
    for b in inv.get("bundles", []):
        if bundle_paths and b["path"] not in bundle_paths:
            continue
        if b.get("bundle_yaml"):
            continue
        inferred = analyzer.infer_bundle_yaml(b["path"], b["name"])
        content = analyzer.generate_yaml_content(inferred)
        yaml_path = str(Path(b["path"]) / "bundle.yaml")
        patch = engine.create_add_file_patch(yaml_path, content, risk="low")
        patches.append(patch)
        findings.append({"bundle": b["path"], "inferred": inferred})
    if mode == "write":
        engine.apply_patches(patches, mode="write")
    return {"patches": patches, "findings": findings}


@mcp.tool()
def import_audit_with_core(
    repo_root: str = "",
    script_paths: list[str] | None = None,
    core_root: str | None = None,
    allowlist: list[str] | None = None,
    mode: str = "dry_run",
) -> dict:
    """Audit imports: unused, raw RevitAPI, wrapper suggestions."""
    root = _get_repo_root(repo_root or None)
    core = core_root or _get_core_path(root)
    if not script_paths:
        inv = RepoIndexer(root).scan()
        script_paths = inv.get("py_files", [])
    analyzer = ImportAuditAnalyzer(root, core)
    findings = analyzer.audit(script_paths)
    if allowlist:
        findings = [f for f in findings if f.get("name") not in allowlist]
    return {
        "findings": findings,
        "patches": [],
        "core_version": CoreIndexer(core).index()["git_sha"] if core else None,
    }


@mcp.tool()
def analyze_duplicates(
    repo_root: str = "",
    script_paths: list[str] | None = None,
    limit: int = 0,
    summary_only: bool = False,
    same_name_only: bool = False,
) -> dict:
    """Find duplicate/near-duplicate functions. limit: max clusters (0=all). same_name_only: only clusters where all have same function name (safe for extract)."""
    root = _get_repo_root(repo_root or None)
    analyzer = DuplicateCodeAnalyzer(root)
    clusters, findings = analyzer.analyze(script_paths, limit=limit or None, same_name_only=same_name_only)
    if summary_only:
        return {
            "clusters_count": len(clusters),
            "total_duplicates": sum(len(c.get("locations", [])) for c in clusters),
        }
    return {"clusters": clusters, "findings": findings}


@mcp.tool()
def propose_lib_structure(
    repo_root: str = "",
    clusters: list[dict] | None = None,
    preferences: dict | None = None,
    same_name_only: bool = False,
) -> dict:
    """Propose lib/ module tree from duplicate clusters. same_name_only: only same-name clusters (extract-safe)."""
    root = _get_repo_root(repo_root or None)
    suggester = LibStructureSuggester(root)
    result = suggester.propose(clusters, preferences, same_name_only=same_name_only)
    return result


@mcp.tool()
def apply_patch(
    repo_root: str = "",
    patches: list[dict] | None = None,
    mode: str = "dry_run",
) -> dict:
    """Apply patches. mode: dry_run | write."""
    root = _get_repo_root(repo_root or None)
    engine = PatchEngine(root)
    patches = patches or []
    applied, errors = engine.apply_patches(patches, mode=mode)
    return {"applied": applied, "errors": errors}


@mcp.tool()
def validate_extensions_json(repo_root: str = "", manifest: dict | None = None) -> dict:
    """Validate extensions.json schema. Pass manifest to validate in-memory, or omit to read from repo."""
    root = _get_repo_root(repo_root or None)
    analyzer = ExtensionsJsonAnalyzer(root)
    issues = analyzer.validate(manifest)
    return {"valid": len(issues) == 0, "issues": issues}


@mcp.tool()
def suggest_extensions_json_dependencies(repo_root: str = "") -> dict:
    """Suggest dependencies for extensions.json based on imports in scripts."""
    root = _get_repo_root(repo_root or None)
    inv = RepoIndexer(root).scan()
    py_files = inv.get("py_files", [])
    ext_json = inv.get("extensions_json") or {}
    current = ext_json.get("dependencies", [])
    analyzer = ExtensionsJsonAnalyzer(root)
    result = analyzer.suggest_dependencies(py_files, current)
    return result


@mcp.tool()
def ironpython_audit(
    repo_root: str = "",
    script_paths: list[str] | None = None,
    limit: int = 0,
    summary_only: bool = False,
) -> dict:
    """Audit scripts for IronPython 2.7 incompatible constructs (f-strings, type hints, walrus, etc)."""
    root = _get_repo_root(repo_root or None)
    if not script_paths:
        inv = RepoIndexer(root).scan()
        script_paths = inv.get("py_files", [])
    analyzer = IronPythonAuditAnalyzer(root)
    findings = analyzer.audit(script_paths)
    total = len(findings)
    if summary_only:
        return {"count": total, "by_type": _count_by_type(findings)}
    if limit > 0:
        findings = findings[:limit]
    return {"findings": findings, "count": total, "sample_size": len(findings)}


def _count_by_type(findings: list) -> dict:
    counts = {}
    for f in findings:
        t = f.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts


@mcp.tool()
def create_extension_config_tool(
    config_path: str = "",
    mode: str = "write",
) -> dict:
    """Create a config file template for extension creation. IMPORTANT: After running this, STOP and ask the user to edit the config file (extension_name, output_path, tabs). Do NOT call create_extension until the user confirms they have updated the config. config_path: where to write the template (e.g. ./extension_config.yaml)."""
    path = config_path or "extension_config.yaml"
    result = create_extension_config(path, mode=mode)
    result["action_required"] = "ask_user_to_edit_config"
    result["message"] = "STOP: Ask the user to edit the config file to set output_path, extension_name, and tabs. Do NOT call create_extension until the user confirms they have updated the config."
    if mode == "dry_run":
        result["template_preview"] = get_extension_config_template()[:500] + "..."
    return result


@mcp.tool()
def get_extension_config_template_tool() -> dict:
    """Return the extension config template content. Use when user wants to see/copy the template without creating a file."""
    return {"template": get_extension_config_template()}


@mcp.tool()
def create_extension(
    output_path: str = "",
    extension_name: str = "",
    tabs: list[dict] | str | None = None,
    config_path: str = "",
    author: str = "",
    description: str = "",
    include_help: bool = True,
    mode: str = "dry_run",
) -> dict:
    """Create a pyRevit extension. Prefer config_path flow: 1) create_extension_config_tool 2) STOP and ask user to edit config 3) create_extension(config_path=...) only after user confirms. If config has placeholder output_path (path/to/output), returns action_required - do not proceed. config_path: path to YAML/JSON config."""
    if config_path:
        out = Path(".")
        ext_name = ""
        tabs_parsed: list[dict] | None = None
    else:
        out = Path(output_path or ".").resolve()
        ext_name = extension_name or ""
        if isinstance(tabs, str):
            try:
                tabs_parsed = json.loads(tabs)
            except json.JSONDecodeError as e:
                return {"errors": [f"tabs must be valid JSON: {e}"], "mode": mode}
        else:
            tabs_parsed = tabs or []

    return create_extension_engine(
        output_path=out,
        extension_name=ext_name,
        tabs=tabs_parsed or [],
        author=author,
        description=description,
        include_help=include_help,
        mode=mode,
        config_path=config_path or None,
    )


@mcp.tool()
def add_button(
    repo_root: str = "",
    target: str = "",
    button_name: str = "",
    author: str = "",
    doc: str = "",
    include_help: bool = True,
    update_layout: bool = True,
    mode: str = "dry_run",
) -> dict:
    """Add a single pushbutton to an existing extension. repo_root: path to .extension folder. target: TabName.tab/PanelName.panel or Tab.tab/Panel.panel/Pulldown.pulldown. mode: dry_run | write."""
    root = _get_repo_root(repo_root or None)
    if not target or not button_name:
        return {"errors": ["target and button_name are required"], "mode": mode}
    return add_button_engine(
        repo_root=root,
        target=target,
        button_name=button_name,
        author=author,
        doc=doc,
        include_help=include_help,
        update_layout=update_layout,
        mode=mode,
    )


@mcp.tool()
def extract_to_lib(
    repo_root: str = "",
    clusters: list[dict] | None = None,
    cluster_indices: list[int] | None = None,
    mode: str = "dry_run",
    same_name_only: bool = True,
) -> dict:
    """Extract duplicate functions to lib/ modules and patch scripts. mode: dry_run | write. same_name_only: when clusters=None, use only same-name clusters (default True)."""
    root = _get_repo_root(repo_root or None)
    engine = ExtractToLibEngine(root)
    result = engine.extract(clusters, cluster_indices, mode, same_name_only=same_name_only)
    return result


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

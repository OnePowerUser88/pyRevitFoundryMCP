# pyRevit Foundry MCP

MCP server for developing and maintaining pyRevit extensions. Static analysis only—no Revit runtime required.

## What it does

- **Scan extension layout** – Inventory bundles, scripts, bundle.yaml
- **Generate bundle.yaml** – Infer title/tooltip from `__title__`/docstring for missing bundles
- **Import audit** – Unused imports, raw RevitAPI usage, pyRevit wrapper suggestions (with core clone)
- **Duplicate detection** – Function-level duplicate code across scripts
- **Lib structure** – Propose `lib/` module tree from duplicates (report-only)
- **Patch engine** – Unified diffs, dry-run by default

## Quickstart

### Install

```bash
pip install -e .
# or: uv pip install -e .
```

### Run MCP server (stdio)

```bash
pyrevit-foundry
# or: python -m foundry_mcp.server
```

### Cursor MCP config

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "pyrevit-foundry": {
      "command": "pyrevit-foundry",
      "args": [],
      "cwd": "D:/path/to/your/pyrevit-extension-repo"
    }
  }
}
```

Or use `uv`:

```json
{
  "mcpServers": {
    "pyrevit-foundry": {
      "command": "uv",
      "args": ["run", "pyrevit-foundry"],
      "cwd": "D:/path/to/your/pyrevit-extension-repo"
    }
  }
}
```

## pyRevit core clone (optional)

For wrapper/import suggestions, point to a local pyRevit core clone:

**Option 1:** `.pyrevit-foundry.toml` in repo root:

```toml
pyrevit_core_path = "D:/path/to/pyrevit-clone"
```

**Option 2:** Pass `core_root` to `import_audit_with_core` tool.

## Tools

| Tool | Description |
|------|--------------|
| `run_health_check` | **One-shot overview** – scan, bundle.yaml, extensions.json, import audit, duplicates, IronPython |
| `scan_extension_layout` | Full inventory (summary_only, limit_bundles, limit_py_files) |
| `list_missing_bundle_yaml` | Bundles without bundle.yaml (optional for pushbuttons; recommended) |
| `generate_bundle_yaml` | Create bundle.yaml for bundles that lack it (dry_run \| write) |
| `validate_extensions_json` | Validate extensions.json schema |
| `suggest_extensions_json_dependencies` | Suggest deps from imports |
| `import_audit_with_core` | Unused imports, raw API, wrapper suggestions |
| `analyze_duplicates` | Duplicate clusters (limit, summary_only) |
| `ironpython_audit` | f-strings, type hints, walrus, match (IronPython 2.7 incompat) |
| `propose_lib_structure` | Lib module proposals |
| `extract_to_lib` | Extract duplicates to lib/ and patch scripts (dry_run \| write) |
| `apply_patch` | Apply patches (dry_run \| write) |
| `create_extension_config_tool` | Create config template for extension (run first, user fills, then create_extension) |
| `get_extension_config_template_tool` | Return config template content (no file) |
| `create_extension` | Create extension from config_path or inline params |
| `add_button` | Add a single pushbutton to an existing extension |

## Resources vs tools

**Use resources** when the client supports MCP resources and you need:
- `foundry://repo/tree` – Full inventory JSON (for context loading)
- `foundry://repo/py_files` – List of scripts
- `foundry://repo/file/{path}` – Read a file by relative path
- `foundry://repo/health` – **Quick health summary** (bundles, missing yaml, ext_json issues)
- `foundry://core/version_info` – pyRevit core git sha
- `foundry://core/index` – Core module/symbol index

**Use tools** when you need to:
- Run analyses (health check, import audit, duplicates, IronPython)
- Generate or apply changes (bundle.yaml, extract_to_lib, patches)
- Validate or suggest (extensions.json)

**Tip:** Start with `run_health_check` or `foundry://repo/health` for a quick overview, then drill down with specific tools.

## Safety

- **Default: dry-run** – No file writes unless `mode="write"`
- Patches are minimal and reversible
- No f-strings in generated patches (IronPython 2.7 compat)
- No network calls

## Tests

```bash
pytest tests/
```

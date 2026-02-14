# Contributing to pyRevit Foundry MCP

Thanks for considering contributing. This project uses the same license as [pyRevit](https://github.com/pyrevitlabs/pyRevit) (GPL-3.0).

## Setup

```bash
git clone https://github.com/onepoweruser88/pyRevitFoundryMCP.git
cd pyRevitFoundryMCP
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v
```

Please ensure tests pass before submitting a PR.

## Pull requests

1. Open an issue or comment on an existing one to discuss the change.
2. Fork the repo, create a branch from `main`.
3. Make your changes; keep scope focused.
4. Run `pytest tests/`.
5. Open a PR with a short description. Link any related issue.

## Scope

- **foundry_core** – Static analysis, indexers, extension creator (no MCP dependency).
- **foundry_mcp** – MCP server and tool wrappers.

Changes that add new tools or alter extension layout behavior should include or update tests where practical.

## Code style

- Python 3.10+.
- No formal style guide; match existing code in the file you edit.
- Generated patches avoid f-strings and modern syntax so generated code stays IronPython 2.7–friendly where it matters.

## pyRevit extension conventions

For extension layout, bundle naming, and `bundle.yaml` format, see [pyRevit documentation](https://docs.pyrevitlabs.io/) and the [pyRevit repo](https://github.com/pyrevitlabs/pyRevit).

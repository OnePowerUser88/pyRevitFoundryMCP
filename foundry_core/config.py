"""Load .pyrevit-foundry.toml config."""

from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


def load_config(repo_root: str | Path) -> dict:
    """Load .pyrevit-foundry.toml from repo root."""
    path = Path(repo_root) / ".pyrevit-foundry.toml"
    if not path.exists():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        if "pyrevit_core_path" in data:
            return data
        return data.get("foundry", {})
    except Exception:
        return {}

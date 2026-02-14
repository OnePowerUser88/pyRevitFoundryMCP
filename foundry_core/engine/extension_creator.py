"""Create pyRevit extension folder structure and apply templates."""

import json
from pathlib import Path
from typing import Any

import yaml

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
DEFAULT_CONFIG_NAME = "extension_config.yaml"


def get_extension_config_template() -> str:
    """Return the default config template content."""
    return (TEMPLATES_DIR / DEFAULT_CONFIG_NAME).read_text(encoding="utf-8", errors="replace")


def create_extension_config(config_path: str | Path, mode: str = "write") -> dict[str, Any]:
    """
    Create a config file template for extension creation.
    User fills it, then runs create_extension(config_path=...).
    mode: dry_run | write
    """
    path = Path(config_path).resolve()
    content = get_extension_config_template()
    if mode == "write":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return {
        "config_path": str(path),
        "mode": mode,
        "instructions": "Edit the config file to customize extension_name, output_path, tabs. Then run create_extension with config_path pointing to this file.",
    }


def load_extension_config(config_path: str | Path) -> dict[str, Any]:
    """Load extension config from YAML or JSON file."""
    path = Path(config_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in (".yaml", ".yml"):
        return yaml.safe_load(text) or {}
    if path.suffix.lower() == ".json":
        return json.loads(text)
    raise ValueError(f"Unsupported config format: {path.suffix}. Use .yaml or .json")


def _load_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    return path.read_text(encoding="utf-8", errors="replace")


def _render(template: str, **kwargs: str) -> str:
    for k, v in kwargs.items():
        template = template.replace("{{" + k + "}}", str(v))
    return template


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _create_pushbutton(
    root: Path,
    rel_path: str,
    name: str,
    author: str = "",
    doc: str = "",
    include_help: bool = True,
) -> list[str]:
    """Create a pushbutton bundle. Returns list of created paths (relative)."""
    created: list[str] = []
    folder = root / rel_path
    _ensure_dir(folder)

    script_content = _render(
        _load_template("script.py"),
        title=name,
        author=author or "pyRevit",
        doc=doc or name,
    )
    (folder / "script.py").write_text(script_content, encoding="utf-8")
    created.append(f"{rel_path}/script.py")

    yaml_content = _render(
        _load_template("bundle_pushbutton.yaml"),
        title=name,
        tooltip=doc or name,
    )
    (folder / "bundle.yaml").write_text(yaml_content, encoding="utf-8")
    created.append(f"{rel_path}/bundle.yaml")

    if include_help:
        help_content = _render(
            _load_template("help.html"),
            title=name,
            doc=doc or name,
        )
        (folder / "help.html").write_text(help_content, encoding="utf-8")
        created.append(f"{rel_path}/help.html")

    return created


def _create_pulldown(
    root: Path,
    rel_path: str,
    name: str,
    buttons: list[dict[str, Any]],
    author: str = "",
    include_help: bool = True,
) -> list[str]:
    """Create a pulldown bundle with nested pushbuttons. Returns created paths."""
    created: list[str] = []
    folder = root / rel_path
    _ensure_dir(folder)

    layout_lines = []
    for btn in buttons:
        btn_name = btn.get("name", "Button")
        layout_lines.append(f'  - {btn_name}')

    yaml_content = _render(
        _load_template("bundle_pulldown.yaml"),
        layout="\n".join(layout_lines),
    )
    (folder / "bundle.yaml").write_text(yaml_content, encoding="utf-8")
    created.append(f"{rel_path}/bundle.yaml")

    for btn in buttons:
        btn_name = btn.get("name", "Button")
        btn_rel = f"{rel_path}/{btn_name}.pushbutton"
        created.extend(
            _create_pushbutton(
                root, btn_rel, btn_name,
                author=author,
                doc=btn.get("doc", btn_name),
                include_help=include_help,
            )
        )

    return created


def _create_stack(
    root: Path,
    rel_path: str,
    name: str,
    items: list[dict[str, Any]],
    author: str = "",
    include_help: bool = True,
) -> list[str]:
    """Create a stack bundle with nested pushbuttons. Returns created paths."""
    created: list[str] = []
    folder = root / rel_path
    _ensure_dir(folder)

    # Normalize items to [{name, type?, doc?}, ...]
    normalized = []
    for it in items:
        if isinstance(it, str):
            normalized.append({"name": it, "type": "pushbutton"})
        else:
            normalized.append({"name": it.get("name", "Item"), "type": it.get("type", "pushbutton"), "doc": it.get("doc", "")})

    layout_lines = [f"  - {it['name']}" for it in normalized]
    yaml_content = _render(
        _load_template("bundle_stack.yaml"),
        layout="\n".join(layout_lines),
    )
    (folder / "bundle.yaml").write_text(yaml_content, encoding="utf-8")
    created.append(f"{rel_path}/bundle.yaml")

    for it in normalized:
        if it.get("type") != "pushbutton":
            continue
        btn_name = it["name"]
        btn_rel = f"{rel_path}/{btn_name}.pushbutton"
        created.extend(
            _create_pushbutton(
                root, btn_rel, btn_name,
                author=author,
                doc=it.get("doc") or btn_name,
                include_help=include_help,
            )
        )

    return created


def create_extension(
    output_path: str | Path = "",
    extension_name: str = "",
    tabs: list[dict[str, Any]] | None = None,
    author: str = "",
    description: str = "",
    include_help: bool = True,
    mode: str = "dry_run",
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Create a full pyRevit extension.

    When config_path is set, load extension_name, output_path, tabs, author, description from file
    (overridden by explicit params). Use create_extension_config first to generate the config template.

    tabs: list of {name, panels: [{name, items: [{name, type: "pushbutton"|"pulldown", buttons?: [...]}]}]}
    mode: dry_run | write
    """
    if config_path:
        try:
            cfg = load_extension_config(config_path)
            extension_name = cfg.get("extension_name") or extension_name or ""
            output_path = cfg.get("output_path") or output_path or "."
            tabs = cfg.get("tabs") or tabs or []
            author = cfg.get("author") or author or ""
            description = cfg.get("description") or description or ""

            # Require user to customize config before proceeding
            out_str = str(output_path).strip()
            if not out_str or "path/to/output" in out_str.lower():
                return {
                    "errors": [],
                    "mode": mode,
                    "action_required": "config_not_customized",
                    "message": "The config file has not been customized. Ask the user to edit the config file to set output_path (and optionally extension_name, tabs). Do NOT call create_extension again until the user confirms they have updated the config.",
                    "config_path": str(config_path),
                }
        except Exception as e:
            return {"errors": [str(e)], "mode": mode}
    root = Path(output_path).resolve()
    ext_folder = root / f"{extension_name}.extension"
    created: list[str] = []
    errors: list[str] = []
    do_write = mode == "write"

    def process_item(parent_rel: str, item: dict, author_val: str) -> None:
        name = item.get("name", "Item")
        itype = item.get("type", "pushbutton")
        if itype == "pushbutton":
            rel = f"{parent_rel}/{name}.pushbutton"
            if do_write:
                created.extend(
                    _create_pushbutton(
                        ext_folder, rel, name,
                        author=author_val,
                        include_help=include_help,
                    )
                )
            else:
                created.extend([f"{rel}/script.py", f"{rel}/bundle.yaml"])
                if include_help:
                    created.append(f"{rel}/help.html")
        elif itype == "pulldown":
            rel = f"{parent_rel}/{name}.pulldown"
            buttons = item.get("buttons", [])
            if buttons and isinstance(buttons[0], str):
                buttons = [{"name": b} for b in buttons]
            if do_write:
                created.extend(
                    _create_pulldown(
                        ext_folder, rel, name,
                        buttons=buttons,
                        author=author_val,
                        include_help=include_help,
                    )
                )
            else:
                created.append(f"{rel}/bundle.yaml")
                for btn in buttons:
                    bn = btn.get("name", "Button") if isinstance(btn, dict) else btn
                    created.extend([f"{rel}/{bn}.pushbutton/script.py", f"{rel}/{bn}.pushbutton/bundle.yaml"])
                    if include_help:
                        created.append(f"{rel}/{bn}.pushbutton/help.html")
        elif itype == "stack":
            rel = f"{parent_rel}/{name}.stack"
            stack_items = item.get("items", [])
            if stack_items and isinstance(stack_items[0], str):
                stack_items = [{"name": b, "type": "pushbutton"} for b in stack_items]
            if do_write:
                created.extend(
                    _create_stack(
                        ext_folder, rel, name,
                        items=stack_items,
                        author=author_val,
                        include_help=include_help,
                    )
                )
            else:
                created.append(f"{rel}/bundle.yaml")
                for it in stack_items:
                    bn = it.get("name", "Button") if isinstance(it, dict) else it
                    created.extend([f"{rel}/{bn}.pushbutton/script.py", f"{rel}/{bn}.pushbutton/bundle.yaml"])
                    if include_help:
                        created.append(f"{rel}/{bn}.pushbutton/help.html")

    try:
        if do_write:
            _ensure_dir(ext_folder)

        for tab in tabs:
            tab_name = tab.get("name", "Tab")
            tab_rel = f"{tab_name}.tab"
            for panel in tab.get("panels", []):
                panel_name = panel.get("name", "Panel")
                panel_rel = f"{tab_rel}/{panel_name}.panel"
                items = panel.get("items", [])

                if do_write:
                    (ext_folder / panel_rel).mkdir(parents=True, exist_ok=True)

                layout_lines = []
                for item in items:
                    name = item.get("name", "Item")
                    itype = item.get("type", "pushbutton")
                    if itype in ("pushbutton", "pulldown", "stack"):
                        layout_lines.append(f"  - {name}")

                if layout_lines:
                    created.append(f"{panel_rel}/bundle.yaml")
                    if do_write:
                        panel_yaml = _render(
                            _load_template("bundle_panel.yaml"),
                            layout="\n".join(layout_lines),
                        )
                        (ext_folder / panel_rel / "bundle.yaml").write_text(
                            panel_yaml, encoding="utf-8"
                        )

                for item in items:
                    process_item(panel_rel, item, author)

        created.append("extensions.json")
        if do_write:
            ext_json = _render(
                _load_template("extensions.json"),
                name=extension_name,
                description=description or extension_name,
                author=author or "pyRevit",
            )
            (ext_folder / "extensions.json").write_text(ext_json, encoding="utf-8")

    except Exception as e:
        errors.append(str(e))

    return {
        "extension_path": str(ext_folder),
        "created": created,
        "errors": errors,
        "mode": mode,
    }


def _append_to_layout(yaml_path: Path, item: str) -> bool:
    """Append item to layout list in bundle.yaml. Returns True if updated."""
    if not yaml_path.exists():
        return False
    text = yaml_path.read_text(encoding="utf-8", errors="replace")
    if "layout:" not in text:
        return False
    indent = "  - "
    new_line = f"{indent}{item}\n"
    if new_line.strip() in text:
        return False
    lines = text.splitlines()
    in_layout = False
    for i, line in enumerate(lines):
        if line.strip().startswith("layout:"):
            in_layout = True
            continue
        if in_layout:
            if line.strip() and not line.strip().startswith("-"):
                break
            if line.strip().startswith("-"):
                continue
            if not line.strip():
                lines.insert(i, new_line.rstrip())
                yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return True
    if in_layout:
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip().startswith("-"):
                lines.insert(i + 1, new_line.rstrip())
                yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return True
    return False


def add_button(
    repo_root: str | Path,
    target: str,
    button_name: str,
    author: str = "",
    doc: str = "",
    include_help: bool = True,
    update_layout: bool = True,
    mode: str = "dry_run",
) -> dict[str, Any]:
    """
    Add a single pushbutton to an existing extension.

    target: path like "TabName.tab/PanelName.panel" or "Tab.tab/Panel.panel/Pulldown.pulldown"
    update_layout: add button to parent bundle.yaml layout (default True)
    mode: dry_run | write
    """
    root = Path(repo_root).resolve()
    rel_path = f"{target}/{button_name}.pushbutton"
    created: list[str] = []
    errors: list[str] = []
    layout_updated = False
    do_write = mode == "write"

    try:
        if do_write:
            _ensure_dir(root / rel_path)
            created.extend(
                _create_pushbutton(
                    root, rel_path, button_name,
                    author=author,
                    doc=doc or button_name,
                    include_help=include_help,
                )
            )
            if update_layout:
                parent_yaml = root / target / "bundle.yaml"
                layout_updated = _append_to_layout(parent_yaml, button_name)
        else:
            created.extend([f"{rel_path}/script.py", f"{rel_path}/bundle.yaml"])
            if include_help:
                created.append(f"{rel_path}/help.html")
    except Exception as e:
        errors.append(str(e))

    return {
        "button_path": str(root / rel_path),
        "created": created,
        "errors": errors,
        "mode": mode,
        "layout_updated": layout_updated,
    }

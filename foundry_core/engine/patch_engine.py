"""Creates and applies unified diffs. Dry-run by default."""

from pathlib import Path
from typing import Any

# Patch format: { path, diff, risk, summary }


def _make_unified_diff(path: Path, old_lines: list[str], new_lines: list[str]) -> str:
    """Produce a minimal unified diff."""
    lines: list[str] = []
    rel = str(path).replace("\\", "/")
    lines.append("--- a/%s" % rel)
    lines.append("+++ b/%s" % rel)
    lines.append("@@ -1,%d +1,%d @@" % (len(old_lines), len(new_lines)))
    for line in new_lines:
        lines.append((" " if line in old_lines else "+") + line)
    return "\n".join(lines) + "\n"


class PatchEngine:
    """Creates unified diffs and applies them with dry-run/write modes."""

    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root).resolve()

    def create_add_file_patch(self, rel_path: str, content: str, risk: str = "low") -> dict[str, Any]:
        """Patch for adding a new file."""
        path = self.repo_root / rel_path
        if not str(path.resolve()).startswith(str(self.repo_root)):
            raise ValueError("Path outside repo_root")
        diff = _make_unified_diff(path, [], content.splitlines() if content else [])
        return {
            "path": rel_path,
            "diff": diff,
            "content": content,
            "risk": risk,
            "summary": "Add %s" % rel_path,
        }

    def create_edit_patch(
        self, rel_path: str, old_content: str, new_content: str, risk: str = "medium"
    ) -> dict[str, Any]:
        """Patch for editing an existing file."""
        path = self.repo_root / rel_path
        if not str(path.resolve()).startswith(str(self.repo_root)):
            raise ValueError("Path outside repo_root")
        old_lines = old_content.splitlines() if old_content else []
        new_lines = new_content.splitlines() if new_content else []
        diff = _make_unified_diff(path, old_lines, new_lines)
        return {
            "path": rel_path,
            "diff": diff,
            "content": new_content,
            "risk": risk,
            "summary": "Edit %s" % rel_path,
        }

    def apply_patches(
        self, patches: list[dict[str, Any]], mode: str = "dry_run"
    ) -> tuple[list[str], list[str]]:
        """
        Apply patches. mode: dry_run | write.
        Returns (applied_paths, errors).
        """
        applied: list[str] = []
        errors: list[str] = []
        for p in patches:
            path = self.repo_root / p["path"]
            if not str(path.resolve()).startswith(str(self.repo_root)):
                errors.append("Skipped %s: outside repo" % p["path"])
                continue
            if mode == "write":
                path.parent.mkdir(parents=True, exist_ok=True)
                content = p.get("content")
                if content is not None:
                    path.write_text(content, encoding="utf-8")
                else:
                    diff = p.get("diff", "")
                    new_lines = [
                        ln[1:]
                        for ln in diff.splitlines()
                        if ln.startswith("+") and not ln.startswith("+++")
                    ]
                    path.write_text(
                        "\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8"
                    )
                applied.append(p["path"])
            else:
                applied.append(p["path"] + " (dry-run)")
        return applied, errors

"""Read and write Claude Code settings.json / settings.local.json."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


USER_SETTINGS = Path.home() / ".claude" / "settings.json"
PROJECT_SETTINGS = Path(".claude/settings.local.json")


def read_user_settings() -> dict:
    """Read ~/.claude/settings.json, return empty dict if absent."""
    if USER_SETTINGS.exists():
        try:
            return json.loads(USER_SETTINGS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def write_user_settings(data: dict) -> None:
    """Write ~/.claude/settings.json with backup before first write."""
    USER_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    if USER_SETTINGS.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = USER_SETTINGS.with_suffix(f".json.bak.{timestamp}")
        shutil.copy2(USER_SETTINGS, backup)
    USER_SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    USER_SETTINGS.chmod(0o600)


def merge_into_user_settings(env_vars: dict[str, str], source: str | None = None) -> Path:
    """Merge provider env vars into ~/.claude/settings.json, preserving other keys.

    Returns the path written.
    """
    data = read_user_settings()
    data.setdefault("env", {}).update(env_vars)
    if source:
        data["_claude_switch_provider"] = source
    write_user_settings(data)
    return USER_SETTINGS


def write_project_settings(env_vars: dict[str, str], source: str | None = None) -> Path:
    """Write provider env vars to .claude/settings.local.json.

    Returns the path written.
    """
    target = Path.cwd() / PROJECT_SETTINGS
    target.parent.mkdir(parents=True, exist_ok=True)
    data = {"env": env_vars}
    if source:
        data["_claude_switch_provider"] = source
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    target.chmod(0o600)
    return target


def remove_project_settings() -> None:
    """Remove .claude/settings.local.json if it exists."""
    path = Path.cwd() / PROJECT_SETTINGS
    if path.exists():
        path.unlink()

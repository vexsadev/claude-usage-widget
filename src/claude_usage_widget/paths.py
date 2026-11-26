"""Filesystem locations, per OS. Standard library only (used by the status line and installer)."""
import json
import os
import sys
from pathlib import Path

APP_NAME = "claude-usage-widget"
IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def claude_dir() -> Path:
    """Claude Code's config dir (honours CLAUDE_CONFIG_DIR, default ~/.claude on every OS)."""
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env).expanduser() if env else Path.home() / ".claude"


def claude_projects_dirs():
    """Where Claude Code writes session transcripts (*.jsonl)."""
    return [claude_dir() / "projects"]


def claude_settings_file() -> Path:
    return claude_dir() / "settings.json"


def data_dir() -> Path:
    """Per-user app data: venv, config, captured limits, notification state.

    Linux:   $XDG_DATA_HOME/claude-usage-widget   (~/.local/share/claude-usage-widget)
    macOS:   ~/Library/Application Support/claude-usage-widget
    Windows: %LOCALAPPDATA%\\claude-usage-widget
    Override with CLAUDE_USAGE_WIDGET_HOME.
    """
    env = os.environ.get("CLAUDE_USAGE_WIDGET_HOME")
    if env:
        return Path(env).expanduser()
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


def rate_limits_file() -> Path:
    return data_dir() / "rate_limits.json"


def config_file() -> Path:
    return data_dir() / "config.json"


def notified_file() -> Path:
    return data_dir() / "notified.json"


def load_json(path: Path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def save_json(path: Path, data) -> None:
    """Atomic write (temp file + replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

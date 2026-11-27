"""Filesystem locations, per OS. Standard library only (used by the status line and installer)."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

APP_NAME = "claude-usage-widget"
IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
VENV_MARKER = "claude-usage-widget-home"  # the installer puts this in <data dir>/venv


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
    Override with CLAUDE_USAGE_WIDGET_HOME. Code running from the installed venv uses the folder that
    venv lives in, so a custom home chosen at install time also holds for the status line hook,
    autostart and manual launches, which don't inherit the variable.
    """
    env = os.environ.get("CLAUDE_USAGE_WIDGET_HOME")
    if env:
        return Path(env).expanduser()
    venv = Path(sys.prefix)
    if (venv / VENV_MARKER).is_file():
        return venv.parent
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
        with open(path, encoding="utf-8-sig") as f:  # -sig: tolerate a BOM (Windows Notepad adds one)
            return json.load(f)
    except Exception:
        return {} if default is None else default


def load_json_strict(path: Path) -> dict:
    """Load a JSON object we are about to rewrite: {} if the file is missing, ValueError if unreadable.

    Use this for files we don't own (Claude Code's settings.json), so a parse error never ends up
    overwriting the user's settings with a near-empty file.
    """
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise ValueError(f"Could not read {path}: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"Could not read {path}: it is not a JSON object")
    return data


def save_json(path: Path, data) -> None:
    """Atomic write (temp file + replace).

    Writes through symlinks (dotfile managers link settings.json) and keeps the file's permissions.
    The temp name is per process, so two Claude Code sessions saving at once can't mix their output.
    """
    path = Path(os.path.realpath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        if path.exists():
            shutil.copymode(path, tmp)
        for attempt in range(10):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:  # Windows: a reader (the widget) has the file open for a moment
                if not IS_WINDOWS or attempt == 9:
                    raise
                time.sleep(0.02)
    finally:
        if tmp.exists():
            tmp.unlink()

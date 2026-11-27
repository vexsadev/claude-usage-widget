"""Claude Code status line command.

Claude Code pipes a JSON blob to this command after each turn. For Claude subscribers it contains
`rate_limits` (5-hour and weekly usage). We save that for the widget, then print a status line:
either the output of the user's previous status line command (if the installer chained one) or a
short default line.

All I/O is UTF-8 bytes: Claude Code sends and expects UTF-8, while Python's pipe encoding on Windows
is the ANSI code page.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import paths


def _pct(v):
    if isinstance(v, dict) and isinstance(v.get("used_percentage"), (int, float)):
        return v["used_percentage"]
    return None


def find_bash():
    """bash to run the chained command with, like Claude Code does; None if there is none."""
    if not paths.IS_WINDOWS:
        return shutil.which("bash")
    env = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")  # the same override Claude Code honours
    if env and os.path.isfile(env):
        return env
    git = shutil.which("git")
    if git:  # Git for Windows: ...\Git\cmd\git.exe or ...\Git\mingw64\bin\git.exe
        g = Path(git).resolve()
        for root in (g.parent.parent, g.parent.parent.parent):
            for c in (root / "bin" / "bash.exe", root / "usr" / "bin" / "bash.exe"):
                if c.is_file():
                    return str(c)
    b = shutil.which("bash")
    if b and "system32" not in b.lower():  # System32\bash.exe is WSL, a different machine
        return b
    return None


def run_chained(cmd, raw):
    """Run the user's previous status line command with Claude Code's input; return its output text."""
    bash = find_bash()
    argv, shell = ([bash, "-c", cmd], False) if bash else (cmd, True)
    r = subprocess.run(argv, shell=shell, input=raw, capture_output=True, timeout=10)
    return r.stdout.decode("utf-8", "replace")


def default_line(d, rl):
    model = d.get("model") if isinstance(d.get("model"), dict) else {}
    parts = [model.get("display_name") or "Claude"]
    for key, label in (("five_hour", "5h"), ("seven_day", "wk")):
        p = _pct((rl or {}).get(key))
        if p is not None:
            parts.append(f"{label} {p:.0f}%")
    return " · ".join(parts) + "\n"


def main():
    raw = sys.stdin.buffer.read()
    try:
        d = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}

    rl = d.get("rate_limits")
    if rl:
        try:
            paths.save_json(paths.rate_limits_file(), {"rate_limits": rl, "_saved_at": time.time()})
        except Exception:
            pass

    out = ""
    chained = paths.load_json(paths.config_file()).get("chain_statusline")
    if chained:
        try:
            out = run_chained(chained, raw)
        except Exception:
            out = ""
    if not out.strip():  # failed or printed nothing: never leave the status line blank
        out = default_line(d, rl)

    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()

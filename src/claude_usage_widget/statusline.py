"""Claude Code status line command.

Claude Code pipes a JSON blob to this command after each turn. For Claude subscribers it contains
`rate_limits` (5-hour and weekly usage). We save that for the widget, then print a status line:
either the output of the user's previous status line command (if the installer chained one) or a
short default line.
"""
import json
import subprocess
import sys
import time

from . import paths


def _pct(v):
    if isinstance(v, dict) and isinstance(v.get("used_percentage"), (int, float)):
        return v["used_percentage"]
    return None


def main():
    raw = sys.stdin.read()
    try:
        d = json.loads(raw)
    except Exception:
        d = {}

    rl = d.get("rate_limits")
    if rl:
        try:
            paths.save_json(paths.rate_limits_file(), {"rate_limits": rl, "_saved_at": time.time()})
        except Exception:
            pass

    chained = paths.load_json(paths.config_file()).get("chain_statusline")
    if chained:
        try:
            r = subprocess.run(chained, shell=True, input=raw, capture_output=True, text=True, timeout=10)
            sys.stdout.write(r.stdout)
            return
        except Exception:
            pass

    parts = [(d.get("model") or {}).get("display_name", "Claude")]
    for key, label in (("five_hour", "5h"), ("seven_day", "wk")):
        p = _pct((rl or {}).get(key))
        if p is not None:
            parts.append(f"{label} {p:.0f}%")
    print(" · ".join(parts))


if __name__ == "__main__":
    main()

# Claude Usage Widget

Always-on-top PySide6 desktop widget (plus tray icon and optional GNOME top-bar extension) that shows
live Claude Code plan limits (5-hour / weekly), per-model tokens and API-equivalent cost.
Runs on Windows, macOS and Linux. Python 3.9+.

## Layout

```
src/claude_usage_widget/
  __main__.py    CLI entry (argparse); imports Qt lazily so --setup/--teardown work without it
  app.py         Qt widget, tray icon, menu-bar pill drawing, single-instance socket, --screenshot
  macbar.py      macOS only: variable-width NSStatusItem with the long pills (Qt's tray is square there)
  usage.py       transcript parsing, PRICES table, cost, limits, notifications   [stdlib only]
  statusline.py  Claude Code statusLine command: saves rate_limits.json, chains old command [stdlib only]
  system.py      autostart, statusLine install/uninstall, notifications, window tweaks  [stdlib only]
  paths.py       per-OS data/config locations                                    [stdlib only]
  demo.py        sample data for screenshots
install.py       stdlib-only installer: private venv, statusLine hook, autostart, GNOME extension
gnome-extension/claude-usage@local/   GJS extension reading rate_limits.json
tests/test_usage.py                   unittest, no Qt needed
docs/            README media; make_media.py / make_diagram.py regenerate them
```

## Commands

```bash
python -m unittest discover -s tests -v                               # unit tests
QT_QPA_PLATFORM=offscreen python -m claude_usage_widget --screenshot /tmp/shot.png   # render with demo data
QT_QPA_PLATFORM=offscreen python docs/make_media.py                    # regenerate README images (needs pillow)
```

Dev setup: `python3 -m venv .venv && . .venv/bin/activate && pip install -e .`

## Rules

- **`usage.py`, `statusline.py`, `system.py`, `paths.py` must stay standard-library only.** The installer
  and the status line hook import them without the venv. Never import PySide6 there.
- **Do not run `install.py`, `--setup` or `--teardown` against the real environment.** They rewrite
  `~/.claude/settings.json` (`statusLine`) and autostart entries for the user's live install. To test them,
  isolate both dirs:
  `CLAUDE_CONFIG_DIR=$(mktemp -d) CLAUDE_USAGE_WIDGET_HOME=$(mktemp -d) python install.py --no-launch --no-autostart --no-gnome-extension --skip-lib-check`
- Cross-platform: every OS-specific branch uses `IS_WINDOWS` / `IS_MAC` / `IS_LINUX` from `paths.py`.
  Claude Code runs the status line through bash even on Windows (forward-slash paths, quoted).
  CI runs Windows and macOS on Python 3.9 and 3.13, Ubuntu on 3.10 and 3.13 — keep 3.9 syntax
  (no `match`, no `X | Y` types).
- Never overwrite Claude Code's `settings.json` from a failed read: load it with `paths.load_json_strict`
  (raises `ValueError`), not `load_json` (returns `{}`).
- Data folder: `paths.data_dir()` = `CLAUDE_USAGE_WIDGET_HOME`, else the parent of an installed venv
  (marked by `paths.VENV_MARKER`), else the OS default. The GNOME extension reads it from the
  `data-dir` key `install.py` stamps into its `metadata.json`. Always go through `data_dir()`.
- The status line hook does all I/O as UTF-8 bytes and runs the chained command with bash, like Claude Code.
- Thresholds and colors are duplicated on purpose and must stay in sync: green < 80, amber 80–89, red ≥ 90,
  ⚠ at ≥ 95. Locations: `usage.status_level` / `THRESHOLDS`, `app.STATUS`, `app.PILL` (mirrors the
  extension's `stylesheet.css`), `usage.pill_text` (mirrors the extension's pill label),
  `gnome-extension/.../extension.js` (`colorFor`) and `stylesheet.css`, the README color table, and `docs/*.svg`.
- Prices: `PRICES` in `usage.py` (USD per MTok: input, output, cache read; longest prefix wins). When
  changing prices, also update the tests in `tests/test_usage.py`.
- The widget makes no network requests and never reads credentials. Keep it that way.
- Version lives in both `pyproject.toml` and `src/claude_usage_widget/__init__.py`.

## Style

- Small, plain functions; short docstrings; no type-heavy code. Match the surrounding style.
- Commit subjects: short imperative sentence, optional `Area:` prefix (e.g. `README: …`, `CI: …`, `Tray icon: …`).
- User-facing text (README, notifications) is written for non-technical users: plain words, short sentences.

# Claude Usage Widget

A small always-on-top Linux desktop widget that shows your Claude Code usage live, plus colored pills in the GNOME top bar for your plan limits.

## Features

- **Plan limits:** 5-hour and weekly usage bars with reset countdowns, the same numbers `/usage` shows.
- **Per-model usage today:** tokens and API-equivalent cost for each model, with a live dot on models in use.
- **Today's cost:** what the day's usage would cost at Claude API list prices, cache tokens included.
- **Desktop notifications:** an alert at 80% and an urgent one at 90% of each limit, once per limit period.
- **Top-bar pills:** for example `30% 5h · 4h 14m` and `14% wk · 4d 2h`. They're green under 80%, amber from 80% to 89% and red from 90%, with ⚠ from 95%. A soft fill inside each pill shows how much of the limit is used.
- **Widget behavior:** it stays above other windows, appears on every workspace, can be dragged anywhere and remembers its position. Its opacity is adjustable, and it can be minimized to the tray.

## How it works

| Piece | What it does |
|---|---|
| `bin/claude-token-widget` | GTK 3 widget (Python). It reads new lines from Claude Code's session logs in `~/.claude/projects/**/*.jsonl` every 2 seconds for token counts and cost, and shows tray pills through AppIndicator. |
| `bin/claude-statusline` | A Claude Code [status line](https://docs.claude.com/en/docs/claude-code/statusline) command. Claude Code passes it your plan's `rate_limits`, and it saves them to `~/.cache/claude-token-widget/rate_limits.json` for the widget and extension. It also prints `Opus 5.5 · 5h 30% · wk 14%` in your terminal. |
| `gnome-extension/claude-usage@local` | GNOME Shell extension that draws the limit pills directly in the top bar. While it runs, the widget hides its own AppIndicator pills. |

Plan limits only update while a Claude Code session is running. Nothing reads or sends your login token.

## Requirements

- Linux with GNOME (tested on Ubuntu, GNOME 50, Wayland). Other X11 desktops work without the extension.
- Python 3 with PyGObject: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 libnotify-bin`
- Claude Code, signed in with a Claude subscription, for plan limits.

## Install

```bash
git clone <this repo> && cd claude-usage-widget
./install.sh
```

The installer copies the scripts to `~/.local/bin`, registers the status line in `~/.claude/settings.json` (an existing status line is left as it is), adds autostart and app-menu entries, installs and enables the GNOME extension, and starts the widget. On Wayland, log out and back in once to load the extension.

## Usage

- **Widget:** left-drag to move it. Click **–** to minimize it to the tray. Right-click for Minimize, Refresh, Opacity, Test notification, Reset position and Quit.
- **Tray pills:** click either pill for Show/hide widget and the limit details.
- **Command line:** `claude-token-widget` starts the widget, or shows it if it's already running. `gapplication action local.claude.usage_widget toggle` shows or hides it.

## Notes

- On GNOME Wayland, apps can't keep their own windows on top. The widget runs through XWayland (`GDK_BACKEND=x11`), where GNOME does honor always-on-top and show-on-all-workspaces.
- Cost uses the API list prices in the `PRICES` table at the top of `bin/claude-token-widget`. On a subscription it shows what the usage would cost at API prices, not what you're billed. It runs a few percent lower than Claude Code's own figure because some background requests aren't written to the session logs.
- Settings and state are stored in `~/.config/claude-token-widget.json` (position, opacity, minimized) and `~/.cache/claude-token-widget/` (limits, notification state, tray images).

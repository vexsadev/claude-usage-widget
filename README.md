# Claude Usage Widget

**See your Claude Code usage live, without typing `/usage`.** A small widget that floats above your other windows on Windows, macOS and Linux. It shows:

- your **5-hour** and **weekly** plan limits, with countdowns to when they reset
- the tokens **each model** has used today, plus what that would cost at API prices
- **desktop alerts** at 80% and 90% of each limit

![Claude Usage Widget](docs/widget.png)

[![CI](https://github.com/vexsadev/claude-usage-widget/actions/workflows/ci.yml/badge.svg)](https://github.com/vexsadev/claude-usage-widget/actions/workflows/ci.yml)

> This is an unofficial community tool, not made or endorsed by Anthropic. "Claude" is a trademark of Anthropic.

---

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Install on Windows](#install-on-windows)
- [Install on macOS](#install-on-macos)
- [Install on Linux](#install-on-linux)
- [Using the widget](#using-the-widget)
- [Updating](#updating)
- [Uninstalling](#uninstalling)
- [Troubleshooting](#troubleshooting)
- [How it works](#how-it-works)
- [Privacy](#privacy)
- [Development](#development)

---

## Features

| | |
|---|---|
| **Plan limits** | 5-hour and weekly bars, the same numbers as Claude Code's `/usage`, with a countdown to each reset. |
| **Colors** | **Green** under 80%, **amber** from 80% to 89%, **red** from 90%, and a ⚠ sign from 95%. |
| **Per-model usage** | Today's tokens and cost for each model, such as Opus, Sonnet and Haiku. A dot lights up while a model is in use. |
| **Today's cost** | What today's usage would cost at Claude API list prices, with cache tokens counted at their own rates. |
| **Alerts** | A desktop notification at 80% and an urgent one at 90% of each limit, sent once per limit period. |
| **Always visible** | Stays above other windows, shows on every desktop or Space, can be dragged anywhere and remembers its position. |
| **Tray icon** | Two small bars (5-hour and weekly) in the system tray or menu bar. Hover over them for details, or click to show or hide the widget. |
| **GNOME top bar** *(Linux, optional)* | Colored pills such as `34% 5h · 3h 11m` and `82% wk · 2d 4h`, drawn right in the top bar. |
| **Start at login** | On by default. You can turn it off from the right-click menu. |

## Requirements

1. **[Claude Code](https://docs.claude.com/en/docs/claude-code/overview)** installed and signed in.
   - The **plan limits** (5-hour and weekly) only appear if you sign in with a **Claude subscription (Pro or Max)**. If you use Claude Code with an API key, you'll still see tokens and cost, but no limit bars.
2. **Python 3.9 or newer.** The installer creates its own private environment and installs everything else, including the Qt toolkit (a one-time download of about 100 MB).
3. **About 300 MB of disk space.**

---

## Install on Windows

**1. Install Python** (skip this if `py --version` already shows 3.9 or newer).
- Download it from <https://www.python.org/downloads/windows/> and run the installer.
- **Tick "Add python.exe to PATH"** on the first screen.
- Or, in PowerShell: `winget install Python.Python.3.13`

**2. Download this project.**
- **With Git:** run `git clone https://github.com/vexsadev/claude-usage-widget.git` in PowerShell.
- **Without Git:** click the green **Code** button above, choose **Download ZIP**, and extract it, for example to `Downloads\claude-usage-widget`.

**3. Run the installer.** Open **PowerShell** in the project folder (in File Explorer, open the folder, type `powershell` in the address bar and press Enter), then run:

```powershell
py install.py
```

**4. Start a Claude Code session** (`claude`) and send any message. The limit bars fill in after the first reply.

The widget appears in the top-right corner of your screen. Its tray icon is in the bottom-right of the taskbar; if you don't see it, click **^** to show hidden icons, and drag the icon onto the taskbar to keep it there. You'll also find **Claude Usage Widget** in the Start menu.

## Install on macOS

**1. Get Python 3 and Git.** Either one works:
- **Apple's developer tools** (simplest): run `xcode-select --install` in Terminal and click **Install**. This provides both `python3` and `git`.
- **Homebrew:** `brew install python git`

**2. Download this project and run the installer** in **Terminal**:

```bash
git clone https://github.com/vexsadev/claude-usage-widget.git
cd claude-usage-widget
python3 install.py
```

**3. Start a Claude Code session** (`claude`) and send any message so the limits appear.

The widget appears in the top-right corner and shows on every Space. Its icon is in the **menu bar**; click it for the menu. It doesn't add a Dock icon.

> **Notifications:** the first alert comes from *Script Editor*. If macOS asks, click **Allow**. If you don't see alerts, check **System Settings → Notifications → Script Editor**.

## Install on Linux

**1. Install the system packages.**

*Ubuntu / Debian:*
```bash
sudo apt install -y git python3 python3-venv libnotify-bin \
  libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1
```

*Fedora:*
```bash
sudo dnf install -y git python3 libnotify xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11
```

*Arch:*
```bash
sudo pacman -S --needed git python libnotify xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11
```

**2. Download this project and run the installer:**

```bash
git clone https://github.com/vexsadev/claude-usage-widget.git
cd claude-usage-widget
python3 install.py
```

**3. GNOME only:** log out and back in once. The installer adds a GNOME Shell extension that draws colored limit pills in the top bar, and GNOME only loads new extensions at login.

**4. Start a Claude Code session** (`claude`) and send any message so the limits appear.

**Notes:**
- **Tray icon on GNOME:** GNOME needs an AppIndicator extension to show tray icons. Ubuntu includes one. On Fedora and other distributions, install [AppIndicator and KStatusNotifierItem Support](https://extensions.gnome.org/extension/615/appindicator-support/). Or rely on the top-bar pills; while they're running, the widget hides its own tray icon.
- **KDE, Xfce, Cinnamon** and other desktops show the tray icon out of the box.
- **Wayland:** Wayland doesn't let apps keep their own windows on top, so the widget runs through XWayland (X11 compatibility), where always-on-top works. That's why the X11 (`xcb`) libraries above are needed.

---

## Using the widget

| To... | Do this |
|---|---|
| Move the widget | Drag it with the left mouse button. Its position is remembered. |
| Hide the widget | Click the **–** button at its top-right. It keeps running in the tray. |
| Show it again | Click the tray icon (Windows and Linux) or use its menu (macOS), or run `claude-usage-widget` again. |
| Change the transparency | Right-click → **Opacity** |
| Turn start at login on or off | Right-click → **Start at login** |
| Check that notifications work | Right-click → **Test notification** |
| Quit | Right-click → **Quit** |

**Starting it by hand:** it starts at login automatically, but you can also start it yourself.
- **Windows:** Start menu → **Claude Usage Widget**
- **Linux:** the app menu, or `claude-usage-widget` in a terminal
- **macOS:** `"$HOME/Library/Application Support/claude-usage-widget/venv/bin/claude-usage-widget"`

Running it again while it's already running just shows it. Add `--toggle` to show or hide it, or `--quit` to quit it.

### What the numbers mean

- **5-hour / Weekly:** the percentage of your plan's limit used so far, the same numbers `/usage` shows, and when that limit resets.
- **Today ≈ $X:** what today's Claude Code usage *would* cost at Claude API list prices. **If you're on a subscription, you aren't charged this amount.** It's a guide to how heavy your usage is. It usually comes out a few percent lower than Claude Code's own figure, because some small background requests aren't saved to the session logs. If the total starts with "≥", a model you used isn't in the price list, so the real figure is higher.
- **Model rows:** today's total tokens (input, output and cache) and cost for each model. A highlighted dot means that model was used in the last 2 minutes.

## Updating

```bash
cd claude-usage-widget
git pull
python3 install.py        # Windows: py install.py
```

Your settings (position, opacity, start at login) are kept.

## Uninstalling

```bash
cd claude-usage-widget
python3 install.py --uninstall        # Windows: py install.py --uninstall
```

This stops the widget, removes start at login, the Start menu or app-menu entry and the GNOME extension, deletes the app folder, and restores your previous Claude Code status line. Add `--keep-data` to keep your settings.

---

## Troubleshooting

**The limit bars say "waiting for Claude Code".**
- The limits come from Claude Code itself. Run `claude`, send a message, and wait for the reply. They only update while a Claude Code session is open.
- Your Claude Code setting must still point at the widget. Open `~/.claude/settings.json` and check that `statusLine.command` contains `claude_usage_widget.statusline`. Running the installer again fixes it.
- Plan limits are only provided for Claude subscription logins (Pro or Max), not for API-key usage.

**I already had a custom status line.**
The installer keeps it. Claude Code runs the widget's hook first, and the hook then runs your original command, so your terminal still shows your own status line. Uninstalling puts it back.

**The widget doesn't stay on top or follow me between desktops (Linux).**
Make sure the X11 libraries from the Linux install steps are installed, then run the installer again. Some tiling window managers ignore always-on-top requests. In that case, add a floating or sticky rule for the widget window; run `xprop WM_CLASS` and click the widget to find its window class.

**`qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` (Linux).**
Install the libraries listed in the Linux install steps.

**No tray icon on GNOME.**
See the Linux notes above. You need an AppIndicator extension or the included top-bar extension, and you need to log out and back in after installing.

**`py` or `python3` is not recognized (Windows).**
Reinstall Python and tick **Add python.exe to PATH**, or run it with its full path, for example `C:\Users\<you>\AppData\Local\Programs\Python\Python313\python.exe install.py`.

**I use a custom Claude config folder.**
If you set `CLAUDE_CONFIG_DIR`, make sure it's also set when the widget starts at login. The widget looks for logs in `$CLAUDE_CONFIG_DIR/projects`.

**Prices look wrong.**
Prices are in the `PRICES` table at the top of [`src/claude_usage_widget/usage.py`](src/claude_usage_widget/usage.py). Pull requests are welcome when Anthropic changes them.

---

## How it works

```
Claude Code ──(after each turn, JSON on stdin)──▶ status line hook ──▶ rate_limits.json ─┐
     │                                                                                     ├─▶ widget, tray icon, GNOME pills
     └──(writes)──▶ ~/.claude/projects/**/*.jsonl ──(widget reads new lines every 2 s)──────┘
```

- **Plan limits:** Claude Code passes JSON to its [status line command](https://docs.claude.com/en/docs/claude-code/statusline) after each turn, and that JSON includes `rate_limits.five_hour` and `rate_limits.seven_day` (`used_percentage`, `resets_at`). The installer registers a small hook as your status line, and the hook saves those values to a file.
- **Tokens and cost:** Claude Code saves each session as a JSONL file. The widget reads only the new lines, counts each request's `usage` block once, and prices it by model.
- **Single instance:** starting the widget a second time just shows the copy that's already running, using a local socket.

### File locations

| | Windows | macOS | Linux |
|---|---|---|---|
| App, venv, settings, data | `%LOCALAPPDATA%\claude-usage-widget` | `~/Library/Application Support/claude-usage-widget` | `~/.local/share/claude-usage-widget` |
| Start at login | Registry `HKCU\…\Run\ClaudeUsageWidget` | `~/Library/LaunchAgents/io.github.claude-usage-widget.plist` | `~/.config/autostart/claude-usage-widget.desktop` |
| Claude Code setting changed | `~/.claude/settings.json` → `statusLine` | same | same |

## Privacy

Everything runs on your own computer. The widget makes **no network requests**, never reads your Claude login or API keys, and only reads Claude Code's local session logs and the limit numbers Claude Code passes to the status line. The only network use is the one-time download of the Python packages during install.

## Development

```bash
python3 -m venv .venv && . .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
python -m unittest discover -s tests -v             # unit tests (no display needed)
QT_QPA_PLATFORM=offscreen claude-usage-widget --screenshot shot.png   # render with demo data
```

CI runs the unit tests, the real installer, a headless render, a status line check and the uninstaller on **Windows, macOS and Linux** (Python 3.9 and 3.13) for every push.

Project layout:

```
src/claude_usage_widget/
  app.py         Qt widget, tray icon, single instance
  usage.py       transcript parsing, prices, limits, notifications (standard library only)
  system.py      start at login, status line hook, notifications, window tweaks per OS
  statusline.py  the Claude Code status line hook
  paths.py       per-OS file locations
gnome-extension/claude-usage@local/   optional GNOME top-bar pills
install.py     cross-platform installer and uninstaller (standard library only)
```

## License

[MIT](LICENSE). Free to use, modify and share.

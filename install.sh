#!/usr/bin/env bash
# Install the Claude usage widget, status line hook, autostart entry and GNOME Shell extension.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BIN="$HOME/.local/bin"
EXT_UUID="claude-usage@local"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
SETTINGS="$HOME/.claude/settings.json"

echo "==> Checking dependencies"
missing=()
python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" 2>/dev/null || missing+=(python3-gi gir1.2-gtk-3.0)
python3 -c "import gi.repository; import gi; gi.require_foreign('cairo')" 2>/dev/null || missing+=(python3-gi-cairo)
python3 -c "import gi; gi.require_version('AyatanaAppIndicator3','0.1')" 2>/dev/null || missing+=(gir1.2-ayatanaappindicator3-0.1)
command -v notify-send >/dev/null || missing+=(libnotify-bin)
if ((${#missing[@]})); then
    echo "    Missing packages: ${missing[*]}"
    echo "    Install with: sudo apt install -y ${missing[*]}"
fi

echo "==> Installing scripts to $BIN"
mkdir -p "$BIN"
install -m 755 "$HERE/bin/claude-token-widget" "$BIN/claude-token-widget"
install -m 755 "$HERE/bin/claude-statusline" "$BIN/claude-statusline"

echo "==> Registering Claude Code status line in $SETTINGS"
mkdir -p "$(dirname "$SETTINGS")"
python3 - "$SETTINGS" "$BIN/claude-statusline" <<'EOF'
import json, os, sys
path, cmd = sys.argv[1], sys.argv[2]
d = {}
if os.path.exists(path):
    with open(path) as f:
        d = json.load(f)
cur = d.get("statusLine")
if cur and cur.get("command") != cmd:
    print(f"    Existing statusLine kept ({cur.get('command')}); set it to {cmd} to feed plan limits to the widget.")
else:
    d["statusLine"] = {"type": "command", "command": cmd}
    with open(path, "w") as f:
        json.dump(d, f, indent=2)
EOF

echo "==> Adding autostart and app-menu entries"
DESKTOP="[Desktop Entry]
Type=Application
Name=Claude Token Widget
Comment=Live Claude Code usage, always on top
Exec=$BIN/claude-token-widget
Icon=utilities-system-monitor
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
Terminal=false"
mkdir -p "$HOME/.config/autostart" "$HOME/.local/share/applications"
printf '%s\n' "$DESKTOP" > "$HOME/.config/autostart/claude-token-widget.desktop"
printf '%s\n' "$DESKTOP" > "$HOME/.local/share/applications/claude-token-widget.desktop"

if command -v gnome-shell >/dev/null; then
    echo "==> Installing GNOME Shell extension ($EXT_UUID)"
    mkdir -p "$EXT_DIR"
    cp "$HERE/gnome-extension/$EXT_UUID/"* "$EXT_DIR/"
    python3 - "$EXT_UUID" <<'EOF'
import ast, subprocess, sys
uuid = sys.argv[1]
cur = subprocess.run(["gsettings", "get", "org.gnome.shell", "enabled-extensions"],
                     capture_output=True, text=True).stdout.strip()
lst = [] if not cur or cur.startswith("@as") else ast.literal_eval(cur)
if uuid not in lst:
    lst.append(uuid)
    subprocess.run(["gsettings", "set", "org.gnome.shell", "enabled-extensions", str(lst)], check=True)
EOF
    echo "    Log out and back in to load the extension (required on Wayland)."
fi

echo "==> Starting the widget"
if ! pgrep -x -f "python3 $BIN/claude-token-widget" >/dev/null; then
    setsid nohup "$BIN/claude-token-widget" >/dev/null 2>&1 < /dev/null &
fi
echo "Done."

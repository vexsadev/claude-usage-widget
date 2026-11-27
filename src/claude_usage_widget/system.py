"""OS integration: autostart, Claude Code status line hook, notifications, window tweaks.

Standard library only (Qt is not imported here), so the installer can call into it.
"""
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from . import paths
from .paths import IS_LINUX, IS_MAC, IS_WINDOWS

AUTOSTART_NAME = "ClaudeUsageWidget"
MAC_AGENT_ID = "io.github.claude-usage-widget"
GNOME_EXT_UUID = "claude-usage@local"


# ---------- how to launch the widget ----------

def launch_command():
    """argv that starts the widget without a console window."""
    exe = Path(sys.executable)
    if IS_WINDOWS:
        pyw = exe.with_name("pythonw.exe")
        if pyw.exists():
            exe = pyw
    return [str(exe), "-m", "claude_usage_widget"]


def statusline_command():
    """Shell command Claude Code runs for the status line (Claude Code uses bash, also on Windows)."""
    exe = Path(sys.executable)
    if IS_WINDOWS:
        p = exe.with_name("python.exe")
        exe = p if p.exists() else exe
        return f'"{exe.as_posix()}" -m claude_usage_widget.statusline'
    return f"{shlex.quote(str(exe))} -m claude_usage_widget.statusline"


# ---------- autostart ----------

def _linux_autostart_file():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / "claude-usage-widget.desktop"


def _mac_agent_file():
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_AGENT_ID}.plist"


DESKTOP_RESERVED = set(' \t\n"\'\\><~|&;$*?#()`')


def desktop_exec(cmd):
    """argv -> Exec= value per the Desktop Entry spec.

    Arguments with reserved characters go in double quotes with " ` $ \\ backslash-escaped; then
    the string-value escape doubles every backslash, and % becomes %% (field codes).
    """
    out = []
    for a in map(str, cmd):
        if any(ch in DESKTOP_RESERVED for ch in a) or not a:
            a = '"' + "".join("\\" + ch if ch in '"`$\\' else ch for ch in a) + '"'
        out.append(a)
    return " ".join(out).replace("\\", "\\\\").replace("%", "%%")


def desktop_entry(cmd):
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Claude Usage Widget",
        "Comment=Live Claude Code usage: plan limits, tokens and cost",
        "Exec=" + desktop_exec(cmd),
        "Icon=utilities-system-monitor",
        "Terminal=false",
        "Categories=Utility;",
        "X-GNOME-Autostart-enabled=true",
        "X-GNOME-Autostart-Delay=5",
        "",
    ])


def autostart_enabled():
    if IS_WINDOWS:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                winreg.QueryValueEx(k, AUTOSTART_NAME)
                return True
        except OSError:
            return False
    if IS_MAC:
        return _mac_agent_file().exists()
    return _linux_autostart_file().exists()


def set_autostart(enabled):
    cmd = launch_command()
    if IS_WINDOWS:
        import winreg
        # CreateKeyEx also opens the key when it exists (it can be missing on fresh accounts)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, AUTOSTART_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
            else:
                try:
                    winreg.DeleteValue(k, AUTOSTART_NAME)
                except OSError:
                    pass
    elif IS_MAC:
        f = _mac_agent_file()
        if enabled:
            import plistlib
            f.parent.mkdir(parents=True, exist_ok=True)
            with open(f, "wb") as fh:
                plistlib.dump({"Label": MAC_AGENT_ID, "ProgramArguments": cmd,
                               "RunAtLoad": True, "ProcessType": "Interactive"}, fh)
        elif f.exists():
            f.unlink()
    else:
        f = _linux_autostart_file()
        if enabled:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(desktop_entry(cmd))
        elif f.exists():
            f.unlink()


# ---------- Claude Code status line ----------

def install_statusline():
    """Point Claude Code's statusLine at our command; chain any existing one. Returns a message."""
    settings_path = paths.claude_settings_file()
    settings = paths.load_json_strict(settings_path)  # ValueError if unreadable: never overwrite it
    ours = statusline_command()
    cur = settings.get("statusLine") or {}
    msg = "Status line registered."
    if cur.get("command") and "claude_usage_widget.statusline" not in cur["command"]:
        cfg = paths.load_json(paths.config_file())
        cfg["chain_statusline"] = cur["command"]
        paths.save_json(paths.config_file(), cfg)
        msg = f"Status line registered (your previous one is kept and still shown: {cur['command']})."
    new = dict(cur) if isinstance(cur, dict) else {}
    new.update({"type": "command", "command": ours})
    settings["statusLine"] = new
    paths.save_json(settings_path, settings)
    return msg


def uninstall_statusline():
    settings_path = paths.claude_settings_file()
    settings = paths.load_json_strict(settings_path)  # ValueError if unreadable: never overwrite it
    cur = settings.get("statusLine") or {}
    if "claude_usage_widget.statusline" not in str(cur.get("command", "")):
        return
    cfg = paths.load_json(paths.config_file())
    chained = cfg.pop("chain_statusline", None)
    if chained:
        cur["command"] = chained
        settings["statusLine"] = cur
    else:
        settings.pop("statusLine", None)
    paths.save_json(settings_path, settings)
    if chained and paths.config_file().exists():  # --keep-data keeps config.json; don't revive it later
        paths.save_json(paths.config_file(), cfg)


# ---------- notifications ----------

def notify(title, body, urgent=False, fallback=None):
    """Native desktop notification; `fallback(title, body)` is used if no native tool works."""
    try:
        if IS_LINUX and shutil.which("notify-send"):
            subprocess.Popen(["notify-send", "-a", "Claude Usage", "-u", "critical" if urgent else "normal",
                              "-i", "dialog-warning", title, body])
            return
        if IS_MAC and shutil.which("osascript"):
            def q(s):
                return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
            subprocess.Popen(["osascript", "-e", f"display notification {q(body)} with title {q(title)}"])
            return
    except Exception:
        pass
    if fallback:
        fallback(title, body)


# ---------- Linux / GNOME ----------

def gnome_extension_active():
    """True when our GNOME Shell extension is running (it then draws the top-bar pills)."""
    if not IS_LINUX or not shutil.which("gnome-extensions"):
        return False
    try:
        out = subprocess.run(["gnome-extensions", "info", GNOME_EXT_UUID],
                             capture_output=True, text=True, timeout=3).stdout
        return "State: ACTIVE" in out
    except Exception:
        return False


def x11_make_sticky(win_id, qt_platform):
    """Ask the X11 window manager to show the window on all workspaces (best effort).

    Sets _NET_WM_DESKTOP=0xFFFFFFFF and _NET_WM_STATE=[STICKY, ABOVE] before the window is mapped.
    Only when Qt itself runs on X11 ("xcb"): on Wayland, winId() is not an X window, and the
    BadWindow error would make Xlib's default handler exit the whole process.
    """
    if not IS_LINUX or qt_platform != "xcb" or not os.environ.get("DISPLAY"):
        return
    try:
        import ctypes
        import ctypes.util
        lib = ctypes.util.find_library("X11")
        if not lib:
            return
        x = ctypes.cdll.LoadLibrary(lib)
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XInternAtom.restype = ctypes.c_ulong
        x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x.XChangeProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        x.XFlush.argtypes = [ctypes.c_void_p]
        x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        dpy = x.XOpenDisplay(None)
        if not dpy:
            return
        atom = lambda n: x.XInternAtom(dpy, n, 0)  # noqa: E731
        cardinal, xa_atom = atom(b"CARDINAL"), atom(b"ATOM")
        desk = (ctypes.c_ulong * 1)(0xFFFFFFFF)
        x.XChangeProperty(dpy, win_id, atom(b"_NET_WM_DESKTOP"), cardinal, 32, 0, desk, 1)
        states = (ctypes.c_ulong * 2)(atom(b"_NET_WM_STATE_STICKY"), atom(b"_NET_WM_STATE_ABOVE"))
        x.XChangeProperty(dpy, win_id, atom(b"_NET_WM_STATE"), xa_atom, 32, 0, states, 2)
        x.XFlush(dpy)
        x.XCloseDisplay(dpy)
    except Exception:
        pass


# ---------- macOS ----------

def mac_accessory_app():
    """Hide the Dock icon (menu-bar style app). Needs pyobjc; silently skipped otherwise."""
    if not IS_MAC:
        return
    try:
        from AppKit import NSApplication
        NSApplication.sharedApplication().setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory
    except Exception:
        pass


def menu_anchor(item_frame, primary_height, cursor, slack=4):
    """Where to open the menu-bar menu, in Qt's global coordinates (y grows downwards).

    `item_frame` is the menu-bar item's window frame (x, y, width, height) in Cocoa coordinates,
    whose y axis grows upwards from the bottom of the primary screen. Normally the menu opens just
    below the item, like a native menu. If the cursor isn't over the item, the frame can't be
    trusted (the item isn't in a real menu bar, or macOS reported it oddly), so the menu opens at
    the mouse pointer instead.
    """
    x, y, w, h = item_frame
    top, bottom = primary_height - (y + h), primary_height - y
    cx, cy = cursor
    if w > 0 and h > 0 and x - slack <= cx <= x + w + slack and top - slack <= cy <= bottom + slack:
        return int(x), int(bottom)
    return int(cx), int(cy)


def mac_all_spaces(win_id):
    """Show the window on every Space and over full-screen apps. Needs pyobjc."""
    if not IS_MAC:
        return
    try:
        import objc
        view = objc.objc_object(c_void_p=int(win_id))
        # CanJoinAllSpaces | Stationary | FullScreenAuxiliary
        view.window().setCollectionBehavior_((1 << 0) | (1 << 4) | (1 << 8))
    except Exception:
        pass

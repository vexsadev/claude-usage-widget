#!/usr/bin/env python3
"""Install / uninstall Claude Usage Widget on Windows, macOS and Linux.

    python3 install.py              # install (or update) and start the widget
    python3 install.py --uninstall  # remove everything

Uses only the Python standard library. Creates a private virtual environment, so nothing is
installed into your system Python.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))
from claude_usage_widget import paths  # noqa: E402  (stdlib-only module)

IS_WINDOWS, IS_MAC, IS_LINUX = paths.IS_WINDOWS, paths.IS_MAC, paths.IS_LINUX
EXT_UUID = "claude-usage@local"
LINUX_QT_LIBS = {  # library -> Debian/Ubuntu package
    "libxcb-cursor.so.0": "libxcb-cursor0",
    "libxkbcommon-x11.so.0": "libxkbcommon-x11-0",
    "libxcb-icccm.so.4": "libxcb-icccm4",
    "libxcb-image.so.0": "libxcb-image0",
    "libxcb-keysyms.so.1": "libxcb-keysyms1",
    "libxcb-render-util.so.0": "libxcb-render-util0",
    "libxcb-xkb.so.1": "libxcb-xkb1",
}


def step(msg):
    print(f"\n==> {msg}", flush=True)


def info(msg):
    print(f"    {msg}", flush=True)


def venv_dir():
    return paths.data_dir() / "venv"


def venv_python(gui=False):
    v = venv_dir()
    if IS_WINDOWS:
        return v / "Scripts" / ("pythonw.exe" if gui else "python.exe")
    return v / "bin" / "python"


def launcher_link():
    return Path.home() / ".local" / "bin" / "claude-usage-widget"


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def spawn_detached(cmd):
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if IS_WINDOWS:
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen([str(c) for c in cmd], **kw)


def stop_running():
    py = venv_python()
    if py.exists():
        subprocess.run([str(py), "-m", "claude_usage_widget", "--quit"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)


# ---------- platform checks ----------

def check_linux_libs():
    """Qt's X11 backend needs a few xcb libraries that minimal desktops may lack."""
    try:
        have = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True).stdout
    except Exception:
        return
    missing = [pkg for lib, pkg in LINUX_QT_LIBS.items() if lib not in have]
    if missing:
        info("Qt needs some system libraries that are missing:")
        info("  Debian/Ubuntu: sudo apt install -y " + " ".join(missing))
        info("  Fedora:        sudo dnf install -y xcb-util-cursor xcb-util-wm xcb-util-image "
             "xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11")
        info("  Arch:          sudo pacman -S --needed xcb-util-cursor xcb-util-wm xcb-util-image "
             "xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11")
        info("Install them, then run this installer again.")
        return False
    return True


# ---------- desktop integration ----------

def linux_desktop_files(cmd):
    from claude_usage_widget.system import desktop_entry
    apps = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / "claude-usage-widget.desktop").write_text(desktop_entry(cmd).replace(
        "X-GNOME-Autostart-enabled=true\nX-GNOME-Autostart-Delay=5\n", ""))
    link = launcher_link()
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(venv_dir() / "bin" / "claude-usage-widget")
    info(f"Command: {link}")
    if str(link.parent) not in os.environ.get("PATH", "").split(os.pathsep):
        info(f"(add {link.parent} to your PATH to run 'claude-usage-widget' from a terminal)")


def gnome_extension(install):
    if not IS_LINUX or not shutil.which("gnome-shell"):
        return
    dest = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") \
        / "gnome-shell" / "extensions" / EXT_UUID
    try:
        cur = subprocess.run(["gsettings", "get", "org.gnome.shell", "enabled-extensions"],
                             capture_output=True, text=True).stdout.strip()
        import ast
        enabled = [] if not cur or cur.startswith("@as") else ast.literal_eval(cur)
    except Exception:
        enabled = None
    if install:
        step("Installing GNOME Shell extension (colored limit pills in the top bar)")
        dest.mkdir(parents=True, exist_ok=True)
        for f in (HERE / "gnome-extension" / EXT_UUID).iterdir():
            shutil.copy2(f, dest / f.name)
        if enabled is not None and EXT_UUID not in enabled:
            subprocess.run(["gsettings", "set", "org.gnome.shell", "enabled-extensions",
                            str(enabled + [EXT_UUID])])
        info("Log out and back in once to load it (GNOME requires this for new extensions).")
    else:
        if dest.exists():
            shutil.rmtree(dest)
        if enabled and EXT_UUID in enabled:
            enabled.remove(EXT_UUID)
            subprocess.run(["gsettings", "set", "org.gnome.shell", "enabled-extensions", str(enabled)])


def windows_shortcut(create):
    lnk = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" \
        / "Claude Usage Widget.lnk"
    if not create:
        if lnk.exists():
            lnk.unlink()
        return
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
        "$s.TargetPath='{exe}';$s.Arguments='-m claude_usage_widget';"
        "$s.Description='Live Claude Code usage';$s.Save()"
    ).format(lnk=str(lnk).replace("'", "''"), exe=str(venv_python(gui=True)).replace("'", "''"))
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, text=True)
    if r.returncode == 0:
        info("Start menu shortcut: Claude Usage Widget")


# ---------- main flows ----------

def remove_hooks():
    """Undo `--setup`: restore Claude Code's status line and turn off start at login.

    Runs in this interpreter, not the venv's: the venv can be broken (a Homebrew or distro Python
    upgrade leaves venv/bin/python dangling), and system.py is standard library only.
    Raises ValueError, without changing anything, if Claude Code's settings.json is unreadable.
    """
    from claude_usage_widget import system
    system.uninstall_statusline()
    system.set_autostart(False)


def install(args):
    if sys.version_info < (3, 9):
        sys.exit("Python 3.9 or newer is required.")
    print(f"Installing Claude Usage Widget into {paths.data_dir()}")

    if IS_LINUX:
        step("Checking system libraries")
        if check_linux_libs() is False and not args.skip_lib_check:
            sys.exit(1)
        info("OK")

    step("Creating a private Python environment")
    if not venv_python().exists():
        try:
            run([sys.executable, "-m", "venv", venv_dir()])
        except subprocess.CalledProcessError:
            sys.exit("Could not create a virtual environment. On Debian/Ubuntu: sudo apt install python3-venv")
    info(str(venv_dir()))

    step("Installing the widget and Qt (first run downloads ~100 MB)")
    stop_running()
    run([venv_python(), "-m", "pip", "install", "--disable-pip-version-check", "-q", "--upgrade", "pip"])
    run([venv_python(), "-m", "pip", "install", "--disable-pip-version-check", "-q", "--upgrade", HERE])
    info("Done")

    step("Connecting to Claude Code (status line) and setting start at login")
    setup = [venv_python(), "-m", "claude_usage_widget", "--setup"]
    if args.no_autostart:
        setup.append("--no-autostart")
    try:
        run(setup)
    except subprocess.CalledProcessError:
        sys.exit("Could not connect to Claude Code (see the message above).")

    launch = [str(venv_python(gui=True)), "-m", "claude_usage_widget"]
    if IS_LINUX:
        step("Adding app-menu entry")
        linux_desktop_files(launch)
        if not args.no_gnome_extension:
            gnome_extension(True)
    elif IS_WINDOWS:
        step("Adding Start menu shortcut")
        windows_shortcut(True)

    if not args.no_launch:
        step("Starting the widget")
        spawn_detached(launch)
        info("It appears in the top-right corner of your main screen.")

    print("\nInstalled. Open a Claude Code session (claude) and send a message so the plan limits appear.")
    print("To start it again later:", subprocess.list2cmdline([str(c) for c in launch]))


def uninstall(args):
    print("Uninstalling Claude Usage Widget")
    step("Stopping the widget")
    try:
        stop_running()
    except Exception:
        pass  # a broken venv can't be asked to quit; the files are removed below anyway
    step("Removing status line hook and start at login")
    try:
        remove_hooks()
    except ValueError as e:
        sys.exit(f"{e}\nFix or remove that file, then run the uninstaller again. Nothing was removed.")
    if IS_LINUX:
        gnome_extension(False)
        link = launcher_link()
        if link.is_symlink():
            link.unlink()
        desk = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") \
            / "applications" / "claude-usage-widget.desktop"
        if desk.exists():
            desk.unlink()
    elif IS_WINDOWS:
        windows_shortcut(False)
    step("Removing files")
    d = paths.data_dir()
    if args.keep_data:
        shutil.rmtree(venv_dir(), ignore_errors=True)
        info(f"Kept settings in {d}")
    else:
        shutil.rmtree(d, ignore_errors=True)
        info(f"Removed {d}")
    print("\nUninstalled.")


def main():
    ap = argparse.ArgumentParser(description="Install or uninstall Claude Usage Widget.")
    ap.add_argument("--uninstall", action="store_true", help="remove the widget")
    ap.add_argument("--keep-data", action="store_true", help="with --uninstall: keep settings")
    ap.add_argument("--no-autostart", action="store_true", help="don't start the widget at login")
    ap.add_argument("--no-launch", action="store_true", help="don't start the widget after installing")
    ap.add_argument("--no-gnome-extension", action="store_true", help="Linux: skip the GNOME top-bar extension")
    ap.add_argument("--skip-lib-check", action="store_true", help="Linux: continue even if Qt libraries are missing")
    args = ap.parse_args()
    uninstall(args) if args.uninstall else install(args)


if __name__ == "__main__":
    main()

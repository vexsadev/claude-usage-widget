"""Entry point: `claude-usage-widget` / `python -m claude_usage_widget`."""
import argparse
import sys

from . import __version__


def main(argv=None):
    ap = argparse.ArgumentParser(prog="claude-usage-widget",
                                 description="Always-on-top widget showing live Claude Code usage.")
    ap.add_argument("--toggle", action="store_true", help="show/hide the running widget")
    ap.add_argument("--quit", action="store_true", help="quit the running widget")
    ap.add_argument("--screenshot", metavar="PNG", help="render the widget with demo data to a PNG and exit")
    ap.add_argument("--setup", action="store_true", help="(installer) register status line and autostart")
    ap.add_argument("--no-autostart", action="store_true", help="with --setup: don't start at login")
    ap.add_argument("--teardown", action="store_true", help="(uninstaller) remove status line and autostart")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)

    if args.setup or args.teardown:
        from . import system  # no Qt needed
        if args.setup:
            print(system.install_statusline())
            system.set_autostart(not args.no_autostart)
            print("Start at login:", "on" if not args.no_autostart else "off")
        else:
            system.uninstall_statusline()
            system.set_autostart(False)
            print("Status line and autostart removed.")
        return 0

    from . import app
    if args.screenshot:
        return app.screenshot(args.screenshot)
    return app.run(args)


if __name__ == "__main__":
    sys.exit(main())

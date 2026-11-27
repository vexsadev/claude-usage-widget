"""Tests for transcript parsing, cost, limits and notifications (no Qt needed)."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from claude_usage_widget import paths, statusline, system, usage  # noqa: E402


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def line(ts, model="claude-opus-5-5", mid="m1", rid="r1", **u):
    usage_block = {"input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 1000,
                   "cache_creation_input_tokens": 0}
    usage_block.update(u)
    return json.dumps({"type": "assistant", "requestId": rid, "timestamp": iso(ts),
                       "message": {"id": mid, "model": model, "usage": usage_block}}) + "\n"


class CostTests(unittest.TestCase):
    def test_opus55_prices(self):
        self.assertAlmostEqual(usage.request_cost("claude-opus-5-5", {"input_tokens": 1_000_000}), 4.0)
        self.assertAlmostEqual(usage.request_cost("claude-opus-5-5", {"output_tokens": 1_000_000}), 20.0)
        self.assertAlmostEqual(usage.request_cost("claude-opus-5-5", {"cache_read_input_tokens": 1_000_000}), 0.2)

    def test_cache_write_ttls(self):
        u = {"cache_creation_input_tokens": 2_000_000,
             "cache_creation": {"ephemeral_1h_input_tokens": 1_000_000}}
        # 1M at 5m (1.25x of $4) + 1M at 1h (2x of $4)
        self.assertAlmostEqual(usage.request_cost("claude-opus-5-5", u), 5.0 + 8.0)

    def test_fast_mode_doubles(self):
        self.assertAlmostEqual(usage.request_cost("claude-opus-5-5", {"output_tokens": 1_000_000, "speed": "fast"}), 40.0)

    def test_longest_prefix(self):
        self.assertAlmostEqual(usage.request_cost("claude-opus-5", {"input_tokens": 1_000_000}), 5.0)
        self.assertAlmostEqual(usage.request_cost("claude-opus-5-5-xyz", {"input_tokens": 1_000_000}), 4.0)

    def test_haiku55_long_prompt(self):
        self.assertAlmostEqual(usage.request_cost("claude-haiku-5-5", {"input_tokens": 200_000}), 0.1)

    def test_unknown_model(self):
        self.assertIsNone(usage.request_cost("some-other-model", {"input_tokens": 5}))


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "proj").mkdir()
        self.f = self.root / "proj" / "s.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_dedupe_and_incremental(self):
        now = time.time()
        self.f.write_text(line(now) + line(now))  # same message logged twice
        t = usage.Tracker([self.root])
        t.scan()
        rows = t.per_model_today()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Opus 5.5")
        self.assertEqual(rows[0]["tokens"], 1110)
        with open(self.f, "a") as fh:
            fh.write(line(now, mid="m2", rid="r2", model="claude-sonnet-5-5"))
            fh.write('{"partial": ')  # incomplete line must be ignored until finished
        t.scan()
        names = sorted(r["name"] for r in t.per_model_today())
        self.assertEqual(names, ["Opus 5.5", "Sonnet 5.5"])

    def test_skips_synthetic_and_yesterday(self):
        now = time.time()
        self.f.write_text(line(now, model="<synthetic>") + line(now - 2 * 86400, mid="old", rid="old"))
        t = usage.Tracker([self.root])
        t.scan()
        self.assertEqual(t.per_model_today(), [])

    def test_model_name(self):
        self.assertEqual(usage.model_name("claude-haiku-4-5-20251001"), "Haiku 4.5")
        self.assertEqual(usage.model_name("claude-fable-5-2"), "Fable 5.2")


class LimitsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CLAUDE_USAGE_WIDGET_HOME"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("CLAUDE_USAGE_WIDGET_HOME", None)
        self.tmp.cleanup()

    def test_load_and_rollover(self):
        now = time.time()
        paths.save_json(paths.rate_limits_file(), {"rate_limits": {
            "five_hour": {"used_percentage": 42, "resets_at": now + 600},
            "seven_day": {"used_percentage": 70, "resets_at": now - 5}}})
        lim = usage.load_limits()
        self.assertEqual(lim["five_hour"][0], 42)
        self.assertEqual(lim["seven_day"], (0.0, None))  # already reset

    def test_notifier_once_per_window(self):
        sent = []
        n = usage.Notifier(lambda t, b, urgent: sent.append((t, urgent)))
        reset = time.time() + 3600
        n.check({"five_hour": (85, reset)})
        n.check({"five_hour": (86, reset)})
        n.check({"five_hour": (91, reset)})
        self.assertEqual([s[0] for s in sent], ["Claude 5-hour limit at 80%", "Claude 5-hour limit at 90%"])
        self.assertTrue(sent[1][1])
        n.check({"five_hour": (95, reset + 18000)})  # new window
        self.assertEqual(len(sent), 3)

    def test_pill_text_matches_gnome_pills(self):
        now = 1_000_000
        self.assertEqual(usage.pill_text(34, now + 3 * 3600 + 11 * 60, "5h", now), "34% 5h · 3h 11m")
        self.assertEqual(usage.pill_text(96.4, now + 48 * 60, "5h", now), "⚠ 96% 5h · 48m")
        self.assertEqual(usage.pill_text(41, now + 4 * 86400 + 2 * 3600, "wk", now), "41% wk · 4d 2h")
        self.assertEqual(usage.pill_text(82.5, None, "wk", now), "83% wk")  # half rounds up, like JS
        self.assertEqual(usage.pill_text(None, None, "5h", now), "– 5h")

    def test_status_levels(self):
        self.assertEqual([usage.status_level(p) for p in (10, 80, 89.9, 90, None)],
                         ["ok", "warn", "warn", "high", None])


class StatuslineSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CLAUDE_USAGE_WIDGET_HOME"] = os.path.join(self.tmp.name, "app")
        os.environ["CLAUDE_CONFIG_DIR"] = os.path.join(self.tmp.name, "claude")

    def tearDown(self):
        os.environ.pop("CLAUDE_USAGE_WIDGET_HOME", None)
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.tmp.cleanup()

    def test_chains_and_restores_existing_statusline(self):
        paths.save_json(paths.claude_settings_file(), {"theme": "dark", "statusLine": {"type": "command", "command": "my-line"}})
        system.install_statusline()
        s = paths.load_json(paths.claude_settings_file())
        self.assertIn("claude_usage_widget.statusline", s["statusLine"]["command"])
        self.assertEqual(paths.load_json(paths.config_file())["chain_statusline"], "my-line")
        system.uninstall_statusline()
        s = paths.load_json(paths.claude_settings_file())
        self.assertEqual(s["statusLine"]["command"], "my-line")
        self.assertEqual(s["theme"], "dark")

    def test_settings_with_bom_keeps_other_keys(self):
        f = paths.claude_settings_file()
        f.parent.mkdir(parents=True)
        f.write_bytes(b'\xef\xbb\xbf{"theme": "dark", "permissions": {"allow": ["Bash(ls)"]}}')
        system.install_statusline()
        s = paths.load_json(f)
        self.assertEqual(s["theme"], "dark")
        self.assertEqual(s["permissions"], {"allow": ["Bash(ls)"]})
        self.assertIn("claude_usage_widget.statusline", s["statusLine"]["command"])

    def test_unreadable_settings_are_never_overwritten(self):
        f = paths.claude_settings_file()
        f.parent.mkdir(parents=True)
        broken = b'{"theme": "dark", "permissions": {},}'  # trailing comma
        f.write_bytes(broken)
        with self.assertRaises(ValueError):
            system.install_statusline()
        with self.assertRaises(ValueError):
            system.uninstall_statusline()
        self.assertEqual(f.read_bytes(), broken)

    def test_installer_removes_hooks_without_the_venv(self):
        # A Python upgrade can break the venv; uninstalling must still restore the old status line.
        import importlib.util
        from unittest import mock
        spec = importlib.util.spec_from_file_location("installer", ROOT / "install.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        self.assertFalse(installer.venv_python().exists())
        paths.save_json(paths.claude_settings_file(), {"statusLine": {"type": "command", "command": "my-line"}})
        system.install_statusline()
        with mock.patch.object(system, "set_autostart") as autostart:  # don't touch the real login items
            installer.remove_hooks()
        autostart.assert_called_once_with(False)
        self.assertEqual(paths.load_json(paths.claude_settings_file())["statusLine"]["command"], "my-line")


    def test_keep_data_uninstall_forgets_restored_command(self):
        # install -> uninstall --keep-data -> user drops their status line -> reinstall
        paths.save_json(paths.claude_settings_file(), {"statusLine": {"type": "command", "command": "old-line"}})
        system.install_statusline()
        system.uninstall_statusline()
        self.assertNotIn("chain_statusline", paths.load_json(paths.config_file()))
        paths.save_json(paths.claude_settings_file(), {})
        system.install_statusline()
        system.uninstall_statusline()
        self.assertNotIn("statusLine", paths.load_json(paths.claude_settings_file()))

    def test_save_writes_through_symlink(self):
        real = Path(self.tmp.name) / "dotfiles" / "settings.json"
        real.parent.mkdir()
        real.write_text('{"theme": "dark"}')
        link = paths.claude_settings_file()
        link.parent.mkdir(parents=True)
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not allowed here")
        system.install_statusline()
        self.assertTrue(link.is_symlink())
        self.assertIn("statusLine", paths.load_json(real))
        self.assertEqual([p.name for p in real.parent.iterdir()], ["settings.json"])  # no temp left


class CustomHomeTests(unittest.TestCase):
    """A CLAUDE_USAGE_WIDGET_HOME chosen at install time must hold later, without the variable."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "custom home"
        self.venv = self.home / "venv"
        self.venv.mkdir(parents=True)
        os.environ.pop("CLAUDE_USAGE_WIDGET_HOME", None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_installed_venv_finds_its_data_dir(self):
        from unittest import mock
        with mock.patch.object(sys, "prefix", str(self.venv)):
            self.assertNotEqual(paths.data_dir(), self.home)  # no marker: the OS default
            (self.venv / paths.VENV_MARKER).write_text("")
            self.assertEqual(paths.data_dir(), self.home)
            os.environ["CLAUDE_USAGE_WIDGET_HOME"] = str(Path(self.tmp.name) / "explicit")
            try:
                self.assertEqual(paths.data_dir(), Path(self.tmp.name) / "explicit")  # env still wins
            finally:
                os.environ.pop("CLAUDE_USAGE_WIDGET_HOME")

    def test_gnome_extension_gets_data_dir(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("installer", ROOT / "install.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        os.environ["CLAUDE_USAGE_WIDGET_HOME"] = str(self.home)
        try:
            dest = Path(self.tmp.name) / "ext"
            installer.copy_extension(dest)
        finally:
            os.environ.pop("CLAUDE_USAGE_WIDGET_HOME")
        meta = json.loads((dest / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["data-dir"], str(self.home))
        self.assertEqual(meta["uuid"], "claude-usage@local")
        self.assertTrue((dest / "extension.js").is_file())


def load_installer():
    import importlib.util
    spec = importlib.util.spec_from_file_location("installer", ROOT / "install.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    return installer


class PlatformEdgeTests(unittest.TestCase):
    def test_no_x11_calls_unless_qt_runs_on_x11(self):
        from unittest import mock
        with mock.patch.object(system, "IS_LINUX", True), \
                mock.patch.dict(os.environ, {"DISPLAY": ":0"}), \
                mock.patch("ctypes.util.find_library") as find:
            system.x11_make_sticky(1234, "wayland")  # a Wayland winId is no X window
            find.assert_not_called()

    def test_desktop_exec_quoting(self):
        self.assertEqual(system.desktop_exec(["/usr/bin/python3", "-m", "claude_usage_widget"]),
                         "/usr/bin/python3 -m claude_usage_widget")
        self.assertEqual(system.desktop_exec(["/home/a b/py", "50%"]), '"/home/a b/py" 50%%')
        self.assertEqual(system.desktop_exec(["it's", '$X"', "a\\b"]),
                         '"it\'s" "\\\\$X\\\\"" "a\\\\\\\\b"')  # file text: "it's" "\\$X\\"" "a\\\\b"

    def test_save_retries_while_windows_reader_has_file_open(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "rate_limits.json"
            real_replace = os.replace
            calls = []

            def flaky(src, dst):
                calls.append(1)
                if len(calls) < 3:
                    raise PermissionError("in use")
                real_replace(src, dst)
            with mock.patch.object(paths, "IS_WINDOWS", True), mock.patch.object(paths.os, "replace", flaky):
                paths.save_json(target, {"ok": 1})
            self.assertEqual(paths.load_json(target), {"ok": 1})
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["rate_limits.json"])

    def test_lib_check_uses_loader(self):
        from unittest import mock
        installer = load_installer()
        real_exists = os.path.exists
        not_nixos = lambda p: False if p == "/etc/NIXOS" else real_exists(p)  # noqa: E731
        with mock.patch("ctypes.CDLL", side_effect=OSError), mock.patch("os.path.exists", not_nixos), \
                mock.patch("os.path.isdir", lambda p: False):
            # a minimal system missing every library must still be warned about
            self.assertEqual(installer.missing_linux_libs(), list(installer.LINUX_QT_LIBS.values()))
        with mock.patch("ctypes.CDLL", side_effect=OSError), \
                mock.patch("os.path.exists", lambda p: p == "/etc/NIXOS" or real_exists(p)):
            self.assertIsNone(installer.missing_linux_libs())  # NixOS: can't tell
        def only_cursor_missing(name):
            if name == "libxcb-cursor.so.0":
                raise OSError(name)
        with mock.patch("ctypes.CDLL", side_effect=only_cursor_missing), mock.patch("os.path.exists", not_nixos), \
                mock.patch("os.path.isdir", lambda p: False):
            self.assertEqual(installer.missing_linux_libs(), ["libxcb-cursor0"])

    def test_store_python_detected(self):
        installer = load_installer()
        self.assertTrue(installer.is_store_python(
            r"C:\Users\a\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0"
            r"\python.exe"))
        self.assertTrue(installer.is_store_python(
            r"C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.13_3.13.1_x64__qbz5n2kfra8p0"))
        self.assertFalse(installer.is_store_python(r"C:\Program Files\Python313\python.exe"))
        self.assertFalse(installer.is_store_python(r"C:\Users\a\AppData\Local\Programs\Python\Python313\python.exe"))


class StatuslineHookTests(unittest.TestCase):
    """Runs the hook the way Claude Code does: a separate process, UTF-8 bytes on stdin and stdout."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = dict(os.environ, CLAUDE_USAGE_WIDGET_HOME=str(self.home), PYTHONPATH=str(ROOT / "src"),
                        PYTHONIOENCODING="cp1252", PYTHONUTF8="0")  # a Windows ANSI code page

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, payload, chain=None):
        if chain:
            paths.save_json(self.home / "config.json", {"chain_statusline": chain})
        r = subprocess.run([sys.executable, "-m", "claude_usage_widget.statusline"], env=self.env,
                           input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                           capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        return r.stdout

    def test_utf8_in_and_out_regardless_of_code_page(self):
        out = self.hook({"model": {"display_name": "Opus 5.5"}, "cwd": "/home/Ёлка/проект",
                         "rate_limits": {"five_hour": {"used_percentage": 31, "resets_at": 4102444800}}})
        self.assertEqual(out, "Opus 5.5 · 5h 31%\n".encode("utf-8"))
        saved = paths.load_json(self.home / "rate_limits.json")
        self.assertEqual(saved["rate_limits"]["five_hour"]["used_percentage"], 31)

    def test_chained_command_runs_in_bash(self):
        if statusline.find_bash() is None:
            self.skipTest("no bash on this machine")
        # [[ ]] is bash-only (fails in dash and cmd.exe); \xe2\x9c\x93 is a UTF-8 check mark
        out = self.hook({"model": {"display_name": "Opus 5.5"}},
                        chain=r"""[[ "$(cat)" == *Opus* ]] && printf 'mine \xe2\x9c\x93'""")
        self.assertEqual(out, "mine ✓".encode("utf-8"))

    def test_failing_chained_command_falls_back_to_default_line(self):
        out = self.hook({"model": {"display_name": "Opus 5.5"}}, chain="exit 3")
        self.assertEqual(out, "Opus 5.5\n".encode("utf-8"))


if __name__ == "__main__":
    unittest.main()

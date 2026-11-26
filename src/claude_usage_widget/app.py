"""The Qt widget, tray icon and single-instance handling."""
import os
import sys
import time
from datetime import datetime

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QColor, QFont, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from . import paths, system, usage
from .paths import IS_LINUX, IS_MAC, IS_WINDOWS
from .usage import LIMITS, fmt_dur, fmt_tokens, fmt_usd

REFRESH_MS = 2000
MAX_MODELS = 4
DEFAULT_OPACITY = 0.62
SOCKET_NAME = "claude-usage-widget-" + (os.environ.get("USER") or os.environ.get("USERNAME") or "user")

BG = QColor(20, 23, 28)
FG = QColor(235, 237, 242)
DIM = QColor(148, 156, 168)
ACCENT = QColor(217, 120, 87)
IDLE_DOT = QColor(89, 94, 105)
STATUS = {  # soft palette shared with the GNOME extension
    "ok": QColor(74, 212, 158),     # mint
    "warn": QColor(250, 199, 84),   # amber
    "high": QColor(247, 112, 120),  # rose
    None: DIM,
}


def status_color(pct):
    return STATUS[usage.status_level(pct)]


def font(px, bold=False):
    f = QFont()
    f.setPixelSize(px)
    f.setBold(bold)
    return f


# ---------- tray icon ----------

TRAY_SIZES = (16, 20, 22, 24, 32, 48, 64)


def tray_pixmap(limits, size=64):
    """Square tray icon: two stacked number pills, 5-hour on top and weekly below.

    Same style as the GNOME top-bar pills: dark glass, colored border, colored number.
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    gap = max(1.0, size * 0.06)
    ph = (size - gap) / 2
    small = size <= 24
    border = 1.0 if small else size * 0.045
    for i, (key, _s, _n) in enumerate(LIMITS):
        pct, _reset = limits.get(key, (None, None))
        c = status_color(pct)
        rect = QRectF(border / 2, i * (ph + gap) + border / 2, size - border, ph - border)
        pill = QPainterPath()
        pill.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        fill = QColor(c.red() // 5 + 14, c.green() // 5 + 16, c.blue() // 5 + 20, 240)
        if pct is not None and pct >= 95:  # ⚠ doesn't fit; a brighter fill flags it instead
            fill = QColor(c.red() // 3 + 10, c.green() // 3 + 10, c.blue() // 3 + 12, 250)
        p.fillPath(pill, fill)
        p.setPen(QPen(c, border))
        p.drawPath(pill)
        text = "–" if pct is None else str(min(999, int(round(pct))))
        f = font(max(6, int(rect.height() * (0.95 if small else 0.8))), bold=True)
        p.setFont(f)
        room = rect.width() - rect.height() * (0.2 if small else 0.45)
        w = p.fontMetrics().horizontalAdvance(text)
        if w > room:
            f.setPixelSize(max(5, int(f.pixelSize() * room / w)))
            p.setFont(f)
        p.setPen(QColor(min(255, c.red() + 40), min(255, c.green() + 40), min(255, c.blue() + 40)))
        p.drawText(rect, Qt.AlignCenter, text)
    p.end()
    return pm


def tray_icon(limits):
    """Icon with a pixmap drawn for each common tray size, so the numbers stay sharp."""
    icon = QIcon()
    for s in TRAY_SIZES:
        icon.addPixmap(tray_pixmap(limits, s))
    return icon


# ---------- widget ----------

class Widget(QWidget):
    W = 236

    def __init__(self, app, demo=False):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.app = app
        self.demo = demo
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        if IS_MAC:
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setWindowTitle("Claude Usage")
        self.conf = paths.load_json(paths.config_file())
        self.tracker = usage.Tracker()
        self.notifier = usage.Notifier(self._notify)
        self.models = []
        self.limits = {}
        self.ext_active = False
        self.setFixedSize(self.W, self.calc_h())

        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self)
            self.tray.setContextMenu(self.build_menu(tray=True))
            self.tray.activated.connect(self._tray_activated)
            self.tray.setIcon(tray_icon({}))
            self.tray.show()

        self._save_timer = QTimer(self, singleShot=True, interval=600, timeout=self._save_conf)
        self.tick()
        if not demo:
            QTimer(self, interval=REFRESH_MS, timeout=self.tick).start()
            QTimer(self, interval=30000, timeout=self._sync_gnome).start()
            self._sync_gnome()

    # ----- config -----
    def _save_conf(self):
        try:
            paths.save_json(paths.config_file(), {**paths.load_json(paths.config_file()), **self.conf})
        except Exception:
            pass

    def opacity(self):
        return float(self.conf.get("opacity", DEFAULT_OPACITY))

    # ----- show / hide -----
    def default_pos(self):
        g = QApplication.primaryScreen().availableGeometry()
        return QPoint(g.right() - self.W - 20, g.top() + 20)

    def place(self):
        x, y = self.conf.get("x"), self.conf.get("y")
        pos = QPoint(x, y) if x is not None and y is not None else self.default_pos()
        # keep it on a visible screen (monitor layouts change)
        if not any(s.availableGeometry().contains(pos) for s in QApplication.screens()):
            pos = self.default_pos()
        self.move(pos)

    def restore(self):
        self.place()
        if IS_LINUX:
            system.x11_make_sticky(int(self.winId()))
        self.show()
        self.raise_()
        if IS_MAC:
            system.mac_all_spaces(int(self.winId()))
        self.conf["hidden"] = False
        self._save_timer.start()
        self._update_menu_labels()

    def minimize(self):
        self.hide()
        self.conf["hidden"] = True
        self._save_timer.start()
        self._update_menu_labels()

    def toggle(self):
        if self.isVisible():
            self.minimize()
        else:
            self.restore()

    def can_hide(self):
        """Hiding is only safe if there is a way back (tray icon or GNOME extension)."""
        return self.tray is not None or self.ext_active

    # ----- menu -----
    def build_menu(self, tray=False):
        m = QMenu()
        act = m.addAction("Hide widget")
        act.triggered.connect(self.toggle)
        if tray:
            self._toggle_act = act
            m.addSeparator()
            self._info_acts = {}
            for key, _s, name in LIMITS:
                a = m.addAction(f"{name}: –")
                a.setEnabled(False)
                self._info_acts[key] = a
            self._cost_act = m.addAction("Today: –")
            self._cost_act.setEnabled(False)
        m.addSeparator()
        op = m.addMenu("Opacity")
        grp = QActionGroup(op)
        for val in (0.35, 0.5, 0.62, 0.8, 0.95):
            a = op.addAction(f"{int(val * 100)}%")
            a.setCheckable(True)
            a.setChecked(abs(self.opacity() - val) < 0.01)
            a.triggered.connect(lambda _=False, v=val: self.set_opacity(v))
            grp.addAction(a)
        start = m.addAction("Start at login")
        start.setCheckable(True)
        start.setChecked(system.autostart_enabled())
        start.toggled.connect(system.set_autostart)
        m.addAction("Reset position").triggered.connect(self.reset_pos)
        m.addAction("Test notification").triggered.connect(
            lambda: self._notify("Claude 5-hour limit at 80%", "This is a test notification", False))
        m.addSeparator()
        m.addAction("Quit").triggered.connect(self.app.quit)
        return m

    def set_opacity(self, v):
        self.conf["opacity"] = v
        self._save_timer.start()
        self.update()

    def reset_pos(self):
        self.conf.pop("x", None)
        self.conf.pop("y", None)
        self._save_timer.start()
        self.move(self.default_pos())

    def _update_menu_labels(self):
        if not self.tray:
            return
        self._toggle_act.setText("Hide widget" if self.isVisible() else "Show widget")

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.MiddleClick) and not IS_MAC:
            self.toggle()

    # ----- notifications -----
    def _notify(self, title, body, urgent):
        def fallback(t, b):
            if self.tray:
                self.tray.showMessage(t, b, QSystemTrayIcon.Warning if urgent else QSystemTrayIcon.Information)
        system.notify(title, body, urgent, fallback=fallback)

    def _sync_gnome(self):
        active = system.gnome_extension_active()
        if active != self.ext_active:
            self.ext_active = active
            if self.tray:
                self.tray.setVisible(not active)  # the extension shows richer top-bar pills

    # ----- data -----
    def tick(self):
        if self.demo:
            from .demo import demo_data
            self.limits, self.models = demo_data()
        else:
            try:
                self.tracker.scan()
                self.models = self.tracker.per_model_today()
                self.limits = usage.load_limits()
                self.notifier.check(self.limits)
            except Exception as e:  # never die on bad data
                print("update error:", e, file=sys.stderr)
        h = self.calc_h()
        if h != self.height():
            self.setFixedSize(self.W, h)
        self._update_tray()
        self.update()

    def _update_tray(self):
        if not self.tray:
            return
        self.tray.setIcon(tray_icon(self.limits))
        now = time.time()
        lines = []
        for key, short, name in LIMITS:
            if key in self.limits:
                pct, reset = self.limits[key]
                warn = "⚠ " if pct >= 95 else ""
                txt = f"{warn}{name}: {pct:.0f}%" + (f" · resets in {fmt_dur(reset - now)}" if reset else "")
            else:
                txt = f"{name}: waiting for Claude Code"
            self._info_acts[key].setText(txt)
            lines.append(txt)
        cost = sum(r["cost"] for r in self.models)
        self._cost_act.setText(f"Today: ≈ {fmt_usd(cost)} at API prices")
        lines.append(f"Today ≈ {fmt_usd(cost)}")
        self.tray.setToolTip("Claude usage\n" + "\n".join(lines))

    # ----- input -----
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            if ev.position().x() > self.W - 30 and ev.position().y() < 30:
                if self.can_hide():
                    self.minimize()
                else:
                    self.showMinimized()
                return
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
        elif ev.button() == Qt.RightButton:
            self.build_menu().exec(ev.globalPosition().toPoint())

    def moveEvent(self, ev):
        if self.isVisible():
            self.conf["x"], self.conf["y"] = self.x(), self.y()
            self._save_timer.start()

    # ----- drawing -----
    def calc_h(self):
        rows = max(1, min(MAX_MODELS, len(self.models)))
        return 118 + rows * 18

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        self.draw(p)
        p.end()

    @staticmethod
    def _text(p, x, y, s, px, color, bold=False, right=False):
        p.setFont(font(px, bold))
        p.setPen(color)
        if right:
            x -= p.fontMetrics().horizontalAdvance(s)
        p.drawText(int(round(x)), int(round(y)), s)

    def draw(self, p):
        W, H, P = self.W, self.height(), 12
        bw = W - 2 * P
        now = time.time()

        bg = QPainterPath()
        bg.addRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 11, 11)
        c = QColor(BG)
        c.setAlphaF(self.opacity())
        p.fillPath(bg, c)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.drawPath(bg)

        # header
        live = any(now - r["last"] < usage.LIVE_S for r in self.models)
        p.setPen(Qt.NoPen)
        p.setBrush(ACCENT if live else DIM)
        p.drawEllipse(QRectF(P, 13.5, 7, 7))
        self._text(p, P + 12, 21, "Claude usage", 11, DIM, bold=True)
        self._text(p, W - P - 22, 21, datetime.now().strftime("%H:%M"), 11, DIM, right=True)
        btn = QPainterPath()
        btn.addRoundedRect(QRectF(W - P - 14, 9, 16, 16), 4, 4)
        p.fillPath(btn, QColor(255, 255, 255, 18))
        p.setPen(QPen(FG, 1.6))
        p.drawLine(QPoint(W - P - 10, 17), QPoint(W - P - 2, 17))

        # limits
        y = 42
        for key, _short, label in LIMITS:
            self._text(p, P, y, label, 11, FG, bold=True)
            if key in self.limits:
                pct, reset = self.limits[key]
                col = status_color(pct)
                warn = "⚠ " if pct >= 95 else ""
                self._text(p, P + 54, y, f"{warn}{pct:.0f}%", 11, col, bold=True)
                if reset:
                    self._text(p, W - P, y, f"resets {fmt_dur(reset - now)}", 10, DIM, right=True)
            else:
                pct, col = 0, DIM
                self._text(p, W - P, y, "waiting for Claude Code", 10, DIM, right=True)
            track = QPainterPath()
            track.addRoundedRect(QRectF(P, y + 5, bw, 6), 3, 3)
            p.fillPath(track, QColor(255, 255, 255, 20))
            fw = bw * min(100.0, max(0.0, pct)) / 100.0
            if fw > 0:
                bar = QPainterPath()
                bar.addRoundedRect(QRectF(P, y + 5, max(6.0, fw), 6), 3, 3)
                p.fillPath(bar, col)
            y += 28

        # today
        p.fillRect(QRectF(P, y - 8, bw, 1), QColor(255, 255, 255, 20))
        cost = sum(r["cost"] for r in self.models)
        approx = "≈ " if all(r["priced"] for r in self.models) else "≥ "
        self._text(p, P, y + 8, "Today", 11, FG, bold=True)
        self._text(p, P + 42, y + 8, approx + fmt_usd(cost), 13, ACCENT, bold=True)
        self._text(p, W - P, y + 8, "tokens · cost", 9, DIM, right=True)
        y += 26
        if not self.models:
            self._text(p, P, y, "no usage yet today", 11, DIM)
        for r in self.models[:MAX_MODELS]:
            is_live = now - r["last"] < usage.LIVE_S
            p.setPen(Qt.NoPen)
            p.setBrush(ACCENT if is_live else IDLE_DOT)
            p.drawEllipse(QRectF(P, y - 7, 6, 6))
            self._text(p, P + 12, y, r["name"], 11, FG, bold=is_live)
            self._text(p, W - P - 50, y, fmt_tokens(r["tokens"]), 11, FG, bold=True, right=True)
            self._text(p, W - P, y, fmt_usd(r["cost"]) if r["priced"] else "n/a", 11, DIM, right=True)
            y += 18


# ---------- single instance ----------

def send_to_running(msg):
    """Send a command to an already-running widget. Returns True if one answered."""
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if not sock.waitForConnected(500):
        return False
    sock.write(msg.encode())
    sock.flush()
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True


def run(args):
    if IS_LINUX and os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY") \
            and "QT_QPA_PLATFORM" not in os.environ:
        # Wayland doesn't let apps keep windows on top; XWayland (X11) does.
        os.environ["QT_QPA_PLATFORM"] = "xcb"

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Claude Usage Widget")
    app.setQuitOnLastWindowClosed(False)

    cmd = "toggle" if args.toggle else "quit" if args.quit else "show"
    if send_to_running(cmd):
        return 0
    if args.quit:
        return 0

    QLocalServer.removeServer(SOCKET_NAME)  # clean up after a crash
    server = QLocalServer()
    server.listen(SOCKET_NAME)
    system.mac_accessory_app()
    w = Widget(app)

    def on_conn():
        conn = server.nextPendingConnection()

        def handle():
            msg = bytes(conn.readAll()).decode(errors="ignore").strip()
            if msg == "toggle":
                w.toggle()
            elif msg == "quit":
                app.quit()
            else:
                w.restore()
        conn.readyRead.connect(handle)
    server.newConnection.connect(on_conn)

    if w.conf.get("hidden") and w.can_hide() and not args.toggle:
        w.minimize()
    else:
        w.restore()
    return app.exec()


def screenshot(out, demo=True):
    """Render the widget and tray icon to PNG files (works headless with QT_QPA_PLATFORM=offscreen)."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    w = Widget(app, demo=demo)
    pm = QPixmap(w.size() * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    w.draw(p)
    p.end()
    pm.save(out)
    base, ext = os.path.splitext(out)
    tray_pixmap(w.limits, 64).save(base + "-tray" + ext)
    print("wrote", out, "and", base + "-tray" + ext)
    return 0

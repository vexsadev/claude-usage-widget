"""macOS menu-bar item showing the limits as two long colored pills, like the GNOME top bar.

Qt's QSystemTrayIcon gives a picture icon a square menu-bar slot on macOS and shrinks anything
wider to fit, so on macOS we create our own variable-width NSStatusItem with pyobjc (a dependency
on macOS) and draw the pills with Qt.

Its menu is a native NSMenu that mirrors the widget's QMenu, rebuilt just before it opens, so macOS
opens and places it like any other menu-bar menu. Each native item triggers its QAction.

The class offers the parts of the QSystemTrayIcon interface the widget uses: setToolTip,
setVisible, show, showMessage, plus set_limits.
"""
import time

from PySide6.QtCore import QBuffer, QByteArray, QIODevice

from . import usage
from .app import pill_strip_pixmap

_BRIDGE_CLASS = None


def _bridge_class():
    """NSMenu delegate and menu-item target that calls back into Python (defined once per process)."""
    global _BRIDGE_CLASS
    if _BRIDGE_CLASS is None:
        import objc
        from Foundation import NSObject

        class ClaudeUsageMenuBridge(NSObject, protocols=[objc.protocolNamed("NSMenuDelegate")]):
            def menuNeedsUpdate_(self, nsmenu):  # called by macOS right before the menu opens
                self.owner.refresh_menu()

            def activate_(self, item):  # target/action of every native item
                self.owner.trigger(item.tag())

        _BRIDGE_CLASS = ClaudeUsageMenuBridge
    return _BRIDGE_CLASS


def create(menu):
    """The menu-bar pills, or None if pyobjc or the status bar isn't available (falls back to Qt)."""
    try:
        return MenuBarPills(menu)
    except Exception:
        return None


class MenuBarPills:
    PILL_HEIGHT = 18  # points; the menu bar is 22-24 points (37 on notched MacBooks)

    def __init__(self, menu):
        from AppKit import NSMenu, NSStatusBar, NSVariableStatusItemLength
        self.menu = menu
        self.bar = NSStatusBar.systemStatusBar()
        self.item = self.bar.statusItemWithLength_(NSVariableStatusItemLength)
        self.button = self.item.button()
        self.bridge = _bridge_class().alloc().init()  # NSMenu holds its delegate weakly: keep it here
        self.bridge.owner = self
        self.nsmenu = NSMenu.alloc().initWithTitle_("Claude usage")
        self.nsmenu.setDelegate_(self.bridge)
        self._actions = {}
        self.refresh_menu()
        self.item.setMenu_(self.nsmenu)  # a click opens it below the pills, natively
        self._labels = None
        self.set_limits({})

    # ----- the pills -----

    def set_limits(self, limits):
        now = time.time()
        labels = tuple(usage.pill_text(*limits.get(key, (None, None)), short, now)
                       for key, short, _name in usage.LIMITS)
        if labels == self._labels:  # countdowns change once a minute; don't redraw every tick
            return
        self._labels = labels
        height = min(self.PILL_HEIGHT, self.bar.thickness() - 4)
        self.button.setImage_(self._ns_image(pill_strip_pixmap(limits, now, height, dpr=2.0)))
        self.button.setAccessibilityLabel_("Claude usage: " + ", ".join(labels))

    @staticmethod
    def _ns_image(pm):
        from AppKit import NSImage
        from Foundation import NSData
        buf = QByteArray()
        dev = QBuffer(buf)
        dev.open(QIODevice.WriteOnly)
        pm.save(dev, "PNG")
        dev.close()
        raw = bytes(buf.data())
        img = NSImage.alloc().initWithData_(NSData.dataWithBytes_length_(raw, len(raw)))
        dpr = pm.devicePixelRatio()
        img.setSize_((pm.width() / dpr, pm.height() / dpr))  # in points, so it stays sharp on Retina
        return img

    # ----- the native menu, mirroring the QMenu -----

    def refresh_menu(self):
        self._actions = {}
        self._fill(self.nsmenu, self.menu)

    def _fill(self, nsmenu, qmenu):
        from AppKit import NSMenu, NSMenuItem
        nsmenu.setAutoenablesItems_(False)
        nsmenu.removeAllItems()
        for act in qmenu.actions():
            if not act.isVisible():
                continue
            if act.isSeparator():
                nsmenu.addItem_(NSMenuItem.separatorItem())
                continue
            title = act.text().replace("&&", "\0").replace("&", "").replace("\0", "&")  # Qt mnemonics
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, "")
            it.setEnabled_(act.isEnabled())
            sub = act.menu()
            if sub is not None:
                subns = NSMenu.alloc().initWithTitle_(title)
                self._fill(subns, sub)
                it.setSubmenu_(subns)
            else:
                tag = len(self._actions) + 1
                self._actions[tag] = act
                it.setTag_(tag)
                it.setTarget_(self.bridge)
                it.setAction_("activate:")
                if act.isCheckable():
                    it.setState_(1 if act.isChecked() else 0)  # NSControlStateValueOn / Off
            nsmenu.addItem_(it)

    def trigger(self, tag):
        act = self._actions.get(tag)
        if act is not None and act.isEnabled():
            act.trigger()

    # ----- the QSystemTrayIcon methods the widget calls -----

    def setToolTip(self, text):
        self.button.setToolTip_(text)

    def setVisible(self, visible):
        self.item.setVisible_(bool(visible))

    def show(self):
        self.setVisible(True)

    def showMessage(self, *_args):
        pass  # notifications on macOS go through system.notify (osascript)

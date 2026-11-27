"""macOS menu-bar item showing the limits as two long colored pills, like the GNOME top bar.

Qt's QSystemTrayIcon gives a picture icon a square menu-bar slot on macOS and shrinks anything
wider to fit, so on macOS we create our own variable-width NSStatusItem with pyobjc (a dependency
on macOS) and draw the pills with Qt. It offers the parts of the QSystemTrayIcon interface the
widget uses: setToolTip, setVisible, show, showMessage, plus set_limits.
"""
import time

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPoint

from . import usage
from .app import pill_strip_pixmap

_TARGET_CLASS = None


def _target_class():
    """An Objective-C object whose clicked: action calls back into Python (defined once per process)."""
    global _TARGET_CLASS
    if _TARGET_CLASS is None:
        from Foundation import NSObject

        class ClaudeUsageMenuBarTarget(NSObject):
            def clicked_(self, _sender):
                self.callback()

        _TARGET_CLASS = ClaudeUsageMenuBarTarget
    return _TARGET_CLASS


def create(menu):
    """The menu-bar pills, or None if pyobjc or the status bar isn't available (falls back to Qt)."""
    try:
        return MenuBarPills(menu)
    except Exception:
        return None


class MenuBarPills:
    PILL_HEIGHT = 18  # points; the menu bar is 22-24 points (37 on notched MacBooks)

    def __init__(self, menu):
        from AppKit import (NSEventMaskLeftMouseUp, NSEventMaskRightMouseUp, NSStatusBar,
                            NSVariableStatusItemLength)
        self.menu = menu
        self.bar = NSStatusBar.systemStatusBar()
        self.item = self.bar.statusItemWithLength_(NSVariableStatusItemLength)
        self.button = self.item.button()
        self._target = _target_class().alloc().init()  # the button only holds a weak reference
        self._target.callback = self._clicked
        self.button.setTarget_(self._target)
        self.button.setAction_("clicked:")
        self.button.sendActionOn_(NSEventMaskLeftMouseUp | NSEventMaskRightMouseUp)
        self._labels = None
        self.set_limits({})

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

    def _clicked(self):
        """Open the widget's menu just below the pills, like a native menu-bar menu."""
        from AppKit import NSScreen
        frame = self.button.window().frame()
        primary_h = NSScreen.screens()[0].frame().size.height  # Cocoa's y axis points up from here
        self.menu.popup(QPoint(int(frame.origin.x), int(primary_h - frame.origin.y)))

    # ----- the QSystemTrayIcon methods the widget calls -----

    def setToolTip(self, text):
        self.button.setToolTip_(text)

    def setVisible(self, visible):
        self.item.setVisible_(bool(visible))

    def show(self):
        self.setVisible(True)

    def showMessage(self, *_args):
        pass  # notifications on macOS go through system.notify (osascript)

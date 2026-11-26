"""Regenerate the README images in docs/ from the real widget drawing code.

    pip install -e . pillow
    QT_QPA_PLATFORM=offscreen python docs/make_media.py     # Windows: QT_QPA_PLATFORM=windows

Writes docs/widget.png, docs/demo.gif and docs/tray.png. (banner.svg and pills.svg are hand-written.)
"""
import io
import math
import os
import sys
import time

from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication

from claude_usage_widget import app as wapp
from claude_usage_widget.demo import demo_data

DOCS = os.path.dirname(os.path.abspath(__file__))
SCALE = 2
MARGIN = 28


def backdrop(p, w, h):
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor(36, 52, 82))
    g.setColorAt(1, QColor(92, 46, 78))
    p.fillRect(QRectF(0, 0, w, h), g)


def render(widget):
    """Widget drawn on the gradient backdrop, as a Pillow RGB image."""
    w, h = widget.W + 2 * MARGIN, widget.calc_h() + 2 * MARGIN
    widget.setFixedSize(widget.W, widget.calc_h())
    img = QImage(w * SCALE, h * SCALE, QImage.Format_ARGB32)
    img.setDevicePixelRatio(SCALE)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    backdrop(p, w, h)
    p.translate(MARGIN, MARGIN)
    widget.draw(p)
    p.end()
    return to_pil(img)


def to_pil(img):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(ba))).convert("RGB")


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def models(now, k):
    """Model rows that grow with k (0..1)."""
    return [
        {"name": "Opus 5.5", "tokens": int(6e6 + 14e6 * k), "cost": 3.1 + 7.2 * k, "last": now, "priced": True},
        {"name": "Sonnet 5.5", "tokens": int(2.4e6 + 0.9e6 * k), "cost": 0.92 + 0.3 * k,
         "last": now - 3600, "priced": True},
        {"name": "Haiku 5.5", "tokens": 640_000, "cost": 0.03, "last": now - 7200, "priced": True},
    ]


def demo_gif(widget):
    now = time.time()
    frames, durations, held = [], [], set()
    n = 70
    for i in range(n + 1):
        k = ease(i / n)
        five = round(18 + (97 - 18) * k)  # Claude Code reports whole percentages
        week = round(46 + (84 - 46) * k)
        widget.limits = {"five_hour": (five, now + 4 * 3600 + 40 * 60 - 3 * 3600 * k),
                         "seven_day": (week, now + 2 * 86400 + 6 * 3600 - 3600 * k)}
        widget.models = models(now, k)
        frames.append(render(widget))
        # linger near the color changes and at the end
        hold = five >= 80 and five // 5 not in held  # pause once at 80, 85, 90, 95
        if hold:
            held.add(five // 5)
        durations.append(2200 if i == n else 450 if hold else 55)
    # one shared palette keeps the gradient smooth and the file small
    picks = frames[::10] + [frames[-1]]
    w, h = frames[0].size
    sheet = Image.new("RGB", (w, h * len(picks)))
    for i, f in enumerate(picks):
        sheet.paste(f, (0, i * h))
    pal = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    out = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    path = os.path.join(DOCS, "demo.gif")
    out[0].save(path, save_all=True, append_images=out[1:], duration=durations, loop=0, optimize=True)
    print("wrote", path, f"{os.path.getsize(path) // 1024} KB")


def tray_strip():
    """Tray icons at three levels on a dark top-bar strip, with captions."""
    states = [((34, 21), "under 80%"), ((86, 58), "80% and up"), ((93, 91), "90% and up")]
    cell, icon, h = 150, 64, 132
    w = cell * len(states)
    img = QImage(w * SCALE, h * SCALE, QImage.Format_ARGB32)
    img.setDevicePixelRatio(SCALE)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(0, 0, w, h), 16, 16)
    p.fillPath(bg, QColor(22, 24, 30))
    for i, ((a, b), caption) in enumerate(states):
        limits = {"five_hour": (a, None), "seven_day": (b, None)}
        pm = wapp.tray_pixmap(limits, icon * SCALE)
        pm.setDevicePixelRatio(SCALE)
        x = i * cell + (cell - icon) / 2
        p.drawPixmap(int(x), 18, pm)
        p.setFont(wapp.font(13, bold=True))
        p.setPen(wapp.status_color(a))
        p.drawText(QRectF(i * cell, 92, cell, 22), Qt.AlignCenter, caption)
    p.end()
    path = os.path.join(DOCS, "tray.png")
    img.save(path)
    print("wrote", path)


def main():
    QApplication.instance() or QApplication(sys.argv[:1])
    widget = wapp.Widget(QApplication.instance(), demo=True)
    widget.conf = {"opacity": 0.86}
    if widget.tray:
        widget.tray.hide()
    widget.limits, widget.models = demo_data()
    still = render(widget)
    still.save(os.path.join(DOCS, "widget.png"))
    print("wrote", os.path.join(DOCS, "widget.png"))
    demo_gif(widget)
    tray_strip()


if __name__ == "__main__":
    main()

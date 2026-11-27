---
name: regen-media
description: Regenerate the README images in docs/ (widget.png, demo.gif, tray.png, menubar.png, how-it-works.svg) after changing how the widget or tray icon is drawn.
---

# Regenerate README media

1. Make sure the package and Pillow are installed in the active env: `pip install -e . pillow`.
2. Render:
   ```bash
   QT_QPA_PLATFORM=offscreen python docs/make_media.py   # widget.png, demo.gif, tray.png, menubar.png
   python docs/make_diagram.py docs/how-it-works.svg     # animated data-flow diagram
   ```
   `banner.svg` and `pills.svg` are hand-written — edit them directly if colors or text changed.
3. Look at every regenerated image with the Read tool before reporting success (fonts missing in
   offscreen mode show up as empty boxes).
4. Check `git diff --stat docs/` — only the files you meant to change should differ.

"""Generate docs/how-it-works.svg, the animated data-flow diagram in the README.

    python docs/make_diagram.py docs/how-it-works.svg
"""
import sys
MINT, AMBER, ROSE, ACC, DIM = "#4ad49e", "#fac754", "#f77078", "#d97857", "#949ca8"
CYCLE = "5s"
out = []
a = out.append

def node(x, y, w, h, title, sub, accent, flash=None, extra=""):
    a(f'<g transform="translate({x} {y})">')
    a(f'  <rect width="{w}" height="{h}" rx="14" fill="#151a23" stroke="#ffffff" stroke-opacity="0.13"/>')
    if flash:  # border lights up when data arrives: flash = (start, end) fractions of the cycle
        s, e = flash
        a(f'  <rect width="{w}" height="{h}" rx="14" fill="none" stroke="{accent}" stroke-width="2" opacity="0">')
        a(f'    <animate attributeName="opacity" values="0;0;1;0;0" keyTimes="0;{s};{s+0.03:.2f};{e};1" dur="{CYCLE}" repeatCount="indefinite"/>')
        a('  </rect>')
    a(f'  <rect x="0" y="16" width="4" height="{h-32}" rx="2" fill="{accent}"/>')
    a(f'  <text x="20" y="32" class="t">{title}</text>')
    for i, line in enumerate(sub):
        a(f'  <text x="20" y="{54 + i*18}" class="s">{line}</text>')
    a(extra)
    a('</g>')

def edge(pid, d, color):
    a(f'<path id="{pid}" d="{d}" fill="none" stroke="#ffffff" stroke-opacity="0.16" stroke-width="2"/>')
    a(f'<path d="{d}" fill="none" stroke="{color}" stroke-opacity="0.45" stroke-width="2" stroke-dasharray="5 9">')
    a(f'  <animate attributeName="stroke-dashoffset" values="28;0" dur="1.2s" repeatCount="indefinite"/>')
    a('</path>')

def dot(pid, color, s, e):
    """A data packet that travels path pid between cycle fractions s..e."""
    a(f'<circle r="5.5" fill="{color}" opacity="0">')
    a(f'  <animateMotion dur="{CYCLE}" repeatCount="indefinite" calcMode="linear" keyPoints="0;0;1;1" keyTimes="0;{s};{e};1"><mpath href="#{pid}"/></animateMotion>')
    a(f'  <animate attributeName="opacity" calcMode="discrete" values="0;1;0" keyTimes="0;{s};{e}" dur="{CYCLE}" repeatCount="indefinite"/>')
    a('</circle>')
    a(f'<circle r="11" fill="{color}" opacity="0">')
    a(f'  <animateMotion dur="{CYCLE}" repeatCount="indefinite" calcMode="linear" keyPoints="0;0;1;1" keyTimes="0;{s};{e};1"><mpath href="#{pid}"/></animateMotion>')
    a(f'  <animate attributeName="opacity" calcMode="discrete" values="0;0.22;0" keyTimes="0;{s};{e}" dur="{CYCLE}" repeatCount="indefinite"/>')
    a('</circle>')

def label(x, y, text, anchor="middle"):
    a(f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="e">{text}</text>')

W, H = 1200, 500
a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
  'aria-label="How it works: Claude Code sends plan limits to the status line hook, which saves rate_limits.json; '
  'the widget, tray icon, top-bar pills and alerts read it. Claude Code also writes session logs, which the widget reads for tokens and cost.">')
a('''<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#161d2e"/><stop offset="0.6" stop-color="#1d1a2e"/><stop offset="1" stop-color="#2b1a2c"/>
  </linearGradient>
  <style>
    text { font-family: "Segoe UI", Ubuntu, Cantarell, "Noto Sans", "Helvetica Neue", Arial, sans-serif; }
    .t { font-size: 17px; font-weight: 700; fill: #eceef2; }
    .s { font-size: 13px; fill: #949ca8; }
    .m { font-family: ui-monospace, "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace; font-size: 12px; fill: #b7bdc9; }
    .e { font-size: 12.5px; font-weight: 700; fill: #b7bdc9; letter-spacing: .3px; }
    .h { font-size: 12px; font-weight: 800; fill: #6f7683; letter-spacing: 1.6px; }
  </style>
</defs>''')
a(f'<rect width="{W}" height="{H}" rx="24" fill="url(#bg)"/>')
# column headings
a('<text x="48" y="44" class="h">SOURCE</text><text x="320" y="44" class="h">CAPTURED</text>'
  '<text x="610" y="44" class="h">STORED LOCALLY</text><text x="930" y="44" class="h">SHOWN TO YOU</text>')

# edges first (under nodes)
edge("e1", "M238 228 C 282 228 280 118 320 118", MINT)
edge("e2", "M540 118 L 610 118", MINT)
edge("e3", "M238 268 C 282 268 280 378 320 378", ACC)
ys = [96, 196, 296, 386]
for i, y in enumerate(ys[:3]):
    edge(f"o{i}", f"M820 118 C 878 118 872 {y} 930 {y}", MINT)
edge("o3", "M820 118 C 890 118 860 372 930 372", MINT)
edge("e5", "M820 396 C 870 396 880 400 930 400", ACC)

label(268, 160, "after each turn", "end")
label(575, 106, "saves")
label(268, 330, "writes", "end")
label(820, 442, "widget reads new lines every 2 s", "end")

# nodes
cursor = ('<g transform="translate(20 66)"><rect width="150" height="22" rx="6" fill="#0b0e13"/>'
          '<text x="10" y="15" class="m">$ claude</text>'
          '<rect x="72" y="5" width="7" height="13" fill="#d97857"><animate attributeName="opacity" values="1;0;1" dur="1s" calcMode="discrete" keyTimes="0;0.5;1" repeatCount="indefinite"/></rect></g>')
node(48, 168, 190, 128, "Claude Code", ["your session"], ACC, extra=cursor)
node(320, 76, 220, 84, "Status line hook", ["gets JSON on stdin"], MINT, flash=(0.22, 0.42))
json_txt = '<text x="20" y="72" class="m">{"five_hour": 34, …}</text>'
node(610, 76, 210, 84, "rate_limits.json", ["% used + reset times"], MINT, flash=(0.38, 0.58), extra=json_txt)
node(320, 336, 500, 84, "Session logs", ["~/.claude/projects/**/*.jsonl  ·  tokens per model × API price = cost"], ACC,
     flash=(0.25, 0.45))

pill = (f'<g transform="translate(130 40)"><rect width="86" height="22" rx="11" fill="#26423a" stroke="{MINT}" stroke-opacity=".55"/>'
        f'<text x="43" y="15.5" text-anchor="middle" style="font-size:11px;font-weight:700;fill:#a3e8cb">34% 5h · 3h</text></g>')
tray = (f'<g transform="translate(166 12)"><rect width="46" height="21" rx="10.5" fill="#1e3a31" stroke="{MINT}" stroke-width="2"/>'
        f'<text x="23" y="15.5" text-anchor="middle" style="font-size:13px;font-weight:800;fill:#7ef0c2">34</text>'
        f'<rect y="25" width="46" height="21" rx="10.5" fill="#3d3520" stroke="{AMBER}" stroke-width="2"/>'
        f'<text x="23" y="40.5" text-anchor="middle" style="font-size:13px;font-weight:800;fill:#ffe08f">82</text></g>')
bell = (f'<g transform="translate(178 16)"><path d="M14 2 C 6 2 5 9 5 14 L 5 21 L 1 26 L 27 26 L 23 21 L 23 14 C 23 9 22 2 14 2 Z" fill="{AMBER}" fill-opacity=".9"/>'
        f'<circle cx="14" cy="30" r="3.5" fill="{AMBER}"/>'
        f'<animateTransform attributeName="transform" type="rotate" additive="sum" values="0 14 4;0 14 4;-14 14 4;12 14 4;-8 14 4;0 14 4;0 14 4" keyTimes="0;0.62;0.66;0.7;0.74;0.78;1" dur="{CYCLE}" repeatCount="indefinite"/></g>')
bars = (f'<g transform="translate(20 52)"><rect width="190" height="6" rx="3" fill="#fff" fill-opacity=".08"/>'
        f'<rect width="65" height="6" rx="3" fill="{MINT}"/>'
        f'<rect y="12" width="190" height="6" rx="3" fill="#fff" fill-opacity=".08"/><rect y="12" width="156" height="6" rx="3" fill="{AMBER}"/></g>')
node(930, 60, 230, 72, "Top-bar pills", ["GNOME, optional"], MINT, flash=(0.62, 0.8), extra=pill)
node(930, 160, 230, 72, "Tray icon", ["5h + weekly pills"], MINT, flash=(0.62, 0.8), extra=tray)
node(930, 260, 230, 72, "Desktop alerts", ["at 80% and 90%"], AMBER, flash=(0.62, 0.8), extra=bell)
node(930, 352, 230, 84, "Widget", [], MINT, flash=(0.62, 0.86), extra=bars)

# data packets (one 5 s cycle): limits path (mint) and logs path (orange)
dot("e1", MINT, 0.0, 0.22)
dot("e2", MINT, 0.24, 0.38)
for i in range(4):
    dot(f"o{i}", MINT, 0.42, 0.62)
dot("e3", ACC, 0.05, 0.25)
dot("e5", ACC, 0.45, 0.64)

a('<text x="600" y="476" text-anchor="middle" class="s">🔒 Everything stays on your computer  ·  no network requests  ·  no login or API keys read</text>')
a('</svg>')
open(sys.argv[1], "w").write("\n".join(out) + "\n")

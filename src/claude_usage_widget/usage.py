"""Usage data: transcript parsing, per-model totals, API-equivalent cost, plan limits.

Standard library only, so it is unit-testable without Qt.
"""
import glob
import json
import os
import time
from collections import deque
from datetime import datetime

from . import paths

RESCAN_S = 10           # look for new transcript files this often
KEEP_S = 26 * 3600      # keep events this long (enough for "today")
LIVE_S = 120            # a model counts as "live" if used this recently

# Claude API list prices, USD per million tokens: (input, output, cache read).
# Cache writes cost 1.25x input (5-minute TTL) or 2x input (1-hour TTL); fast mode is 2x.
# Longest prefix match wins. Update when Anthropic changes prices.
PRICES = {
    "claude-fable-5-2": (8.0, 40.0, 0.20), "claude-mythos-5-2": (8.0, 40.0, 0.20),
    "claude-fable-5-1": (10.0, 50.0, 0.25), "claude-mythos-5-1": (10.0, 50.0, 0.25),
    "claude-fable-5": (10.0, 50.0, 1.00), "claude-mythos-5": (10.0, 50.0, 1.00),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 0.50), "claude-opus-4-7": (5.0, 25.0, 0.50),
    "claude-opus-4-6": (5.0, 25.0, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10),
    "claude-sonnet-5": (2.0, 10.0, 0.20),
    "claude-sonnet-4-6": (3.0, 15.0, 0.30),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
}
HAIKU55_LONG = (0.50, 2.50, 0.05)  # Haiku 5.5 when the prompt is over 100K tokens

LIMITS = (("five_hour", "5h", "5-hour"), ("seven_day", "wk", "Weekly"))
THRESHOLDS = (80, 90)


# ---------- formatting ----------

def fmt_tokens(n):
    n = float(n)
    for unit, div in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(n) >= div:
            v = n / div
            return f"{v:.1f}{unit}" if v < 100 else f"{v:.0f}{unit}"
    return f"{int(n)}"


def fmt_usd(v):
    if v >= 100:
        return f"${v:.0f}"
    if v >= 10:
        return f"${v:.1f}"
    return f"${v:.2f}"


def fmt_dur(sec):
    sec = max(0, int(sec))
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def model_name(m):
    """claude-opus-5-5 -> 'Opus 5.5'; claude-haiku-4-5-20251001 -> 'Haiku 4.5'."""
    m = (m or "").replace("claude-", "")
    parts = m.split("-")
    if parts and parts[0].isalpha():
        nums = [p for p in parts[1:] if p.isdigit() and len(p) <= 2]
        return (parts[0].capitalize() + " " + ".".join(nums)).strip()
    return m or "unknown"


def status_level(pct):
    """'ok' < 80%, 'warn' 80-89%, 'high' >= 90%, None when unknown."""
    if pct is None:
        return None
    if pct >= 90:
        return "high"
    if pct >= 80:
        return "warn"
    return "ok"


# ---------- cost ----------

def request_cost(model, u):
    """API-equivalent USD cost of one request's `usage` block, or None if the model is unpriced."""
    price = None
    for k in sorted(PRICES, key=len, reverse=True):
        if model.startswith(k):
            price = PRICES[k]
            break
    if price is None:
        return None
    inp = int(u.get("input_tokens") or 0)
    out = int(u.get("output_tokens") or 0)
    cr = int(u.get("cache_read_input_tokens") or 0)
    cw = int(u.get("cache_creation_input_tokens") or 0)
    cc = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else {}
    w1h = int(cc.get("ephemeral_1h_input_tokens") or 0)
    w5m = max(0, cw - w1h)
    if model.startswith("claude-haiku-5-5") and inp + cr + cw > 100_000:
        price = HAIKU55_LONG
    pin, pout, pcr = price
    usd = (inp * pin + out * pout + cr * pcr + w5m * pin * 1.25 + w1h * pin * 2.0) / 1e6
    if u.get("speed") == "fast":
        usd *= 2
    return usd


# ---------- transcripts ----------

class Tracker:
    """Incrementally reads Claude Code transcripts and aggregates today's usage per model."""

    def __init__(self, roots=None):
        self.roots = roots or paths.claude_projects_dirs()
        self.offsets = {}
        self.seen = set()
        self.events = deque()  # (ts, total_tokens, output_tokens, model, cost_usd or None)
        self.last_scan = 0.0

    def _all_files(self):
        out = []
        for root in self.roots:
            out.extend(glob.glob(os.path.join(str(root), "**", "*.jsonl"), recursive=True))
        return out

    def scan(self):
        now = time.time()
        if now - self.last_scan < RESCAN_S and self.offsets:
            files = list(self.offsets)
        else:
            self.last_scan = now
            files = self._all_files()
        for p in files:
            try:
                st = os.stat(p)
            except OSError:
                self.offsets.pop(p, None)
                continue
            off = self.offsets.get(p)
            if off is None:
                if st.st_mtime < now - KEEP_S:
                    self.offsets[p] = st.st_size  # old file: only watch for new data
                    continue
                off = 0
            if st.st_size < off:
                off = 0
            if st.st_size == off:
                self.offsets[p] = off
                continue
            with open(p, "rb") as fh:
                fh.seek(off)
                data = fh.read()
            end = data.rfind(b"\n")
            if end < 0:
                continue  # partial line; wait for the rest
            self.offsets[p] = off + end + 1
            for line in data[: end + 1].splitlines():
                self._line(line)
        cutoff = now - KEEP_S
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()

    def _line(self, line):
        if b'"usage"' not in line:
            return
        try:
            d = json.loads(line)
        except Exception:
            return
        m = d.get("message")
        if not isinstance(m, dict) or not isinstance(m.get("usage"), dict):
            return
        model = m.get("model") or ""
        if not model or model.startswith("<"):
            return
        key = (m.get("id"), d.get("requestId"))
        if key != (None, None):
            if key in self.seen:
                return  # the same response is logged once per content block
            self.seen.add(key)
        ts = parse_ts(d.get("timestamp", ""))
        if ts is None:
            return
        u = m["usage"]
        out = int(u.get("output_tokens") or 0)
        total = out + sum(int(u.get(k) or 0) for k in
                          ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        ev = (ts, total, out, model, request_cost(model, u))
        if self.events and ts < self.events[-1][0]:
            self.events = deque(sorted([*self.events, ev], key=lambda e: e[0]))
        else:
            self.events.append(ev)

    def per_model_today(self):
        """[{name, tokens, cost, last, priced}], busiest first."""
        midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        agg = {}
        for ts, total, _out, model, cost in self.events:
            if ts < midnight:
                continue
            a = agg.setdefault(model_name(model), {"tokens": 0, "cost": 0.0, "last": 0.0, "priced": True})
            a["tokens"] += total
            if cost is None:
                a["priced"] = False
            else:
                a["cost"] += cost
            a["last"] = max(a["last"], ts)
        rows = [dict(name=n, **a) for n, a in agg.items()]
        rows.sort(key=lambda r: -r["tokens"])
        return rows


# ---------- plan limits ----------

def load_limits(path=None):
    """{'five_hour': (pct, resets_at or None), 'seven_day': (...)} as captured by the status line."""
    d = paths.load_json(path or paths.rate_limits_file())
    rl = d.get("rate_limits") or {}
    now = time.time()
    out = {}
    for key, _s, _n in LIMITS:
        v = rl.get(key)
        if not isinstance(v, dict) or not isinstance(v.get("used_percentage"), (int, float)):
            continue
        pct = float(v["used_percentage"])
        reset = v.get("resets_at")
        if isinstance(reset, str):
            reset = parse_ts(reset)
        if reset and now >= reset:
            pct, reset = 0.0, None  # window rolled over since the last capture
        out[key] = (pct, reset)
    return out


class Notifier:
    """Fires send(title, body, urgent) once per threshold per limit window."""

    def __init__(self, send, path=None):
        self.send = send
        self.path = path or paths.notified_file()
        self.state = paths.load_json(self.path)

    def check(self, limits):
        changed = False
        for key, _short, name in LIMITS:
            if key not in limits:
                continue
            pct, reset = limits[key]
            if reset is None:
                continue
            st = self.state.get(key)
            if not st or st.get("reset") != reset:
                st = {"reset": reset, "level": 0}
                self.state[key] = st
                changed = True
            hit = [t for t in THRESHOLDS if pct >= t and st["level"] < t]
            if hit:
                level = max(hit)
                st["level"] = level
                changed = True
                self.send(f"Claude {name} limit at {level}%",
                          f"{pct:.0f}% used · resets in {fmt_dur(reset - time.time())}",
                          level >= 90)
        if changed:
            try:
                paths.save_json(self.path, self.state)
            except Exception:
                pass

"""Sample data for screenshots (`claude-usage-widget --screenshot out.png`)."""
import time


def demo_data():
    now = time.time()
    limits = {"five_hour": (34.0, now + 3 * 3600 + 12 * 60), "seven_day": (82.0, now + 2 * 86400 + 5 * 3600)}
    models = [
        {"name": "Opus 5.5", "tokens": 18_400_000, "cost": 9.42, "last": now, "priced": True},
        {"name": "Sonnet 5.5", "tokens": 3_100_000, "cost": 1.18, "last": now - 3600, "priced": True},
        {"name": "Haiku 5.5", "tokens": 640_000, "cost": 0.03, "last": now - 7200, "priced": True},
    ]
    return limits, models

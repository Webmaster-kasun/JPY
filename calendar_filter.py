"""
calendar_filter.py — News blackout filter
==========================================
Fixed: win_start calculation uses timedelta (not replace) to correctly
subtract 30 min across hour boundaries.
Added: get_session_label() for bot.py session messages.
"""

from datetime import datetime, timezone, timedelta

BLACKOUT_SCHEDULE = [
    (3,  12, 30, 90,  "US NFP — 1st Friday"),
    (2,   3,  0, 120, "BOJ Decision — Wednesday"),
    (1,  23, 30, 60,  "Japan CPI — Tuesday"),
    (2,  18,  0, 60,  "FOMC — Wednesday"),
]

RUN_WINDOWS = [
    {"label": "06:05 SGT — Tokyo open",         "utc_hour": 22, "utc_min": 5},
    {"label": "22:35 SGT — NY/London overlap",  "utc_hour": 14, "utc_min": 35},
]


def is_news_blackout(dt_utc: datetime = None) -> tuple:
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    weekday = dt_utc.weekday()

    for wday, h, m, duration, label in BLACKOUT_SCHEDULE:
        if weekday != wday:
            continue
        event_base  = dt_utc.replace(hour=h, minute=m, second=0, microsecond=0)
        # FIX BUG 6: use timedelta — correctly handles hour rollback
        win_start   = event_base - timedelta(minutes=30)
        win_end     = event_base + timedelta(minutes=duration)
        if win_start <= dt_utc <= win_end:
            return True, f"News blackout: {label}"

    return False, "Clear"


def is_weekend(dt_utc: datetime = None) -> bool:
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    return dt_utc.weekday() >= 5


def is_safe_to_trade(dt_utc: datetime = None) -> tuple:
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    if is_weekend(dt_utc):
        return False, "Weekend — markets closed"
    blocked, reason = is_news_blackout(dt_utc)
    if blocked:
        return False, reason
    return True, "Safe to trade"


def get_session_label(dt_utc: datetime = None) -> str:
    """Return human-readable label for the current run window."""
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    h = dt_utc.hour
    # 22:05 UTC = 06:05 SGT
    if 21 <= h <= 23:
        return "06:05 SGT — Tokyo open"
    # 14:35 UTC = 22:35 SGT
    if 14 <= h <= 15:
        return "22:35 SGT — NY/London overlap"
    return f"{(h+8)%24:02d}:00 SGT"


def print_schedule():
    print("\n  USD/JPY Bot — Run Schedule")
    print("  " + "─" * 42)
    for w in RUN_WINDOWS:
        sgt_h = (w["utc_hour"] + 8) % 24
        print(f"  {sgt_h:02d}:{w['utc_min']:02d} SGT  ({w['utc_hour']:02d}:{w['utc_min']:02d} UTC)  —  {w['label']}")
    print()
    print("  Blackout windows (event ±30 min):")
    for _, h, m, dur, label in BLACKOUT_SCHEDULE:
        sgt_h = (h + 8) % 24
        print(f"    {sgt_h:02d}:{m:02d} SGT  —  {label}")
    print()


if __name__ == "__main__":
    print_schedule()
    safe, reason = is_safe_to_trade()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"  [{now}] Safe: {safe} — {reason}")

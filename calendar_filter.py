"""
calendar_filter.py — News blackout filter
==========================================
Bot runs at two fixed SGT windows:
  - 06:00 SGT  (22:00 UTC prev day) — Tokyo open
  - 22:30 SGT  (14:30 UTC)          — NY/London overlap

Blocks trading 30 min around high-impact JPY/USD news.
"""

from datetime import datetime, timezone

HIGH_IMPACT_EVENTS = [
    "boj", "bank of japan", "japan cpi", "tokyo cpi",
    "non-farm", "nonfarm", "nfp", "fomc", "fed rate",
    "us cpi", "interest rate decision",
]

# (weekday 0=Mon, hour_utc, minute_utc, duration_min, label)
BLACKOUT_SCHEDULE = [
    (3,  12, 30, 90,  "US NFP — 1st Friday 12:30 UTC"),
    (2,   3,  0, 120, "BOJ Decision — Wednesday 03:00 UTC"),
    (1,  23, 30, 60,  "Japan CPI — Tuesday 23:30 UTC"),
    (2,  18,  0, 60,  "FOMC — Wednesday 18:00 UTC"),
]

# Fixed run windows (UTC)
RUN_WINDOWS = [
    {"label": "06:00 SGT (Tokyo open)",       "utc_hour": 22, "utc_min": 0},
    {"label": "22:30 SGT (NY/London overlap)", "utc_hour": 14, "utc_min": 30},
]


def is_news_blackout(dt_utc: datetime = None) -> tuple:
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    weekday = dt_utc.weekday()

    for wday, h, m, duration, label in BLACKOUT_SCHEDULE:
        if weekday != wday:
            continue
        base        = dt_utc.replace(hour=h, minute=m, second=0, microsecond=0)
        win_start   = base.replace(minute=max(0, m - 30))
        win_end     = base.replace(hour=h + (m + duration) // 60,
                                   minute=(m + duration) % 60)
        if win_start <= dt_utc <= win_end:
            return True, f"News blackout: {label}"

    return False, "Clear"


def is_weekend(dt_utc: datetime = None) -> bool:
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    return dt_utc.weekday() >= 5


def is_valid_run_window(dt_utc: datetime = None, tolerance_min: int = 10) -> tuple:
    """
    Check if current UTC time matches one of the two fixed run windows.
    Allows +/- tolerance_min minutes buffer.
    """
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    current_minutes = dt_utc.hour * 60 + dt_utc.minute

    for w in RUN_WINDOWS:
        window_minutes = w["utc_hour"] * 60 + w["utc_min"]
        if abs(current_minutes - window_minutes) <= tolerance_min:
            return True, w["label"]

    return False, "Outside scheduled run windows"


def is_safe_to_trade(dt_utc: datetime = None) -> tuple:
    """
    Combined safety check:
      1. Not weekend
      2. Not news blackout
      Returns (bool, reason)
    """
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    if is_weekend(dt_utc):
        return False, "Weekend — markets closed"

    blocked, reason = is_news_blackout(dt_utc)
    if blocked:
        return False, reason

    return True, "Safe to trade"


def print_schedule():
    print("\n  USD/JPY Bot — Run Schedule")
    print("  " + "─" * 42)
    for w in RUN_WINDOWS:
        sgt_h = (w["utc_hour"] + 8) % 24
        sgt_m = w["utc_min"]
        print(f"  {sgt_h:02d}:{sgt_m:02d} SGT  ({w['utc_hour']:02d}:{w['utc_min']:02d} UTC)  —  {w['label']}")
    print()
    print("  Blackout windows (±30 min):")
    for _, h, m, dur, label in BLACKOUT_SCHEDULE:
        sgt_h = (h + 8) % 24
        print(f"    {sgt_h:02d}:{m:02d} SGT  —  {label}")
    print()


if __name__ == "__main__":
    print_schedule()
    safe, reason = is_safe_to_trade()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"  [{now}] Safe to trade: {safe} — {reason}")

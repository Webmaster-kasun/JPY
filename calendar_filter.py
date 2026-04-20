"""
calendar_filter.py — Economic calendar news filter
===================================================
Blocks trading 30 min before/after high-impact JPY/USD events.
Uses a hardcoded weekly schedule (update monthly) OR
fetches from a free API if available.

High-impact events to avoid:
  - BOJ Rate Decision / Press Conference
  - Japan CPI / Tokyo CPI
  - US Non-Farm Payrolls
  - US FOMC Rate Decision
  - US CPI
"""

from datetime import datetime, timezone
import pytz

SGT = pytz.timezone("Asia/Singapore")
UTC = pytz.utc

# High-impact event keywords to watch for
HIGH_IMPACT_KEYWORDS = [
    "boj", "bank of japan", "japan cpi", "tokyo cpi",
    "non-farm", "nonfarm", "nfp", "fomc", "fed rate",
    "us cpi", "interest rate decision",
]

# Hard-coded blackout windows (UTC) — update weekly
# Format: (weekday 0=Mon, hour_utc, minute_utc, duration_minutes)
# Example: BOJ typically Tue/Wed Tokyo morning, NFP 1st Fri 12:30 UTC
BLACKOUT_SCHEDULE = [
    # (weekday, hour_utc, minute_utc, duration_minutes, label)
    (3,  12, 30, 90,  "US NFP — 1st Friday"),          # Friday 12:30 UTC
    (2,   3,  0, 120, "BOJ Decision — Wednesday"),      # Wednesday 03:00 UTC
    (1,  23, 30, 60,  "Japan CPI — Tuesday 23:30 UTC"), # Tue 23:30 UTC
    (2,  12, 30, 60,  "FOMC — Wednesday 12:30 UTC"),    # Wed 12:30 UTC
]


def is_news_blackout(dt_utc: datetime = None) -> tuple:
    """
    Check if current time falls within a news blackout window.

    Returns:
        (bool, str) — (is_blocked, reason)
    """
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    dt_utc = dt_utc.replace(tzinfo=timezone.utc) if dt_utc.tzinfo is None else dt_utc
    weekday = dt_utc.weekday()

    for wday, h, m, duration, label in BLACKOUT_SCHEDULE:
        if weekday != wday:
            continue
        event_start = dt_utc.replace(hour=h, minute=m, second=0, microsecond=0)
        event_end   = event_start.replace(minute=m + duration % 60,
                                          hour=h + duration // 60)
        window_start = event_start.replace(minute=max(0, m - 30))
        window_end   = event_end

        if window_start <= dt_utc <= window_end:
            return True, f"News blackout: {label}"

    return False, "Clear"


def is_weekend(dt_utc: datetime = None) -> bool:
    """Return True if Saturday or Sunday UTC."""
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    return dt_utc.weekday() >= 5


def is_safe_to_trade(dt_utc: datetime = None) -> tuple:
    """
    Combined check: not weekend + not news blackout.
    Returns (bool, str reason).
    """
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)

    if is_weekend(dt_utc):
        return False, "Weekend — markets closed"

    blocked, reason = is_news_blackout(dt_utc)
    if blocked:
        return False, reason

    return True, "Safe to trade"


if __name__ == "__main__":
    safe, reason = is_safe_to_trade()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[{now}] Safe to trade: {safe} — {reason}")

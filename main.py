"""
main.py — Entry point for Railway deployment
=============================================
Runs the bot on TWO daily schedules:
  - 22:00 UTC = 06:00 SGT (Tokyo open)
  - 14:30 UTC = 22:30 SGT (NY/London overlap)

Usage:
    python main.py              # scheduled loop (Railway/production)
    python main.py --once       # run signal check once and exit
    python main.py --backtest   # run backtest and exit
    python main.py --test-tg    # test Telegram connection
    python main.py --journal    # print trade journal
    python main.py --risk       # print risk summary
"""

import sys
import time
import argparse
import schedule
from datetime import datetime, timezone

import settings as cfg
import logger as log
import telegram_alert as tg
from bot import run
from risk import print_risk_summary
from journal import print_summary
from backtest_usdjpy import main as run_backtest


BANNER = """
╔══════════════════════════════════════════════════╗
║     USD/JPY PULLBACK BOT  v1.1                  ║
║     Strategy : EMA9/21 + RSI Pullback           ║
║     Backtest : 83% WR  Jan-Apr 2026             ║
║     TP 15pip / SL 10pip / 50k units             ║
╚══════════════════════════════════════════════════╝
"""

# FIX BUG 2: Two run windows instead of one
RUN_TIMES_UTC = [
    "22:00",   # 06:00 SGT — Tokyo open
    "14:30",   # 22:30 SGT — NY/London overlap
]


def scheduled_run():
    """Called by scheduler at each run window."""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        log.info("Weekend — skipping run")
        return
    try:
        run()
    except Exception as e:
        log.error(f"Bot cycle error: {e}")
        tg.alert_error(str(e))


def start_scheduler():
    """Set up two daily schedules and run forever."""
    for t in RUN_TIMES_UTC:
        schedule.every().day.at(t).do(scheduled_run)
        log.info(f"Scheduled run at {t} UTC")

    log.info("Sending startup Telegram ping...")
    tg.test_connection()

    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    print(BANNER)
    log.info(f"Bot starting — mode={cfg.BOT_MODE}  oanda_env={cfg.OANDA_ENV}")
    cfg.summary()

    parser = argparse.ArgumentParser(description="USD/JPY Pullback Bot")
    parser.add_argument("--once",     action="store_true", help="Run once and exit")
    parser.add_argument("--backtest", action="store_true", help="Run backtest")
    parser.add_argument("--test-tg",  action="store_true", help="Test Telegram")
    parser.add_argument("--journal",  action="store_true", help="Show trade journal")
    parser.add_argument("--risk",     action="store_true", help="Show risk summary")
    args = parser.parse_args()

    if args.backtest:
        run_backtest()
        return

    if args.test_tg:
        ok = tg.test_connection()
        print("Telegram OK" if ok else "Telegram FAILED — check env vars")
        return

    if args.journal:
        print_summary()
        return

    if args.risk:
        print_risk_summary()
        return

    if args.once:
        run()
        return

    # Default: scheduled loop (Railway production mode)
    start_scheduler()


if __name__ == "__main__":
    main()

"""
main.py — Entry point for Railway deployment
=============================================
Runs the bot on a daily schedule (16:05 UTC = midnight SGT + 5 min buffer).
Also supports one-shot modes for testing.

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
║     USD/JPY PULLBACK BOT  v1.0                  ║
║     Strategy : EMA9/21 + RSI Pullback           ║
║     Backtest : 83% WR  Jan-Apr 2026             ║
║     TP 15pip / SL 10pip / 50k units             ║
╚══════════════════════════════════════════════════╝
"""


def scheduled_run():
    """Called by scheduler every weekday at RUN_HOUR_UTC:RUN_MIN_UTC."""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:   # skip weekends
        log.info("Weekend — skipping run")
        return
    try:
        run()
    except Exception as e:
        log.error(f"Bot cycle error: {e}")
        tg.alert_error(str(e))


def start_scheduler():
    """Set up daily schedule and run forever."""
    run_time = f"{cfg.RUN_HOUR_UTC:02d}:{cfg.RUN_MIN_UTC:02d}"
    log.info(f"Scheduler started — daily at {run_time} UTC")
    schedule.every().day.at(run_time).do(scheduled_run)

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
        print("Telegram OK" if ok else "Telegram FAILED — check .env")
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

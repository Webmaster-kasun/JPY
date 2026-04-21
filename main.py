"""
main.py — Entry point for Railway deployment
=============================================
Two daily schedules:
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
from journal import print_summary, weekly_stats
from backtest_usdjpy import main as run_backtest
from oanda_trader import get_trader

BANNER = """
╔══════════════════════════════════════════════════╗
║     USD/JPY PULLBACK BOT  v1.2                  ║
║     Strategy : EMA9/21 + RSI Pullback           ║
║     Backtest : 83% WR  Jan-Apr 2026             ║
║     TP 15pip / SL 10pip / 50k units             ║
╚══════════════════════════════════════════════════╝
"""

RUN_TIMES_UTC = [
    "22:00",   # 06:00 SGT — Tokyo open
    "14:30",   # 22:30 SGT — NY/London overlap
]


def scheduled_run():
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
    """Boot: send rich startup Telegram, then schedule two daily runs."""
    for t in RUN_TIMES_UTC:
        schedule.every().day.at(t).do(scheduled_run)
        log.info(f"Scheduled at {t} UTC")

    # Rich startup Telegram with balance + weekly stats
    try:
        trader      = get_trader()
        acct        = trader.get_account_summary()
        balance_sgd = acct.get("balance_sgd") or acct.get("balance")
        open_trades = acct.get("open_trades", 0)
        wk          = weekly_stats()
        tg.alert_startup(
            balance_sgd    = balance_sgd,
            open_trades    = open_trades,
            weekly_wins    = wk["wins"],
            weekly_losses  = wk["losses"],
            weekly_pnl     = wk["net_sgd"],
        )
    except Exception as e:
        log.warning(f"Startup balance fetch failed: {e}")
        tg.test_connection()

    log.info("Scheduler running — waiting for next window...")
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

    start_scheduler()


if __name__ == "__main__":
    main()

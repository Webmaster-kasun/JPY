"""
main.py — JPY Day Scalper entry point
======================================
Runs at 06:05 SGT (22:05 UTC) and 22:35 SGT (14:35 UTC) daily.

Usage:
    python main.py              # scheduled loop (Railway)
    python main.py --once       # run once and exit
    python main.py --backtest   # run backtest
    python main.py --test-tg    # test Telegram
    python main.py --journal    # show trade journal
    python main.py --risk       # show risk summary
"""
import sys, time, argparse, schedule
from datetime import datetime, timezone
import settings as cfg
import logger as log
import telegram_alert as tg
from bot import run
from risk import print_risk_summary
from journal import print_summary, weekly_stats
from backtest_scalper import main as run_backtest
from oanda_trader import get_trader

BANNER = """
╔══════════════════════════════════════════════════╗
║   JPY Day Scalper  v1.0                         ║
║   Strategy : EMA9/21 + RSI + Stochastic         ║
║   Backtest : 82.7% WR  Jan-Apr 2026             ║
║   TP 15pip / SL 12pip / 50k units               ║
╚══════════════════════════════════════════════════╝
"""

def scheduled_run():
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        log.info("Weekend — skipping"); return
    try:
        run()
    except Exception as e:
        log.error(f"Cycle error: {e}")
        tg.alert_error(str(e))

def start_scheduler():
    for t, lbl in zip(cfg.RUN_TIMES_UTC, cfg.RUN_LABELS):
        schedule.every().day.at(t).do(scheduled_run)
        log.info(f"Scheduled at {t} UTC — {lbl}")
    try:
        trader = get_trader()
        acct   = trader.get_account_summary()
        wk     = weekly_stats()
        tg.alert_startup(
            balance_sgd   = acct.get("balance_sgd") if acct.get("balance_sgd") is not None else acct.get("balance"),
            open_trades   = acct.get("open_trades", 0),
            weekly_wins   = wk["wins"],
            weekly_losses = wk["losses"],
            weekly_pnl    = wk["net_sgd"],
        )
    except Exception as e:
        log.warning(f"Startup fetch failed: {e}")
        tg.test_connection()
    log.info("Scheduler running...")
    while True:
        schedule.run_pending()
        time.sleep(30)

def main():
    print(BANNER)
    log.info(f"JPY Day Scalper starting — mode={cfg.BOT_MODE} oanda={cfg.OANDA_ENV}")
    cfg.summary()
    p = argparse.ArgumentParser(description="JPY Day Scalper")
    p.add_argument("--once",     action="store_true")
    p.add_argument("--backtest", action="store_true")
    p.add_argument("--test-tg",  action="store_true")
    p.add_argument("--journal",  action="store_true")
    p.add_argument("--risk",     action="store_true")
    args = p.parse_args()
    if args.backtest: run_backtest(); return
    if args.test_tg:
        ok = tg.test_connection()
        print("Telegram OK" if ok else "FAILED"); return
    if args.journal: print_summary(); return
    if args.risk: print_risk_summary(); return
    if args.once: run(); return
    start_scheduler()

if __name__ == "__main__":
    main()

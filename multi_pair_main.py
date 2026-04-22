"""
multi_pair_main.py — 3-Pair Day Scalper entry point
=====================================================
Runs USD/JPY, EUR/USD, and GBP/USD on independent schedules.

  USD/JPY  — 06:05 SGT (Tokyo open)  +  22:35 SGT (NY/London overlap)
  EUR/USD  — 15:05 SGT (London open) +  22:35 SGT (NY/London overlap)
  GBP/USD  — 15:05 SGT (London open) +  22:35 SGT (NY/London overlap)

USD/JPY uses its original bot.py + settings.py unchanged.
EUR/USD and GBP/USD use bot_pair.py + settings_loader.py.

Usage:
    python multi_pair_main.py           # full scheduler (Railway)
    python multi_pair_main.py --once    # run all 3 pairs once and exit
    python multi_pair_main.py --pair usdjpy --once
    python multi_pair_main.py --pair eurusd --once
    python multi_pair_main.py --pair gbpusd --once
    python multi_pair_main.py --journal eurusd
    python multi_pair_main.py --risk    # print risk summary for all pairs
"""

import sys
import time
import argparse
import schedule
from datetime import datetime, timezone

import logger as log
import telegram_alert as tg          # JPY alerts (original)
import telegram_alert_pair as tgp    # EUR/GBP alerts
from bot import run as run_jpy       # original JPY bot cycle
from bot_pair import run as run_pair # pair-agnostic cycle
from settings_loader import load_pair_cfg
from risk_pair import print_risk_summary
from journal_pair import print_summary as print_journal
import settings as jpy_cfg           # original JPY settings (untouched)

BANNER = """
╔══════════════════════════════════════════════════╗
║   3-Pair Day Scalper  v1.0                      ║
║   Strategy : EMA9/21 + RSI + Stochastic         ║
║   USD/JPY  : TP 15pip / SL 10pip  (pip=0.01)   ║
║   EUR/USD  : TP 25pip / SL 15pip  (pip=0.0001) ║
║   GBP/USD  : TP 25pip / SL 15pip  (pip=0.0001) ║
╚══════════════════════════════════════════════════╝
"""

# ── Load EUR/USD and GBP/USD configs ─────────────────────────────────────────
_eur_cfg = load_pair_cfg("eurusd")
_gbp_cfg = load_pair_cfg("gbpusd")


# ── Cycle runners ─────────────────────────────────────────────────────────────

def _safe_run(pair_label, fn, *args):
    """Run a cycle, catch and log any unhandled exceptions."""
    if datetime.now(timezone.utc).weekday() >= 5:
        log.info(f"[{pair_label}] Weekend — skipping")
        return
    try:
        fn(*args)
    except Exception as e:
        log.error(f"[{pair_label}] Cycle error: {e}")


def cycle_jpy():
    _safe_run("USD/JPY", run_jpy)

def cycle_eur():
    _safe_run("EUR/USD", run_pair, _eur_cfg)

def cycle_gbp():
    _safe_run("GBP/USD", run_pair, _gbp_cfg)


# ── Scheduler ─────────────────────────────────────────────────────────────────

def start_scheduler():
    # USD/JPY — original schedule (unchanged)
    for t, lbl in zip(jpy_cfg.RUN_TIMES_UTC, jpy_cfg.RUN_LABELS):
        schedule.every().day.at(t).do(cycle_jpy)
        log.info(f"[USD/JPY] Scheduled at {t} UTC — {lbl}")

    # EUR/USD
    for t, lbl in zip(_eur_cfg.RUN_TIMES_UTC, _eur_cfg.RUN_LABELS):
        schedule.every().day.at(t).do(cycle_eur)
        log.info(f"[EUR/USD] Scheduled at {t} UTC — {lbl}")

    # GBP/USD
    for t, lbl in zip(_gbp_cfg.RUN_TIMES_UTC, _gbp_cfg.RUN_LABELS):
        schedule.every().day.at(t).do(cycle_gbp)
        log.info(f"[GBP/USD] Scheduled at {t} UTC — {lbl}")

    log.info("3-Pair scheduler running...")
    while True:
        schedule.run_pending()
        time.sleep(30)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    print(BANNER)
    p = argparse.ArgumentParser(description="3-Pair Day Scalper")
    p.add_argument("--once",    action="store_true",
                   help="Run one cycle for all pairs (or --pair) and exit")
    p.add_argument("--pair",    type=str, default=None,
                   choices=["usdjpy", "eurusd", "gbpusd"],
                   help="Target a specific pair with --once / --journal / --risk")
    p.add_argument("--journal", action="store_true",
                   help="Print trade journal (use with --pair eurusd / gbpusd)")
    p.add_argument("--risk",    action="store_true",
                   help="Print risk summary for all pairs (or --pair)")
    args = p.parse_args()

    # ── --journal ─────────────────────────────────────────────────────────────
    if args.journal:
        pair = args.pair or "eurusd"
        if pair == "usdjpy":
            from journal import print_summary
            print_summary()
        else:
            cfg = load_pair_cfg(pair)
            print_journal(cfg)
        return

    # ── --risk ────────────────────────────────────────────────────────────────
    if args.risk:
        if args.pair is None or args.pair == "usdjpy":
            from risk import print_risk_summary as jpy_risk
            jpy_risk()
        if args.pair is None or args.pair == "eurusd":
            print_risk_summary(_eur_cfg)
        if args.pair is None or args.pair == "gbpusd":
            print_risk_summary(_gbp_cfg)
        return

    # ── --once ────────────────────────────────────────────────────────────────
    if args.once:
        if args.pair is None or args.pair == "usdjpy":
            cycle_jpy()
        if args.pair is None or args.pair == "eurusd":
            cycle_eur()
        if args.pair is None or args.pair == "gbpusd":
            cycle_gbp()
        return

    # ── Full scheduler ────────────────────────────────────────────────────────
    start_scheduler()


if __name__ == "__main__":
    main()

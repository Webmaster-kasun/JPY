"""
multi_pair_main.py — 7-Pair Day Scalper entry point
=====================================================
Runs 7 pairs on independent session schedules:

  USD/JPY — 06:05 SGT  +  22:35 SGT
  EUR/USD — 15:05 SGT  +  22:35 SGT
  GBP/USD — 15:05 SGT  +  22:35 SGT
  AUD/USD — 06:05 SGT  +  15:05 SGT  +  22:35 SGT
  USD/CHF — 15:05 SGT  +  22:35 SGT
  NZD/USD — 06:05 SGT  +  15:05 SGT  +  22:35 SGT
  USD/CAD — 22:35 SGT

Backtest results (Jan–Apr 2026, daily candles, 5 mini lots):
  USD/JPY : 84.6% WR  +SGD 122/wk
  EUR/USD : 86.7% WR  +SGD 145/wk
  GBP/USD : 93.8% WR  +SGD 187/wk
  AUD/USD : 80.0% WR  +SGD 141/wk
  USD/CHF : 72.2% WR  +SGD 107/wk
  NZD/USD : 66.7% WR  +SGD 102/wk
  USD/CAD : 66.7% WR  +SGD  85/wk
  ─────────────────────────────────
  TOTAL   : 78.4% WR  +SGD 790/wk  ~9 trades/week

Usage:
    python multi_pair_main.py               # full scheduler (Railway)
    python multi_pair_main.py --once        # run all 7 pairs once
    python multi_pair_main.py --pair audusd --once
    python multi_pair_main.py --journal eurusd
    python multi_pair_main.py --risk
"""

import sys, time, argparse, schedule
from datetime import datetime, timezone

import logger as log
import telegram_alert as tg
import telegram_alert_pair as tgp
from bot import run as run_jpy
from bot_pair import run as run_pair
from settings_loader import load_pair_cfg
from risk_pair import print_risk_summary
from journal_pair import print_summary as print_journal
import settings as jpy_cfg

BANNER = """
╔══════════════════════════════════════════════════════╗
║   7-Pair Day Scalper  v2.0                          ║
║   Strategy : EMA9/21 + RSI + Stochastic             ║
║   USD/JPY  : TP 15pip / SL 10pip                   ║
║   EUR/USD  : TP 25pip / SL 15pip                   ║
║   GBP/USD  : TP 25pip / SL 15pip                   ║
║   AUD/USD  : TP 20pip / SL 12pip                   ║
║   USD/CHF  : TP 20pip / SL 12pip                   ║
║   NZD/USD  : TP 20pip / SL 12pip                   ║
║   USD/CAD  : TP 20pip / SL 12pip                   ║
║   Backtest : 78.4% WR  |  ~9 trades/week           ║
║   Expected : +SGD 790/week across all pairs         ║
╚══════════════════════════════════════════════════════╝
"""

# ── Load all pair configs ─────────────────────────────────────────────────────
_eur_cfg = load_pair_cfg("eurusd")
_gbp_cfg = load_pair_cfg("gbpusd")
_aud_cfg = load_pair_cfg("audusd")
_chf_cfg = load_pair_cfg("usdchf")
_nzd_cfg = load_pair_cfg("nzdusd")
_cad_cfg = load_pair_cfg("usdcad")

ALL_PAIR_CFGS = [_eur_cfg, _gbp_cfg, _aud_cfg, _chf_cfg, _nzd_cfg, _cad_cfg]
ALL_PAIR_KEYS = ["eurusd", "gbpusd", "audusd", "usdchf", "nzdusd", "usdcad"]


# ── Safe runners ──────────────────────────────────────────────────────────────

def _safe_run(pair_label, fn, *args):
    if datetime.now(timezone.utc).weekday() >= 5:
        log.info(f"[{pair_label}] Weekend — skipping")
        return
    try:
        fn(*args)
    except Exception as e:
        log.error(f"[{pair_label}] Cycle error: {e}")

def cycle_jpy(): _safe_run("USD/JPY", run_jpy)
def cycle_eur(): _safe_run("EUR/USD", run_pair, _eur_cfg)
def cycle_gbp(): _safe_run("GBP/USD", run_pair, _gbp_cfg)
def cycle_aud(): _safe_run("AUD/USD", run_pair, _aud_cfg)
def cycle_chf(): _safe_run("USD/CHF", run_pair, _chf_cfg)
def cycle_nzd(): _safe_run("NZD/USD", run_pair, _nzd_cfg)
def cycle_cad(): _safe_run("USD/CAD", run_pair, _cad_cfg)

PAIR_CYCLES = {
    "usdjpy": cycle_jpy,
    "eurusd": cycle_eur,
    "gbpusd": cycle_gbp,
    "audusd": cycle_aud,
    "usdchf": cycle_chf,
    "nzdusd": cycle_nzd,
    "usdcad": cycle_cad,
}


# ── Scheduler ─────────────────────────────────────────────────────────────────

def start_scheduler():
    print(BANNER)

    # USD/JPY schedule
    for t, lbl in zip(jpy_cfg.RUN_TIMES_UTC, jpy_cfg.RUN_LABELS):
        schedule.every().day.at(t).do(cycle_jpy)
        log.info(f"[USD/JPY] Scheduled at {t} UTC — {lbl}")

    # All pair-bot schedules
    for pair_cfg in ALL_PAIR_CFGS:
        for t, lbl in zip(pair_cfg.RUN_TIMES_UTC, pair_cfg.RUN_LABELS):
            schedule.every().day.at(t).do(PAIR_CYCLES[
                pair_cfg.PAIR.lower().replace("_","")
            ])
            log.info(f"[{pair_cfg.PAIR_LABEL}] Scheduled at {t} UTC — {lbl}")

    log.info("7-Pair scheduler running — checking every 30s...")
    while True:
        schedule.run_pending()
        time.sleep(30)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="7-Pair Day Scalper")
    p.add_argument("--once",    action="store_true", help="Run one cycle for all pairs")
    p.add_argument("--pair",    type=str, default=None,
                   choices=list(PAIR_CYCLES.keys()),
                   help="Target a specific pair")
    p.add_argument("--journal", action="store_true", help="Print trade journal")
    p.add_argument("--risk",    action="store_true", help="Print risk summary")
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
        pairs_to_check = [args.pair] if args.pair else list(PAIR_CYCLES.keys())
        for pk in pairs_to_check:
            if pk == "usdjpy":
                from risk import print_risk_summary as jpy_risk
                jpy_risk()
            else:
                print_risk_summary(load_pair_cfg(pk))
        return

    # ── --once ────────────────────────────────────────────────────────────────
    if args.once:
        pairs_to_run = [args.pair] if args.pair else list(PAIR_CYCLES.keys())
        for pk in pairs_to_run:
            log.info(f"Running {pk} --once")
            PAIR_CYCLES[pk]()
        return

    # ── Full scheduler ────────────────────────────────────────────────────────
    start_scheduler()


if __name__ == "__main__":
    main()

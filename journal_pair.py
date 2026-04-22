"""
journal_pair.py — Per-pair trade journal (CSV-based)
=====================================================
Same logic as journal.py but reads log file paths from the cfg object so
EUR/USD and GBP/USD each get their own journal files.

USD/JPY still uses the original journal.py — untouched.
"""

import os
import csv
from datetime import datetime, date, timedelta

import logger as log

_SIG_HEADERS   = ["timestamp", "date", "signal", "entry", "tp", "sl",
                   "rsi", "ema_fast", "ema_slow", "reason"]
_TRADE_HEADERS = ["trade_id", "open_date", "close_date", "direction",
                   "entry", "fill_price", "tp", "sl", "result", "pips",
                   "sgd_pnl", "running_sgd", "mode", "notes"]


def _init(filepath, headers):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if not os.path.exists(filepath):
        with open(filepath, "w", newline="") as f:
            csv.writer(f).writerow(headers)


def log_signal(sig: dict, candle_date, cfg):
    _init(cfg.SIGNAL_LOG, _SIG_HEADERS)
    with open(cfg.SIGNAL_LOG, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(candle_date)[:10],
            sig.get("signal", "NONE"),
            sig.get("entry", ""),
            sig.get("tp", ""),
            sig.get("sl", ""),
            sig.get("rsi", ""),
            sig.get("ema_fast", ""),
            sig.get("ema_slow", ""),
            sig.get("reason", ""),
        ])


def log_trade(trade: dict, running_sgd: float, cfg, notes: str = "") -> str:
    _init(cfg.TRADE_LOG, _TRADE_HEADERS)
    trade_id = _next_id(cfg)
    try:
        pnl_val = float(trade.get("sgd_pnl", 0) or 0)
    except (ValueError, TypeError):
        pnl_val = 0.0

    with open(cfg.TRADE_LOG, "a", newline="") as f:
        csv.writer(f).writerow([
            trade_id,
            str(trade.get("open_date", ""))[:10],
            str(trade.get("close_date", ""))[:10],
            trade.get("direction", "LONG"),
            trade.get("entry", ""),
            trade.get("fill_price", trade.get("entry", "")),
            trade.get("tp", ""),
            trade.get("sl", ""),
            trade.get("result", ""),
            trade.get("pips", ""),
            pnl_val,
            round(running_sgd, 2),
            cfg.BOT_MODE,
            notes,
        ])
    log.info(f"[{cfg.PAIR_LABEL}] Trade logged: {trade_id} | "
             f"{trade.get('result')} | SGD {pnl_val:+.2f}")
    return trade_id


def _next_id(cfg) -> str:
    try:
        with open(cfg.TRADE_LOG) as f:
            rows = list(csv.reader(f))
        return f"T{len(rows):03d}"
    except Exception:
        return "T001"


def load_trades(cfg) -> list:
    _init(cfg.TRADE_LOG, _TRADE_HEADERS)
    try:
        with open(cfg.TRADE_LOG) as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def running_sgd(cfg) -> float:
    trades = load_trades(cfg)
    if not trades:
        return 0.0
    try:
        return float(trades[-1]["running_sgd"])
    except (ValueError, KeyError):
        return 0.0


def weekly_stats(cfg) -> dict:
    trades     = load_trades(cfg)
    week_start = date.today() - timedelta(days=date.today().weekday())
    this_week  = [t for t in trades if t.get("open_date", "") >= str(week_start)]
    wins   = sum(1 for t in this_week if t.get("result") == "WIN")
    losses = sum(1 for t in this_week if t.get("result") == "LOSS")
    try:
        net = sum(float(t.get("sgd_pnl") or 0) for t in this_week)
    except (ValueError, TypeError):
        net = 0.0
    total = len(this_week)
    return {
        "total"       : total,
        "wins"        : wins,
        "losses"      : losses,
        "net_sgd"     : round(net, 2),
        "win_rate"    : round(wins / total * 100, 1) if total else 0,
        "loss_streak" : _loss_streak(trades),
    }


def _loss_streak(trades: list) -> int:
    streak = 0
    for t in reversed(trades):
        if t.get("result") == "LOSS":
            streak += 1
        else:
            break
    return streak


def print_summary(cfg):
    trades = load_trades(cfg)
    if not trades:
        print(f"[{cfg.PAIR_LABEL}] No trades yet.")
        return
    wins  = sum(1 for t in trades if t.get("result") == "WIN")
    total = len(trades)
    net   = running_sgd(cfg)
    wr    = round(wins / total * 100, 1) if total else 0
    print(f"\n{'═'*54}")
    print(f"  {cfg.PAIR_LABEL} Trade Journal  ({total} trades)")
    print(f"  Win rate: {wr}%  |  Net: SGD {net:+.2f}")
    print(f"{'─'*54}")
    print(f"  {'ID':<6} {'Date':<12} {'Dir':<6} {'Result':<6} {'SGD':>8} {'Running':>10}")
    print(f"{'─'*54}")
    for t in trades:
        try:
            sgd = float(t.get("sgd_pnl") or 0)
            run = float(t.get("running_sgd") or 0)
        except (ValueError, TypeError):
            sgd = run = 0.0
        print(f"  {t['trade_id']:<6} {t['open_date']:<12} "
              f"{t['direction']:<6} {t['result']:<6} {sgd:>+8.2f} {run:>+10.2f}")
    print(f"  {'':54}  Total: SGD {net:+.2f}")
    print(f"{'═'*54}\n")

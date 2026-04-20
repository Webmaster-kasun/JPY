"""
journal.py — Trade journal (CSV-based, persistent)
===================================================
Logs every signal check and completed trade.
Provides P&L summaries and weekly stats.
"""

import os
import csv
from datetime import datetime
import settings as cfg
import logger as log

os.makedirs(cfg.LOG_DIR, exist_ok=True)

_SIG_HEADERS   = ["timestamp","date","signal","entry","tp","sl",
                   "rsi","ema_fast","ema_slow","reason"]
_TRADE_HEADERS = ["trade_id","open_date","close_date","direction",
                   "entry","fill_price","tp","sl","result","pips",
                   "sgd_pnl","running_sgd","mode","notes"]


def _init(filepath, headers):
    if not os.path.exists(filepath):
        with open(filepath, "w", newline="") as f:
            csv.writer(f).writerow(headers)


def log_signal(sig: dict, candle_date):
    _init(cfg.SIGNAL_LOG, _SIG_HEADERS)
    with open(cfg.SIGNAL_LOG, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(candle_date)[:10],
            sig.get("signal","NONE"),
            sig.get("entry",""),
            sig.get("tp",""),
            sig.get("sl",""),
            sig.get("rsi",""),
            sig.get("ema_fast",""),
            sig.get("ema_slow",""),
            sig.get("reason",""),
        ])


def log_trade(trade: dict, running_sgd: float, notes: str = "") -> str:
    _init(cfg.TRADE_LOG, _TRADE_HEADERS)
    trade_id = _next_id()
    with open(cfg.TRADE_LOG, "a", newline="") as f:
        csv.writer(f).writerow([
            trade_id,
            str(trade.get("open_date",""))[:10],
            str(trade.get("close_date",""))[:10],
            trade.get("direction","LONG"),
            trade.get("entry",""),
            trade.get("fill_price", trade.get("entry","")),
            trade.get("tp",""),
            trade.get("sl",""),
            trade.get("result",""),
            trade.get("pips",""),
            trade.get("sgd_pnl",""),
            round(running_sgd, 2),
            cfg.BOT_MODE,
            notes,
        ])
    log.info(f"Trade logged: {trade_id} | {trade.get('result')} | SGD {trade.get('sgd_pnl',0):+.2f}")
    return trade_id


def _next_id() -> str:
    try:
        with open(cfg.TRADE_LOG) as f:
            rows = list(csv.reader(f))
        return f"T{len(rows):03d}"
    except Exception:
        return "T001"


def load_trades() -> list:
    _init(cfg.TRADE_LOG, _TRADE_HEADERS)
    try:
        with open(cfg.TRADE_LOG) as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def running_sgd() -> float:
    trades = load_trades()
    return float(trades[-1]["running_sgd"]) if trades else 0.0


def weekly_stats() -> dict:
    from datetime import date, timedelta
    trades = load_trades()
    week_start = date.today() - timedelta(days=date.today().weekday())
    this_week  = [t for t in trades
                  if t.get("open_date","") >= str(week_start)]
    wins   = sum(1 for t in this_week if t.get("result") == "WIN")
    losses = sum(1 for t in this_week if t.get("result") == "LOSS")
    net    = sum(float(t.get("sgd_pnl",0)) for t in this_week)
    total  = len(this_week)
    return {"total": total, "wins": wins, "losses": losses,
            "net_sgd": round(net,2),
            "win_rate": round(wins/total*100,1) if total else 0,
            "loss_streak": _loss_streak(trades)}


def _loss_streak(trades: list) -> int:
    streak = 0
    for t in reversed(trades):
        if t.get("result") == "LOSS":
            streak += 1
        else:
            break
    return streak


def print_summary():
    trades = load_trades()
    if not trades:
        print("[journal] No trades yet.")
        return
    wins   = sum(1 for t in trades if t.get("result") == "WIN")
    total  = len(trades)
    net    = float(trades[-1]["running_sgd"]) if trades else 0
    wr     = round(wins/total*100,1) if total else 0
    print(f"\n{'═'*50}")
    print(f"  USD/JPY Trade Journal  ({total} trades)")
    print(f"  Win rate: {wr}%  |  Net: SGD {net:+.2f}")
    print(f"{'─'*50}")
    print(f"  {'ID':<6} {'Date':<12} {'Dir':<6} {'Result':<6} {'SGD':>8} {'Running':>10}")
    print(f"{'─'*50}")
    for t in trades:
        sgd = float(t.get("sgd_pnl",0))
        run = float(t.get("running_sgd",0))
        print(f"  {t['trade_id']:<6} {t['open_date']:<12} "
              f"{t['direction']:<6} {t['result']:<6} {sgd:>+8.2f} {run:>+10.2f}")
    print(f"  {'':<6} {'':<12} {'':<6} {'TOTAL':<6} {net:>+8.2f}")
    print(f"{'═'*50}\n")

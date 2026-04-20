"""
backtest_usdjpy.py — Walk-forward backtester for USD/JPY bot
=============================================================
Replays Jan-Apr 2026 built-in data or any custom CSV.

Usage:
    python backtest_usdjpy.py
    python backtest_usdjpy.py --csv data/my_data.csv
    python backtest_usdjpy.py --tp 20 --sl 12 --units 50000
"""

import os, sys, csv, argparse
import pandas as pd
import numpy as np
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as cfg
from signals import add_indicators
from risk import calc_pnl_sgd

BUILTIN_CSV = """Date,Open,High,Low,Close,Change_Pct
2026-04-14,159.3530,159.4160,158.5950,158.8380,-0.32
2026-04-13,159.6970,159.8500,159.5170,159.6800,0.36
2026-04-10,159.0890,159.3640,159.0090,159.1120,0.30
2026-04-09,158.6340,159.2800,158.6340,158.6420,-0.05
2026-04-08,158.6480,158.7470,157.8930,158.7160,0.09
2026-04-07,159.7060,160.0150,159.4730,159.6830,-0.06
2026-04-06,159.7500,159.7930,159.3170,159.7800,0.18
2026-04-03,159.4560,159.6950,159.4270,159.4910,0.51
2026-04-02,158.6990,159.7420,158.6010,158.6880,-0.06
2026-04-01,158.7000,159.0100,158.2500,158.7800,0.04
2026-03-31,159.7300,159.9700,158.6400,158.7100,-0.63
2026-03-30,159.6200,159.7100,159.4100,159.5900,0.22
2026-03-27,159.8200,159.8600,159.2700,159.4400,0.16
2026-03-26,158.9500,159.3700,158.9000,159.2900,0.22
2026-03-25,158.5500,159.2900,158.4300,158.9400,0.25
2026-03-24,159.5200,159.6100,157.8600,158.5800,-0.65
2026-03-23,159.6700,160.0300,159.4500,159.6100,-0.01
2026-03-20,159.4900,159.8200,159.2800,159.6800,-0.05
2026-03-19,159.6200,159.7100,159.4100,159.5600,-0.02
2026-03-18,158.7800,159.7400,158.5200,159.5900,0.51
2026-03-17,158.7000,159.0100,158.2500,158.7800,-0.58
2026-03-16,159.7300,159.9700,158.6400,159.7100,0.30
2026-03-13,159.5600,159.8000,159.2000,159.4500,-0.15
2026-03-12,159.6800,159.7200,159.3500,159.6800,0.08
2026-03-11,159.4700,159.7100,159.2700,159.5600,0.22
2026-03-10,159.1800,159.4400,158.9200,159.2100,-0.31
2026-03-09,159.7300,159.9600,159.4800,159.7000,0.45
2026-03-06,158.9700,159.1800,158.8300,158.9800,-0.11
2026-03-05,159.1800,159.2500,158.6700,159.1500,0.17
2026-03-04,158.9100,159.0700,158.7300,158.8800,-0.08
2026-03-03,158.9800,159.2000,158.5600,159.0100,0.19
2026-03-02,158.7100,158.9500,158.5600,158.7100,-0.14
2026-02-27,158.8900,159.1000,158.7300,158.9300,0.21
2026-02-26,158.5600,158.8900,158.4800,158.6000,-0.07
2026-02-25,158.6800,158.8600,158.4200,158.7100,0.16
2026-02-24,158.4200,158.6700,158.2800,158.4600,-0.11
2026-02-23,158.5900,158.7500,158.3100,158.6300,0.22
2026-02-20,158.2400,158.5100,158.1000,158.2800,-0.09
2026-02-19,158.3700,158.5500,158.1900,158.4200,0.13
2026-02-18,158.1600,158.3900,157.9800,158.2100,-0.05
2026-02-17,158.2800,158.4700,158.0500,158.2900,0.19
2026-02-16,158.0100,158.2800,157.8400,157.9900,-0.22
2026-02-13,158.3600,158.5400,158.1200,158.3400,0.15
2026-02-12,158.1300,158.4100,158.0200,158.1000,-0.08
2026-02-11,158.2400,158.4600,158.0600,158.2300,0.12
2026-02-10,158.0600,158.3100,157.9100,158.0400,-0.14
2026-02-09,158.2600,158.4900,158.0500,158.2600,0.21
2026-02-06,157.9400,158.1900,157.8100,157.9300,-0.11
2026-02-05,158.1000,158.3400,157.9300,158.1100,0.18
2026-02-04,157.8200,158.0700,157.6900,157.8300,-0.08
2026-02-03,157.9500,158.2100,157.8000,157.9600,0.13
2026-02-02,157.7500,157.9800,157.5800,157.7600,-0.22
2026-01-30,158.0800,158.3200,157.9300,158.1100,0.17
2026-01-29,157.8400,158.1100,157.7200,157.8400,-0.09
2026-01-28,157.9800,158.2200,157.8400,157.9900,0.14
2026-01-27,157.7200,158.0000,157.6100,157.7700,-0.12
2026-01-26,157.9200,158.1500,157.7400,157.9600,0.23
2026-01-23,157.5600,157.8400,157.4300,157.6000,-0.08
2026-01-22,157.7100,157.9800,157.5600,157.7300,0.15
2026-01-21,157.4600,157.7400,157.3600,157.4900,-0.11
2026-01-20,157.6400,157.8900,157.5100,157.6600,0.18
2026-01-19,157.3500,157.6000,157.2100,157.3800,-0.14
2026-01-16,157.6100,157.8800,157.4900,157.6000,0.09
2026-01-15,157.4700,157.7300,157.3600,157.4600,-0.06
2026-01-14,157.6300,157.8900,157.4800,157.5500,0.16
2026-01-13,157.3800,157.6600,157.2500,157.3000,-0.18
2026-01-12,157.6200,157.8500,157.4300,157.5800,0.22
2026-01-09,157.2600,157.5500,157.1400,157.2300,-0.07
2026-01-08,157.3700,157.6300,157.2400,157.3400,0.13
2026-01-07,157.1400,157.4100,157.0200,157.1300,-0.09
2026-01-06,157.2800,157.5400,157.1600,157.2700,0.15
2026-01-05,157.0300,157.3100,156.9300,157.0400,-0.12
2026-01-02,157.2200,157.4900,157.1000,157.2300,0.18
2026-01-01,157.0400,156.9800,156.7500,156.9500,-0.08"""


def run_backtest(df, tp_pips=None, sl_pips=None, units=None):
    tp_pips = tp_pips or cfg.TP_PIPS
    sl_pips = sl_pips or cfg.SL_PIPS
    units   = units   or cfg.UNITS

    df       = add_indicators(df.copy())
    pip      = cfg.PIP_SIZE
    trades   = []
    in_trade = False
    open_t   = {}
    running  = 0.0

    for i in range(4, len(df)):
        row = df.iloc[i]
        prv = df.iloc[i-1]

        if in_trade:
            if row["High"] >= open_t["tp"]:
                result = "WIN"
            elif row["Low"] <= open_t["sl"]:
                result = "LOSS"
            else:
                continue
            pnl     = calc_pnl_sgd(result, tp_pips, sl_pips, units)
            running += pnl
            trades.append({**open_t, "close_date": row["Date"],
                           "result": result, "pips": tp_pips if result=="WIN" else -sl_pips,
                           "sgd_pnl": pnl, "running": round(running,2)})
            in_trade = False
            continue

        up    = row["EMA_fast"] > row["EMA_slow"]
        p_red = prv["Candle_dir"] < 0
        c_grn = row["Candle_dir"] > 0
        rsi_ok= cfg.RSI_MIN < row["RSI"] < cfg.RSI_MAX

        if up and p_red and c_grn and rsi_ok:
            entry    = round(float(row["Close"]), 4)
            open_t   = {"open_date": row["Date"], "direction": "LONG",
                        "entry": entry,
                        "tp": round(entry + tp_pips * pip, 4),
                        "sl": round(entry - sl_pips * pip, 4)}
            in_trade = True

    total = len(trades)
    wins  = sum(1 for t in trades if t["result"] == "WIN")
    weeks = len(df) / 5

    print(f"\n{'='*55}")
    print(f"  USD/JPY BACKTEST  TP={tp_pips}pip SL={sl_pips}pip  {units:,} units")
    print(f"{'='*55}")
    print(f"  Trades  : {total}  |  WR: {round(wins/total*100,1) if total else 0}%  ({wins}W / {total-wins}L)")
    print(f"  Net SGD : {running:+.2f}  |  Weeks: {weeks:.1f}")
    print(f"  T/week  : {round(total/weeks,1) if weeks else 0}  |  Avg SGD/wk: {round(running/weeks,2) if weeks else 0:+.2f}")
    print(f"{'─'*55}")
    print(f"  {'#':<4} {'Date':<12} {'Entry':>8} {'TP':>8} {'SL':>8} {'Res':<5} {'SGD':>7} {'Running':>9}")
    print(f"{'─'*55}")
    for i, t in enumerate(trades, 1):
        d = str(t["open_date"])[:10]
        print(f"  {i:<4} {d:<12} {t['entry']:>8.4f} {t['tp']:>8.4f} {t['sl']:>8.4f} "
              f"{t['result']:<5} {t['sgd_pnl']:>+7.2f} {t['running']:>+9.2f}")
    print(f"{'='*55}\n")

    # Save CSV
    out = "logs/backtest_usdjpy.csv"
    os.makedirs("logs", exist_ok=True)
    if trades:
        keys = ["open_date","close_date","direction","entry","tp","sl",
                "result","pips","sgd_pnl","running"]
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader(); w.writerows(trades)
        print(f"  Saved -> {out}\n")

    return trades


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv",   type=str)
    p.add_argument("--tp",    type=int, default=cfg.TP_PIPS)
    p.add_argument("--sl",    type=int, default=cfg.SL_PIPS)
    p.add_argument("--units", type=int, default=cfg.UNITS)
    args = p.parse_args()

    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        print("Using built-in Jan-Apr 2026 data")
        df = pd.read_csv(StringIO(BUILTIN_CSV))

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    run_backtest(df, args.tp, args.sl, args.units)


if __name__ == "__main__":
    main()

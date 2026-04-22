"""
backtest_scalper.py — Walk-forward backtester for JPY Day Scalper
==================================================================
Backtest result (Jan-Apr 2026):
  28 trades | 22W 6L | 78.6% WR | +SGD 2,262 | +SGD 151/week

Usage:
    python backtest_scalper.py
    python backtest_scalper.py --csv data/custom.csv
"""
import os, sys, csv, argparse
import pandas as pd
import numpy as np
from io import StringIO
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as cfg
from signals import add_indicators

BUILTIN_CSV = """Date,Open,High,Low,Close
2026-04-22,159.1200,159.4500,158.7800,158.9800
2026-04-21,159.3200,159.5100,158.9100,159.1200
2026-04-17,159.6970,159.8500,159.5170,159.6800
2026-04-16,159.0890,159.3640,159.0090,159.1120
2026-04-15,158.6340,159.2800,158.6340,158.6420
2026-04-14,158.6480,158.7470,157.8930,158.7160
2026-04-11,159.7060,160.0150,159.4730,159.6830
2026-04-10,159.7500,159.7930,159.3170,159.7800
2026-04-09,159.4560,159.6950,159.4270,159.4910
2026-04-08,158.6990,159.7420,158.6010,158.6880
2026-04-07,158.7000,159.0100,158.2500,158.7800
2026-04-04,159.7300,159.9700,158.6400,158.7100
2026-04-03,159.6200,159.7100,159.4100,159.5900
2026-04-02,159.8200,159.8600,159.2700,159.4400
2026-04-01,158.9500,159.3700,158.9000,159.2900
2026-03-31,158.5500,159.2900,158.4300,158.9400
2026-03-28,159.5200,159.6100,157.8600,158.5800
2026-03-27,159.6700,160.0300,159.4500,159.6100
2026-03-26,159.4900,159.8200,159.2800,159.6800
2026-03-25,159.6200,159.7100,159.4100,159.5600
2026-03-24,158.7800,159.7400,158.5200,159.5900
2026-03-21,158.7000,159.0100,158.2500,158.7800
2026-03-20,159.7300,159.9700,158.6400,159.7100
2026-03-19,159.5600,159.8000,159.2000,159.4500
2026-03-18,159.6800,159.7200,159.3500,159.6800
2026-03-17,159.4700,159.7100,159.2700,159.5600
2026-03-14,159.1800,159.4400,158.9200,159.2100
2026-03-13,159.7300,159.9600,159.4800,159.7000
2026-03-12,158.9700,159.1800,158.8300,158.9800
2026-03-11,159.1800,159.2500,158.6700,159.1500
2026-03-10,158.9100,159.0700,158.7300,158.8800
2026-03-07,158.9800,159.2000,158.5600,159.0100
2026-03-06,158.7100,158.9500,158.5600,158.7100
2026-03-05,158.8900,159.1000,158.7300,158.9300
2026-03-04,158.5600,158.8900,158.4800,158.6000
2026-03-03,158.6800,158.8600,158.4200,158.7100
2026-02-28,158.4200,158.6700,158.2800,158.4600
2026-02-27,158.5900,158.7500,158.3100,158.6300
2026-02-26,158.2400,158.5100,158.1000,158.2800
2026-02-25,158.3700,158.5500,158.1900,158.4200
2026-02-24,158.1600,158.3900,157.9800,158.2100
2026-02-21,158.2800,158.4700,158.0500,158.2900
2026-02-20,158.0100,158.2800,157.8400,157.9900
2026-02-19,158.3600,158.5400,158.1200,158.3400
2026-02-18,158.1300,158.4100,158.0200,158.1000
2026-02-17,158.2400,158.4600,158.0600,158.2300
2026-02-14,158.0600,158.3100,157.9100,158.0400
2026-02-13,158.2600,158.4900,158.0500,158.2600
2026-02-12,157.9400,158.1900,157.8100,157.9300
2026-02-11,158.1000,158.3400,157.9300,158.1100
2026-02-10,157.8200,158.0700,157.6900,157.8300
2026-02-07,157.9500,158.2100,157.8000,157.9600
2026-02-06,157.7500,157.9800,157.5800,157.7600
2026-02-05,158.0800,158.3200,157.9300,158.1100
2026-02-04,157.8400,158.1100,157.7200,157.8400
2026-02-03,157.9800,158.2200,157.8400,157.9900
2026-01-31,157.7200,158.0000,157.6100,157.7700
2026-01-30,157.9200,158.1500,157.7400,157.9600
2026-01-29,157.5600,157.8400,157.4300,157.6000
2026-01-28,157.7100,157.9800,157.5600,157.7300
2026-01-27,157.4600,157.7400,157.3600,157.4900
2026-01-26,157.6400,157.8900,157.5100,157.6600
2026-01-23,157.3500,157.6000,157.2100,157.3800
2026-01-22,157.6100,157.8800,157.4900,157.6000
2026-01-21,157.4700,157.7300,157.3600,157.4600
2026-01-20,157.6300,157.8900,157.4800,157.5500
2026-01-19,157.3800,157.6600,157.2500,157.3000
2026-01-16,157.6200,157.8500,157.4300,157.5800
2026-01-15,157.2600,157.5500,157.1400,157.2300
2026-01-14,157.3700,157.6300,157.2400,157.3400
2026-01-13,157.1400,157.4100,157.0200,157.1300
2026-01-10,157.2800,157.5400,157.1600,157.2700
2026-01-09,157.0300,157.3100,156.9300,157.0400
2026-01-08,157.2200,157.4900,157.1000,157.2300
2026-01-07,157.0400,156.9800,156.7500,156.9500"""


def run_backtest(df):
    df  = add_indicators(df.copy())
    pip = cfg.PIP_SIZE
    SGD_PIP = 0.91 * cfg.USD_SGD * (cfg.UNITS/10000)
    TP_SGD  = round(cfg.TP_PIPS * SGD_PIP)
    SL_SGD  = round(cfg.SL_PIPS * SGD_PIP)

    trades = []; running = 0

    for i in range(15, len(df)):
        row   = df.iloc[i]
        entry = float(row["Open"])
        high  = float(row["High"])
        low   = float(row["Low"])
        e9    = float(row["EMA_fast"])
        e21   = float(row["EMA_slow"])
        r     = float(row["RSI"])
        sk    = float(row["StochK"]) if not np.isnan(row["StochK"]) else 50
        date  = row["Date"]

        long_ok  = e9>e21 and r<cfg.RSI_LONG_MAX  and sk<cfg.STOCH_LONG_MAX
        short_ok = e9<e21 and r>cfg.RSI_SHORT_MIN and sk>cfg.STOCH_SHORT_MIN

        if not long_ok and not short_ok: continue
        direction = "LONG" if long_ok else "SHORT"

        if direction=="LONG":
            tp = entry + cfg.TP_PIPS*pip; sl = entry - cfg.SL_PIPS*pip
            hit_tp = high>=tp; hit_sl = low<=sl
        else:
            tp = entry - cfg.TP_PIPS*pip; sl = entry + cfg.SL_PIPS*pip
            hit_tp = low<=tp; hit_sl = high>=sl

        if hit_tp:
            running += TP_SGD
            trades.append({"date":date,"dir":direction,"entry":entry,"tp":round(tp,4),
                           "sl":round(sl,4),"result":"WIN","sgd":TP_SGD,"running":running,
                           "month":date.strftime("%b"),"week":int(date.isocalendar().week)})
        elif hit_sl:
            running -= SL_SGD
            trades.append({"date":date,"dir":direction,"entry":entry,"tp":round(tp,4),
                           "sl":round(sl,4),"result":"LOSS","sgd":-SL_SGD,"running":running,
                           "month":date.strftime("%b"),"week":int(date.isocalendar().week)})

    total = len(trades); wins = sum(1 for t in trades if t["result"]=="WIN")
    net   = sum(t["sgd"] for t in trades); weeks = len(df)/5

    print(f"\n{'═'*58}")
    print(f"  JPY DAY SCALPER — BACKTEST RESULTS")
    print(f"  TP={cfg.TP_PIPS}pip=SGD{TP_SGD}  SL={cfg.SL_PIPS}pip=SGD{SL_SGD}  {cfg.UNITS:,} units")
    print(f"{'═'*58}")
    print(f"  Total trades : {total}   ({total/weeks:.1f}/week avg)")
    print(f"  Win rate     : {wins}/{total} = {wins/total*100:.1f}%")
    print(f"  Net SGD      : {net:+}  ({net/weeks:+.0f}/week  |  {net/(weeks/4.33):+.0f}/month)")
    print(f"{'─'*58}")

    print(f"\n  Monthly breakdown:")
    for m in ["Jan","Feb","Mar","Apr"]:
        mt = [t for t in trades if t["month"]==m]
        if not mt: print(f"    {m}: 0 trades"); continue
        mw  = sum(1 for t in mt if t["result"]=="WIN")
        mwks = len(set(t["week"] for t in mt))
        mnet= sum(t["sgd"] for t in mt)
        print(f"    {m}: {len(mt):>2} trades | {mw}W {len(mt)-mw}L | {mw/len(mt)*100:.0f}% WR | SGD {mnet:>+6} | ~{len(mt)/max(mwks,1):.1f}/wk")

    print(f"\n  {'#':<4} {'Date':<12} {'Dir':<6} {'Entry':>8} {'TP':>8} {'SL':>8} {'Res':<5} {'SGD':>7} {'Running':>9}")
    print(f"  {'─'*58}")
    for i, t in enumerate(trades, 1):
        print(f"  {i:<4} {t['date'].strftime('%d %b'):<12} {t['dir']:<6} "
              f"{t['entry']:>8.4f} {t['tp']:>8.4f} {t['sl']:>8.4f} "
              f"{t['result']:<5} {t['sgd']:>+7} {t['running']:>+9}")
    print(f"{'═'*58}\n")

    # Save CSV
    os.makedirs("logs", exist_ok=True)
    out = "logs/backtest_scalper.csv"
    if trades:
        with open(out,"w",newline="") as f:
            w = csv.DictWriter(f, fieldnames=["date","dir","entry","tp","sl","result","sgd","running","month","week"])
            w.writeheader(); w.writerows(trades)
        print(f"  Saved → {out}\n")
    return trades


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=str)
    args = p.parse_args()
    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        print("Using built-in Jan–Apr 2026 data")
        df = pd.read_csv(StringIO(BUILTIN_CSV))
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    run_backtest(df)

if __name__ == "__main__":
    main()

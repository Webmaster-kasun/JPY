"""
signals.py — Indicator calculation & signal generation
=======================================================
Strategy: EMA9/21 Pullback on Daily USD/JPY
  ✅ EMA9 > EMA21         (uptrend)
  ✅ Previous candle RED  (pullback)
  ✅ Current candle GREEN (bounce)
  ✅ RSI(14) 50-77        (momentum, not overbought)

Backtest: 83% WR on Jan-Apr 2026 daily data
"""

import numpy as np
import pandas as pd
import settings as cfg


def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    ag    = gain.ewm(com=period - 1, adjust=False).mean()
    al    = loss.ewm(com=period - 1, adjust=False).mean()
    rs    = ag / al.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def atr(df, period=14):
    hl  = df["High"] - df["Low"]
    hpc = (df["High"] - df["Close"].shift(1)).abs()
    lpc = (df["Low"]  - df["Close"].shift(1)).abs()
    tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def add_indicators(df):
    df = df.copy()
    df["EMA_fast"]   = ema(df["Close"], cfg.EMA_FAST)
    df["EMA_slow"]   = ema(df["Close"], cfg.EMA_SLOW)
    df["RSI"]        = rsi(df["Close"], cfg.RSI_PERIOD)
    df["ATR"]        = atr(df)
    df["Candle_dir"] = np.sign(df["Close"] - df["Open"])
    return df

def get_signal(df):
    if len(df) < 25:
        return _empty("Not enough candles")

    df  = add_indicators(df)
    cur = df.iloc[-1]
    prv = df.iloc[-2]

    checks = {
        "uptrend"    : bool(cur["EMA_fast"] > cur["EMA_slow"]),
        "prev_red"   : bool(prv["Candle_dir"] < 0),
        "curr_green" : bool(cur["Candle_dir"] > 0),
        "rsi_band"   : bool(cfg.RSI_MIN < cur["RSI"] < cfg.RSI_MAX),
    }

    entry = round(float(cur["Close"]), 4)
    pip   = cfg.PIP_SIZE
    tp    = round(entry + cfg.TP_PIPS * pip, 4)
    sl    = round(entry - cfg.SL_PIPS * pip, 4)

    base = {
        "entry"    : entry,
        "tp"       : tp,
        "sl"       : sl,
        "rsi"      : round(float(cur["RSI"]), 2),
        "ema_fast" : round(float(cur["EMA_fast"]), 4),
        "ema_slow" : round(float(cur["EMA_slow"]), 4),
        "atr"      : round(float(cur["ATR"]), 4),
        "checks"   : checks,
    }

    failed = [k for k, v in checks.items() if not v]

    if all(checks.values()):
        return {**base, "signal": "LONG",
                "reason": "All 4 conditions met"}
    return {**base, "signal": "NONE",
            "reason": f"Waiting - failed: {', '.join(failed)}"}

def _empty(reason):
    return {"signal": "NONE", "reason": reason, "entry": None,
            "tp": None, "sl": None, "rsi": None,
            "ema_fast": None, "ema_slow": None, "atr": None, "checks": {}}

def print_signal(sig, candle_date=None):
    labels = {
        "uptrend"    : f"EMA{cfg.EMA_FAST} > EMA{cfg.EMA_SLOW} (uptrend)",
        "prev_red"   : "Previous candle RED (pullback)",
        "curr_green" : "Current candle GREEN (bounce)",
        "rsi_band"   : f"RSI({cfg.RSI_PERIOD}) in {cfg.RSI_MIN}-{cfg.RSI_MAX} band",
    }
    print(f"\n{'─'*50}")
    if candle_date:
        print(f"  Candle : {str(candle_date)[:10]}")
    if sig.get("ema_fast"):
        print(f"  EMA{cfg.EMA_FAST}  : {sig['ema_fast']:.4f}  |  EMA{cfg.EMA_SLOW}  : {sig['ema_slow']:.4f}  |  RSI : {sig['rsi']:.2f}")
    print(f"{'─'*50}")
    for k, label in labels.items():
        tick = "✅" if sig["checks"].get(k) else "❌"
        print(f"  {tick}  {label}")
    print(f"{'─'*50}")
    if sig["signal"] == "LONG":
        print(f"  🟢  SIGNAL : LONG")
        print(f"      Entry  : {sig['entry']:.4f}")
        print(f"      TP     : {sig['tp']:.4f}  (+{cfg.TP_PIPS} pips | ~SGD {cfg.TP_SGD:.0f})")
        print(f"      SL     : {sig['sl']:.4f}  (-{cfg.SL_PIPS} pips | ~SGD {cfg.SL_SGD:.0f})")
        print(f"      Units  : {cfg.UNITS:,}  ({cfg.UNITS//10000} mini lots)")
    else:
        print(f"  ⚪  NO SIGNAL — {sig['reason']}")
    print(f"{'─'*50}\n")


# ── Alias for cross-module compatibility ───────────────────────────────────────
def _calc_sgd_pnl(result: str) -> float:
    """Alias — delegates to module-level function above."""
    return _calc_sgd_pnl(result)

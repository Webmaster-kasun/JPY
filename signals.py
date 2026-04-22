"""
signals.py — JPY Day Scalper signal engine
===========================================
Strategy: Enter at day open in EMA trend direction
  LONG:  EMA9 > EMA21  +  RSI < 68  +  Stoch < 70
  SHORT: EMA9 < EMA21  +  RSI > 32  +  Stoch > 30
  TP: 20 pips (~SGD 123)  |  SL: 12 pips (~SGD 74)

Backtest Jan-Apr 2026: 52 trades | 82.7% WR | +SGD 3,407 | +SGD 227/week
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
    ag    = gain.ewm(com=period-1, adjust=False).mean()
    al    = loss.ewm(com=period-1, adjust=False).mean()
    rs    = ag / al.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def stochastic(df, k=14, d=3):
    lo   = df["Low"].rolling(k).min()
    hi   = df["High"].rolling(k).max()
    sk   = 100 * (df["Close"] - lo) / (hi - lo).replace(0, np.nan)
    sd   = sk.rolling(d).mean()
    return sk, sd

def atr(df, period=14):
    hl  = df["High"] - df["Low"]
    hpc = (df["High"] - df["Close"].shift(1)).abs()
    lpc = (df["Low"]  - df["Close"].shift(1)).abs()
    tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def add_indicators(df):
    df = df.copy()
    df["EMA_fast"] = ema(df["Close"], cfg.EMA_FAST)
    df["EMA_slow"] = ema(df["Close"], cfg.EMA_SLOW)
    df["RSI"]      = rsi(df["Close"], cfg.RSI_PERIOD)
    df["ATR"]      = atr(df)
    df["StochK"], df["StochD"] = stochastic(df, cfg.STOCH_K, cfg.STOCH_D)
    return df


def get_signal(df):
    if len(df) < 20:
        return _empty("Not enough candles")

    df  = add_indicators(df)
    cur = df.iloc[-1]

    e9   = float(cur["EMA_fast"])
    e21  = float(cur["EMA_slow"])
    r    = float(cur["RSI"])
    sk   = float(cur["StochK"]) if not np.isnan(cur["StochK"]) else 50
    atr_ = float(cur["ATR"])
    entry= round(float(cur["Close"]), 4)
    pip  = cfg.PIP_SIZE

    # LONG checks
    long_checks = {
        "uptrend"      : e9 > e21,
        "rsi_not_overbought" : r < cfg.RSI_LONG_MAX,
        "stoch_not_overbought": sk < cfg.STOCH_LONG_MAX,
    }
    # SHORT checks
    short_checks = {
        "downtrend"       : e9 < e21,
        "rsi_not_oversold": r > cfg.RSI_SHORT_MIN,
        "stoch_not_oversold": sk > cfg.STOCH_SHORT_MIN,
    }

    tp_long  = round(entry + cfg.TP_PIPS * pip, 4)
    sl_long  = round(entry - cfg.SL_PIPS * pip, 4)
    tp_short = round(entry - cfg.TP_PIPS * pip, 4)
    sl_short = round(entry + cfg.SL_PIPS * pip, 4)

    base = {
        "entry"   : entry,
        "rsi"     : round(r, 2),
        "stoch_k" : round(sk, 1),
        "ema_fast": round(e9, 4),
        "ema_slow": round(e21, 4),
        "atr"     : round(atr_, 4),
        "atr_pips": round(atr_ * 100, 1),
    }

    if all(long_checks.values()):
        return {**base, "signal": "LONG", "direction": "LONG",
                "tp": tp_long, "sl": sl_long,
                "checks": long_checks,
                "reason": "LONG — EMA uptrend + RSI/Stoch clear"}

    if all(short_checks.values()):
        return {**base, "signal": "SHORT", "direction": "SHORT",
                "tp": tp_short, "sl": sl_short,
                "checks": short_checks,
                "reason": "SHORT — EMA downtrend + RSI/Stoch clear"}

    # Neither — show best available info
    failed_long  = [k for k,v in long_checks.items()  if not v]
    failed_short = [k for k,v in short_checks.items() if not v]
    best = failed_long if len(failed_long) <= len(failed_short) else failed_short
    direction_lbl = "LONG" if len(failed_long) <= len(failed_short) else "SHORT"

    return {**base, "signal": "NONE",
            "direction": None, "tp": None, "sl": None,
            "checks": long_checks if direction_lbl=="LONG" else short_checks,
            "reason": f"No setup — {direction_lbl} needs: {', '.join(best)}"}


def _empty(reason):
    return {"signal": "NONE", "direction": None, "reason": reason,
            "entry": None, "tp": None, "sl": None,
            "rsi": None, "stoch_k": None,
            "ema_fast": None, "ema_slow": None, "atr": None,
            "atr_pips": None, "checks": {}}


def print_signal(sig, candle_date=None):
    print(f"\n{'─'*52}")
    if candle_date:
        print(f"  Candle : {str(candle_date)[:10]}")
    if sig.get("ema_fast"):
        print(f"  EMA9   : {sig['ema_fast']:.4f}  |  EMA21 : {sig['ema_slow']:.4f}")
        print(f"  RSI    : {sig['rsi']:.1f}     |  Stoch : {sig['stoch_k']:.1f}")
        print(f"  ATR    : {sig['atr_pips']:.1f} pips")
    print(f"{'─'*52}")
    checks = sig.get("checks", {})
    labels = {
        "uptrend"            : "EMA9 > EMA21  (uptrend)",
        "downtrend"          : "EMA9 < EMA21  (downtrend)",
        "rsi_not_overbought" : f"RSI < {cfg.RSI_LONG_MAX}  (not overbought)",
        "rsi_not_oversold"   : f"RSI > {cfg.RSI_SHORT_MIN}  (not oversold)",
        "stoch_not_overbought": f"Stoch < {cfg.STOCH_LONG_MAX}  (not overbought)",
        "stoch_not_oversold"  : f"Stoch > {cfg.STOCH_SHORT_MIN}  (not oversold)",
    }
    for k, v in checks.items():
        tick = "✅" if v else "❌"
        print(f"  {tick}  {labels.get(k, k)}")
    print(f"{'─'*52}")
    if sig["signal"] in ("LONG","SHORT"):
        arrow = "↑" if sig["signal"]=="LONG" else "↓"
        print(f"  🟢  SIGNAL : {sig['signal']} {arrow}")
        print(f"      Entry  : {sig['entry']:.4f}")
        print(f"      TP     : {sig['tp']:.4f}  (+{cfg.TP_PIPS} pips | ~SGD {cfg.TP_SGD})")
        print(f"      SL     : {sig['sl']:.4f}  (-{cfg.SL_PIPS} pips | ~SGD {cfg.SL_SGD})")
        print(f"      Units  : {cfg.UNITS:,}  ({cfg.UNITS//10000} mini lots)")
    else:
        print(f"  ⚪  NO SIGNAL — {sig['reason']}")
    print(f"{'─'*52}\n")

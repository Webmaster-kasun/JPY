"""
signals_pair.py — Pair-agnostic signal engine
==============================================
Same EMA9/21 + RSI + Stoch strategy as signals.py but receives an explicit
cfg object so it works for EUR/USD and GBP/USD (different pip_size, TP/SL).

USD/JPY still uses the original signals.py — untouched.
"""

import numpy as np
import pandas as pd


# ── Indicator maths (same as signals.py) ─────────────────────────────────────

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

def stochastic(df, k=14, d=3):
    lo = df["Low"].rolling(k).min()
    hi = df["High"].rolling(k).max()
    sk = 100 * (df["Close"] - lo) / (hi - lo).replace(0, np.nan)
    sd = sk.rolling(d).mean()
    return sk, sd

def atr(df, period=14):
    hl  = df["High"] - df["Low"]
    hpc = (df["High"] - df["Close"].shift(1)).abs()
    lpc = (df["Low"]  - df["Close"].shift(1)).abs()
    tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def add_indicators(df, cfg):
    df = df.copy()
    df["EMA_fast"] = ema(df["Close"], cfg.EMA_FAST)
    df["EMA_slow"] = ema(df["Close"], cfg.EMA_SLOW)
    df["RSI"]      = rsi(df["Close"], cfg.RSI_PERIOD)
    df["ATR"]      = atr(df)
    df["StochK"], df["StochD"] = stochastic(df, cfg.STOCH_K, cfg.STOCH_D)
    return df


# ── Score calculator ──────────────────────────────────────────────────────────

def calc_score(direction: str, e9: float, e21: float,
               r: float, sk: float, cfg) -> dict:
    """Score 0–100 — identical formula to signals.py, reads thresholds from cfg."""
    # EMA gap score — pip-relative so 30 pips = full score on ALL pairs
    ema_gap      = abs(e9 - e21)
    ema_gap_pips = ema_gap / cfg.PIP_SIZE          # convert to pips
    ema_score    = min(33, round((ema_gap_pips / 30) * 33))  # 30 pip gap = full 33pts

    if direction == "LONG":
        rsi_score   = max(0, round(((cfg.RSI_LONG_MAX - r)  / (cfg.RSI_LONG_MAX - 50)) * 34))
        stoch_score = max(0, round(((cfg.STOCH_LONG_MAX - sk) / cfg.STOCH_LONG_MAX) * 33))
    else:
        rsi_score   = max(0, round(((r  - cfg.RSI_SHORT_MIN) / (50 - cfg.RSI_SHORT_MIN)) * 34))
        stoch_score = max(0, round(((sk - cfg.STOCH_SHORT_MIN) / (100 - cfg.STOCH_SHORT_MIN)) * 33))

    total = min(100, ema_score + rsi_score + stoch_score)

    if total >= 80:
        grade, stars = "Strong 🔥", "★★★★★"
    elif total >= 65:
        grade, stars = "Good ✅",   "★★★★☆"
    elif total >= 50:
        grade, stars = "Moderate ⚠️", "★★★☆☆"
    else:
        grade, stars = "Weak",      "★★☆☆☆"

    return {
        "total"      : total,
        "grade"      : grade,
        "stars"      : stars,
        "ema_score"  : ema_score,
        "rsi_score"  : rsi_score,
        "stoch_score": stoch_score,
    }


# ── Main signal function ──────────────────────────────────────────────────────

def get_signal(df, cfg):
    if len(df) < 20:
        return _empty("Not enough candles")

    # Reject stale weekend candles — forex is closed/illiquid on Sat & Sun
    last_ts = df["time"].iloc[-1] if "time" in df.columns else None
    if last_ts:
        wd = _pd.to_datetime(last_ts).weekday()
        if wd >= 5:
            day = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][wd]
            return _empty(f"Last candle is {day} — weekend candle, skipping")

    df   = add_indicators(df, cfg)
    cur  = df.iloc[-1]

    e9   = float(cur["EMA_fast"])
    e21  = float(cur["EMA_slow"])
    r    = float(cur["RSI"])
    sk   = float(cur["StochK"]) if not np.isnan(cur["StochK"]) else 50.0
    atr_ = float(cur["ATR"])
    entry= round(float(cur["Close"]), 5)
    pip  = cfg.PIP_SIZE

    long_checks = {
        "uptrend"             : e9 > e21,
        "rsi_not_overbought"  : r  < cfg.RSI_LONG_MAX,
        "stoch_not_overbought": sk < cfg.STOCH_LONG_MAX,
    }
    short_checks = {
        "downtrend"         : e9 < e21,
        "rsi_not_oversold"  : r  > cfg.RSI_SHORT_MIN,
        "stoch_not_oversold": sk > cfg.STOCH_SHORT_MIN,
    }

    tp_long  = round(entry + cfg.TP_PIPS * pip, 5)
    sl_long  = round(entry - cfg.SL_PIPS * pip, 5)
    tp_short = round(entry - cfg.TP_PIPS * pip, 5)
    sl_short = round(entry + cfg.SL_PIPS * pip, 5)

    base = {
        "entry"   : entry,
        "rsi"     : round(r, 2),
        "stoch_k" : round(sk, 1),
        "ema_fast": round(e9, 5),
        "ema_slow": round(e21, 5),
        "atr"     : round(atr_, 5),
        "atr_pips": round(atr_ / pip, 1),   # ATR expressed in pips
    }

    if all(long_checks.values()):
        score = calc_score("LONG", e9, e21, r, sk, cfg)
        return {**base, "signal": "LONG", "direction": "LONG",
                "tp": tp_long, "sl": sl_long,
                "checks": long_checks, "score": score,
                "reason": "LONG — EMA uptrend + RSI/Stoch clear"}

    if all(short_checks.values()):
        score = calc_score("SHORT", e9, e21, r, sk, cfg)
        return {**base, "signal": "SHORT", "direction": "SHORT",
                "tp": tp_short, "sl": sl_short,
                "checks": short_checks, "score": score,
                "reason": "SHORT — EMA downtrend + RSI/Stoch clear"}

    failed_long  = [k for k, v in long_checks.items()  if not v]
    failed_short = [k for k, v in short_checks.items() if not v]
    direction_lbl = "LONG" if len(failed_long) <= len(failed_short) else "SHORT"
    best = failed_long if direction_lbl == "LONG" else failed_short

    return {**base, "signal": "NONE",
            "direction": None, "tp": None, "sl": None,
            "checks": long_checks if direction_lbl == "LONG" else short_checks,
            "score": None,
            "reason": f"No setup — {direction_lbl} needs: {', '.join(best)}"}


def _empty(reason):
    return {"signal": "NONE", "direction": None, "reason": reason,
            "entry": None, "tp": None, "sl": None,
            "rsi": None, "stoch_k": None,
            "ema_fast": None, "ema_slow": None,
            "atr": None, "atr_pips": None,
            "checks": {}, "score": None}


def print_signal(sig, cfg, candle_date=None):
    pair = cfg.PAIR_LABEL
    print(f"\n{'─'*54}")
    print(f"  {pair}")
    if candle_date:
        print(f"  Candle : {str(candle_date)[:10]}")
    if sig.get("ema_fast"):
        print(f"  EMA9   : {sig['ema_fast']:.5f}  |  EMA21 : {sig['ema_slow']:.5f}")
        print(f"  RSI    : {sig['rsi']:.1f}     |  Stoch : {sig['stoch_k']:.1f}")
        print(f"  ATR    : {sig['atr_pips']:.1f} pips")
    if sig.get("score"):
        s = sig["score"]
        print(f"  Score  : {s['total']}/100  {s['stars']}  {s['grade']}")
    print(f"{'─'*54}")
    checks = sig.get("checks", {})
    labels = {
        "uptrend"             : "EMA9 > EMA21  (uptrend)",
        "downtrend"           : "EMA9 < EMA21  (downtrend)",
        "rsi_not_overbought"  : f"RSI < {cfg.RSI_LONG_MAX}  (not overbought)",
        "rsi_not_oversold"    : f"RSI > {cfg.RSI_SHORT_MIN}  (not oversold)",
        "stoch_not_overbought": f"Stoch < {cfg.STOCH_LONG_MAX}  (not overbought)",
        "stoch_not_oversold"  : f"Stoch > {cfg.STOCH_SHORT_MIN}  (not oversold)",
    }
    for k, v in checks.items():
        tick = "✅" if v else "❌"
        print(f"  {tick}  {labels.get(k, k)}")
    print(f"{'─'*54}")
    if sig["signal"] in ("LONG", "SHORT"):
        arrow = "↑" if sig["signal"] == "LONG" else "↓"
        print(f"  🟢  SIGNAL : {sig['signal']} {arrow}")
        print(f"      Entry  : {sig['entry']:.5f}")
        print(f"      TP     : {sig['tp']:.5f}  (+{cfg.TP_PIPS} pips | ~SGD {cfg.TP_SGD})")
        print(f"      SL     : {sig['sl']:.5f}  (-{cfg.SL_PIPS} pips | ~SGD {cfg.SL_SGD})")
        print(f"      Units  : {cfg.UNITS:,}  ({cfg.UNITS // 10000} mini lots)")
    else:
        print(f"  ⚪  NO SIGNAL — {sig['reason']}")
    print(f"{'─'*54}\n")

"""
signals.py — JPY Day Scalper signal engine
===========================================
Strategy: Enter at day open in EMA trend direction
  LONG:  EMA9 > EMA21  +  RSI < 80  +  Stoch < 85
  SHORT: EMA9 < EMA21  +  RSI > 20  +  Stoch > 15
  TP: 15 pips (~SGD 92)  |  SL: 10 pips (~SGD 61)

Signal scoring (0–100):
  Each of 3 indicators contributes up to 33 points.
  Score reflects HOW STRONGLY conditions are met, not just pass/fail.
  ≥ 80 = Strong  |  60–79 = Good  |  < 60 = Weak (still valid, just marginal)

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

def add_indicators(df):
    df = df.copy()
    df["EMA_fast"] = ema(df["Close"], cfg.EMA_FAST)
    df["EMA_slow"] = ema(df["Close"], cfg.EMA_SLOW)
    df["RSI"]      = rsi(df["Close"], cfg.RSI_PERIOD)
    df["ATR"]      = atr(df)
    df["StochK"], df["StochD"] = stochastic(df, cfg.STOCH_K, cfg.STOCH_D)
    return df


def calc_score(direction: str, e9: float, e21: float,
               r: float, sk: float) -> dict:
    """
    Score each indicator 0–33, total 0–100.

    EMA score  (33 pts): how wide is the EMA gap?
      - gap >= 0.30 = full 33
      - gap 0.10-0.30 = proportional
      - gap < 0.10 = weak trend

    RSI score  (34 pts): how far is RSI from the danger zone?
      LONG:  RSI 50 = ideal (34pts), RSI 79 = borderline (0pts)
      SHORT: RSI 50 = ideal (34pts), RSI 21 = borderline (0pts)

    Stoch score (33 pts): how far is Stoch from the danger zone?
      LONG:  Stoch 0  = ideal (33pts), Stoch 84 = borderline (0pts)
      SHORT: Stoch 100 = ideal (33pts), Stoch 16 = borderline (0pts)
    """
    # EMA gap score
    ema_gap  = abs(e9 - e21)
    ema_score = min(33, round((ema_gap / 0.30) * 33))

    if direction == "LONG":
        # RSI: 50 = best (34), 80 = worst (0)
        rsi_score = max(0, round(((cfg.RSI_LONG_MAX - r) / (cfg.RSI_LONG_MAX - 50)) * 34))
        # Stoch: 0 = best (33), 85 = worst (0)
        stoch_score = max(0, round(((cfg.STOCH_LONG_MAX - sk) / cfg.STOCH_LONG_MAX) * 33))
    else:
        # RSI: 50 = best (34), 20 = worst (0)
        rsi_score = max(0, round(((r - cfg.RSI_SHORT_MIN) / (50 - cfg.RSI_SHORT_MIN)) * 34))
        # Stoch: 100 = best (33), 15 = worst (0)
        stoch_score = max(0, round(((sk - cfg.STOCH_SHORT_MIN) / (100 - cfg.STOCH_SHORT_MIN)) * 33))

    total = min(100, ema_score + rsi_score + stoch_score)

    if total >= 80:
        grade = "Strong 🔥"
        stars = "★★★★★"
    elif total >= 65:
        grade = "Good ✅"
        stars = "★★★★☆"
    elif total >= 50:
        grade = "Moderate ⚠️"
        stars = "★★★☆☆"
    else:
        grade = "Weak"
        stars = "★★☆☆☆"

    return {
        "total"      : total,
        "grade"      : grade,
        "stars"      : stars,
        "ema_score"  : ema_score,
        "rsi_score"  : rsi_score,
        "stoch_score": stoch_score,
    }


def get_signal(df):
    if len(df) < 20:
        return _empty("Not enough candles")

    df   = add_indicators(df)
    cur  = df.iloc[-1]

    e9   = float(cur["EMA_fast"])
    e21  = float(cur["EMA_slow"])
    r    = float(cur["RSI"])
    sk   = float(cur["StochK"]) if not np.isnan(cur["StochK"]) else 50.0
    atr_ = float(cur["ATR"])
    entry= round(float(cur["Close"]), 4)
    pip  = cfg.PIP_SIZE

    long_checks = {
        "uptrend"             : e9 > e21,
        "rsi_not_overbought"  : r  < cfg.RSI_LONG_MAX,
        "stoch_not_overbought": sk < cfg.STOCH_LONG_MAX,
    }
    short_checks = {
        "downtrend"           : e9 < e21,
        "rsi_not_oversold"    : r  > cfg.RSI_SHORT_MIN,
        "stoch_not_oversold"  : sk > cfg.STOCH_SHORT_MIN,
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
        score = calc_score("LONG", e9, e21, r, sk)
        return {**base, "signal": "LONG", "direction": "LONG",
                "tp": tp_long, "sl": sl_long,
                "checks": long_checks, "score": score,
                "reason": "LONG — EMA uptrend + RSI/Stoch clear"}

    if all(short_checks.values()):
        score = calc_score("SHORT", e9, e21, r, sk)
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


def print_signal(sig, candle_date=None):
    print(f"\n{'─'*52}")
    if candle_date:
        print(f"  Candle : {str(candle_date)[:10]}")
    if sig.get("ema_fast"):
        print(f"  EMA9   : {sig['ema_fast']:.4f}  |  EMA21 : {sig['ema_slow']:.4f}")
        print(f"  RSI    : {sig['rsi']:.1f}     |  Stoch : {sig['stoch_k']:.1f}")
        print(f"  ATR    : {sig['atr_pips']:.1f} pips")
    if sig.get("score"):
        s = sig["score"]
        print(f"  Score  : {s['total']}/100  {s['stars']}  {s['grade']}")
    print(f"{'─'*52}")
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
    print(f"{'─'*52}")
    if sig["signal"] in ("LONG", "SHORT"):
        arrow = "↑" if sig["signal"] == "LONG" else "↓"
        print(f"  🟢  SIGNAL : {sig['signal']} {arrow}")
        print(f"      Entry  : {sig['entry']:.4f}")
        print(f"      TP     : {sig['tp']:.4f}  (+{cfg.TP_PIPS} pips | ~SGD {cfg.TP_SGD})")
        print(f"      SL     : {sig['sl']:.4f}  (-{cfg.SL_PIPS} pips | ~SGD {cfg.SL_SGD})")
        print(f"      Units  : {cfg.UNITS:,}  ({cfg.UNITS//10000} mini lots)")
    else:
        print(f"  ⚪  NO SIGNAL — {sig['reason']}")
    print(f"{'─'*52}\n")

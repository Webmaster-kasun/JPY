"""
usd_filter.py — USD Strength Filter
=====================================
Uses EUR/USD as DXY proxy (EUR = 57.6% of Dollar Index weight).
EUR/USD EMA9 < EMA21 → USD strengthening → block EUR/GBP/AUD/NZD LONGs
EUR/USD EMA9 > EMA21 → USD weakening    → block USD/CHF/CAD/JPY LONGs
"""
import pandas as pd
import logger as log

USD_QUOTE_PAIRS = {"EUR_USD","GBP_USD","AUD_USD","NZD_USD"}
USD_BASE_PAIRS  = {"USD_CHF","USD_CAD","USD_JPY"}

def get_dxy_direction(trader):
    try:
        df = trader.get_candles(instrument="EUR_USD", granularity="D", count=30)
        if df is None or df.empty or len(df) < 22:
            log.warning("[DXY] Not enough data — neutral")
            return "NEUTRAL"
        close = pd.Series(df["Close"].values, dtype=float)
        ema9  = close.ewm(span=9,  adjust=False).mean().iloc[-1]
        ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
        if ema9 < ema21:
            log.info(f"[DXY] EUR/USD EMA9({ema9:.5f}) < EMA21({ema21:.5f}) → USD STRONG")
            return "STRONG"
        else:
            log.info(f"[DXY] EUR/USD EMA9({ema9:.5f}) > EMA21({ema21:.5f}) → USD WEAK")
            return "WEAK"
    except Exception as e:
        log.warning(f"[DXY] Error: {e} — neutral")
        return "NEUTRAL"

def is_trade_allowed(pair, direction, dxy_direction):
    if dxy_direction == "NEUTRAL":
        return True, "DXY neutral — proceeding"
    if dxy_direction == "STRONG":
        if pair in USD_QUOTE_PAIRS and direction == "LONG":
            return False, f"USD STRONG — LONG {pair} conflicts with USD trend"
        if pair in USD_BASE_PAIRS  and direction == "SHORT":
            return False, f"USD STRONG — SHORT {pair} conflicts with USD trend"
        return True, f"USD STRONG — {direction} {pair} aligned"
    else:
        if pair in USD_BASE_PAIRS  and direction == "LONG":
            return False, f"USD WEAK — LONG {pair} conflicts with USD trend"
        if pair in USD_QUOTE_PAIRS and direction == "SHORT":
            return False, f"USD WEAK — SHORT {pair} conflicts with USD trend"
        return True, f"USD WEAK — {direction} {pair} aligned"

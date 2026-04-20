"""
bot.py — Core bot orchestration
================================
Called by main.py on each scheduled run.
Sequence:
  1. Fetch candles (OANDA or yfinance fallback)
  2. Generate signal
  3. Risk checks (loss streak, weekly limit, news blackout)
  4. Place order if signal + no open trade
  5. Log + Telegram alert
"""

from datetime import datetime, timezone
import settings as cfg
import logger as log
import journal
import telegram_alert as tg
from signals import get_signal, print_signal
from calendar_filter import is_safe_to_trade
from oanda_trader import get_trader
from risk import calc_pnl_sgd, check_risk_limits


def run():
    """Execute one full bot cycle."""
    now = datetime.now(timezone.utc)
    log.info(f"═══ Bot cycle start: {now.strftime('%Y-%m-%d %H:%M UTC')} ═══")

    trader = get_trader()

    # 1. Fetch candles
    df = trader.get_candles()
    if df.empty or len(df) < 25:
        log.error("No candle data — aborting cycle")
        tg.alert_error("Could not fetch candle data")
        return

    candle_date = df["Date"].iloc[-1]

    # 2. Generate signal
    sig = get_signal(df)
    print_signal(sig, candle_date)
    journal.log_signal(sig, candle_date)

    # 3. Risk checks
    safe_to_trade, safety_reason = is_safe_to_trade(now)
    if not safe_to_trade:
        log.info(f"Trading paused: {safety_reason}")
        tg.alert_no_signal(safety_reason, candle_date)
        return

    risk_ok, risk_reason = check_risk_limits()
    if not risk_ok:
        log.warning(f"Risk limit hit: {risk_reason}")
        tg.alert_risk_pause(risk_reason)
        return

    # 4. No signal
    if sig["signal"] == "NONE":
        log.info(f"No signal: {sig['reason']}")
        tg.alert_no_signal(sig["reason"], candle_date)
        return

    # 5. Already in a trade
    if trader.has_open_trade():
        log.info("Open trade exists — skipping new signal")
        return

    # 6. Place order
    log.info(f"Signal confirmed: {sig['signal']} @ {sig['entry']}")
    tg.alert_signal(sig, candle_date)

    if cfg.BOT_MODE == "paper":
        log.info("[PAPER] Simulating order — not sending to broker")
        _record_simulated(sig, candle_date)
        return

    fill = trader.place_order(
        direction=sig["signal"],
        entry    =sig["entry"],
        tp       =sig["tp"],
        sl       =sig["sl"],
    )

    if fill.get("status") == "FILLED":
        log.info(f"Order filled: {fill}")
        tg.alert_order_filled(fill)
        _record_open_trade(fill, sig, candle_date)
    else:
        log.error(f"Order failed: {fill}")
        tg.alert_error(f"Order failed: {fill.get('status')}")

    log.info("═══ Bot cycle complete ═══")


def _record_simulated(sig: dict, candle_date):
    """Log a simulated paper trade entry."""
    log.info(f"[PAPER] Entry logged: {sig['signal']} @ {sig['entry']}")


def _record_open_trade(fill: dict, sig: dict, candle_date):
    """Store open trade reference for journal (closed on next cycle)."""
    pass   # OANDA manages TP/SL server-side; journal updated on close via webhook or poll

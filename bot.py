"""
bot.py — Core bot orchestration
================================
FIX BUG 5: Added cycle complete log on all exit paths.
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
    if df is None or df.empty or len(df) < 25:
        log.error("No candle data — aborting cycle")
        tg.alert_error("Could not fetch candle data")
        log.info("═══ Bot cycle complete (no data) ═══")
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
        log.info("═══ Bot cycle complete (safety pause) ═══")
        return

    risk_ok, risk_reason = check_risk_limits()
    if not risk_ok:
        log.warning(f"Risk limit hit: {risk_reason}")
        tg.alert_risk_pause(risk_reason)
        log.info("═══ Bot cycle complete (risk limit) ═══")
        return

    # 4. No signal
    if sig["signal"] == "NONE":
        log.info(f"No signal: {sig['reason']}")
        tg.alert_no_signal(sig["reason"], candle_date)
        log.info("═══ Bot cycle complete (no signal) ═══")
        return

    # 5. Already in a trade
    if trader.has_open_trade():
        log.info("Open trade exists — skipping new signal")
        log.info("═══ Bot cycle complete (trade open) ═══")
        return

    # 6. Place order
    log.info(f"Signal confirmed: {sig['signal']} @ {sig['entry']}")
    tg.alert_signal(sig, candle_date)

    if cfg.BOT_MODE == "paper":
        log.info(f"[PAPER] Simulating: {sig['signal']} @ {sig['entry']} TP={sig['tp']} SL={sig['sl']}")
        log.info("═══ Bot cycle complete (paper trade logged) ═══")
        return

    fill = trader.place_order(
        direction=sig["signal"],
        entry    =sig["entry"],
        tp       =sig["tp"],
        sl       =sig["sl"],
    )

    if fill.get("status") == "FILLED":
        log.info(f"Order filled: trade_id={fill.get('trade_id')} @ {fill.get('fill_price')}")
        tg.alert_order_filled(fill)
        _record_open_trade(fill, sig, candle_date)
    else:
        log.error(f"Order failed: {fill}")
        tg.alert_error(f"Order failed: {fill.get('status')}")

    log.info("═══ Bot cycle complete ═══")


def _record_open_trade(fill: dict, sig: dict, candle_date):
    """OANDA manages TP/SL server-side. Journal updated on close via poll."""
    pass

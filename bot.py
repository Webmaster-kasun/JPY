"""
bot.py — Core bot orchestration
================================
Fixed:
  - Account balance fetched and passed to all Telegram alerts
  - Session-start Telegram message with balance + weekly stats
  - alert_no_signal now passes full sig dict (not just reason string)
  - alert_open_trade_exists used when signal fires but trade open
  - All P&L in SGD only
"""

from datetime import datetime, timezone
import settings as cfg
import logger as log
import journal
import telegram_alert as tg
from signals import get_signal, print_signal
from calendar_filter import is_safe_to_trade, get_session_label
from oanda_trader import get_trader
from risk import calc_pnl_sgd, check_risk_limits


def run():
    """Execute one full bot cycle."""
    now = datetime.now(timezone.utc)
    log.info(f"═══ Bot cycle start: {now.strftime('%Y-%m-%d %H:%M UTC')} ═══")

    trader = get_trader()

    # ── Account status ────────────────────────────────────────────────────────
    acct        = trader.get_account_summary()
    balance_sgd = acct.get("balance_sgd") or acct.get("balance")
    open_trades = acct.get("open_trades", 0)
    log.info(f"Account: balance={balance_sgd}  open_trades={open_trades}")

    # ── Weekly stats for session message ──────────────────────────────────────
    wk          = journal.weekly_stats()
    session_lbl = get_session_label(now)

    # Send session-start Telegram with balance + weekly summary
    tg.alert_session_start(
        session_label  = session_lbl,
        balance_sgd    = balance_sgd,
        open_trades    = open_trades,
        weekly_pnl     = wk["net_sgd"],
        weekly_wins    = wk["wins"],
        weekly_losses  = wk["losses"],
    )

    # ── Fetch candles ─────────────────────────────────────────────────────────
    df = trader.get_candles()
    if df is None or df.empty or len(df) < 25:
        log.error("No candle data — aborting cycle")
        tg.alert_error("Could not fetch candle data")
        log.info("═══ Bot cycle complete (no data) ═══")
        return

    candle_date = df["Date"].iloc[-1]

    # ── Generate signal ───────────────────────────────────────────────────────
    sig = get_signal(df)
    print_signal(sig, candle_date)
    journal.log_signal(sig, candle_date)

    # ── Safety checks ─────────────────────────────────────────────────────────
    safe_to_trade, safety_reason = is_safe_to_trade(now)
    if not safe_to_trade:
        log.info(f"Trading paused: {safety_reason}")
        tg.alert_risk_pause(safety_reason)
        log.info("═══ Bot cycle complete (safety pause) ═══")
        return

    risk_ok, risk_reason = check_risk_limits()
    if not risk_ok:
        log.warning(f"Risk limit hit: {risk_reason}")
        tg.alert_risk_pause(risk_reason)
        log.info("═══ Bot cycle complete (risk limit) ═══")
        return

    # ── No signal ─────────────────────────────────────────────────────────────
    if sig["signal"] == "NONE":
        log.info(f"No signal: {sig['reason']}")
        tg.alert_no_signal(sig, candle_date)   # pass full sig dict
        log.info("═══ Bot cycle complete (no signal) ═══")
        return

    # ── Already in trade ──────────────────────────────────────────────────────
    if trader.has_open_trade():
        log.info("Open trade exists — skipping new signal")
        tg.alert_open_trade_exists()
        log.info("═══ Bot cycle complete (trade open) ═══")
        return

    # ── Place order ───────────────────────────────────────────────────────────
    log.info(f"Signal confirmed: {sig['signal']} @ {sig['entry']}")
    tg.alert_signal(sig, candle_date, balance_sgd=balance_sgd)

    if cfg.BOT_MODE == "paper":
        log.info(f"[PAPER] {sig['signal']} @ {sig['entry']}  TP={sig['tp']}  SL={sig['sl']}")
        log.info("═══ Bot cycle complete (paper trade logged) ═══")
        return

    fill = trader.place_order(
        direction = sig["signal"],
        entry     = sig["entry"],
        tp        = sig["tp"],
        sl        = sig["sl"],
    )

    if fill.get("status") == "FILLED":
        # Refresh balance after fill
        acct2       = trader.get_account_summary()
        bal_after   = acct2.get("balance_sgd") or acct2.get("balance")
        log.info(f"Order filled: trade_id={fill.get('trade_id')} @ {fill.get('fill_price')}")
        tg.alert_order_filled(fill, balance_sgd=bal_after)
    else:
        log.error(f"Order failed: {fill}")
        tg.alert_error(f"Order failed: {fill.get('status')}")

    log.info("═══ Bot cycle complete ═══")

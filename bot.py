"""
bot.py — JPY Day Scalper cycle orchestration
=============================================
Fixed:
  - Balance uses explicit None check (not 'or' which breaks on 0.0)
  - Score passed to Telegram signal alert
  - Open P&L shown in session message
"""

from datetime import datetime, timezone
import settings as cfg
import logger as log
import journal
import telegram_alert as tg
from signals import get_signal, print_signal
from calendar_filter import is_safe_to_trade, get_session_label
from oanda_trader import get_trader
from risk import check_risk_limits


def run():
    """Execute one full bot cycle."""
    now = datetime.now(timezone.utc)
    log.info(f"═══ Scalper cycle: {now.strftime('%Y-%m-%d %H:%M UTC')} ═══")

    trader = get_trader()

    # ── Account status ────────────────────────────────────────────────────────
    acct        = trader.get_account_summary()
    # Explicit None check — 'or' breaks when balance is legitimately 0.0
    balance_sgd = acct.get("balance_sgd") if acct.get("balance_sgd") is not None \
                  else acct.get("balance")
    open_trades = acct.get("open_trades", 0)
    open_pl     = acct.get("open_pl", 0.0)
    currency    = acct.get("currency", "SGD")

    if balance_sgd is not None:
        log.info(f"Balance: {currency} {balance_sgd:.2f}  open_pl={open_pl:+.2f}  trades={open_trades}")
    else:
        log.warning("Could not fetch account balance from OANDA")

    # ── Weekly stats ──────────────────────────────────────────────────────────
    wk          = journal.weekly_stats()
    session_lbl = get_session_label(now)

    tg.alert_session_start(
        session_label = session_lbl,
        balance_sgd   = balance_sgd,
        open_trades   = open_trades,
        open_pl       = open_pl,
        weekly_pnl    = wk["net_sgd"],
        weekly_wins   = wk["wins"],
        weekly_losses = wk["losses"],
    )

    # ── Fetch candles ─────────────────────────────────────────────────────────
    df = trader.get_candles()
    if df is None or df.empty or len(df) < 20:
        log.error("No candle data — aborting cycle")
        tg.alert_error("Could not fetch candle data from OANDA")
        log.info("═══ Cycle complete (no data) ═══")
        return

    candle_date = df["Date"].iloc[-1]

    # ── Signal ────────────────────────────────────────────────────────────────
    sig = get_signal(df)
    print_signal(sig, candle_date)
    journal.log_signal(sig, candle_date)

    # ── Safety checks ─────────────────────────────────────────────────────────
    safe, reason = is_safe_to_trade(now)
    if not safe:
        log.info(f"Paused: {reason}")
        tg.alert_risk_pause(reason)
        log.info("═══ Cycle complete (paused) ═══")
        return

    risk_ok, risk_reason = check_risk_limits()
    if not risk_ok:
        log.warning(f"Risk limit: {risk_reason}")
        tg.alert_risk_pause(risk_reason)
        log.info("═══ Cycle complete (risk) ═══")
        return

    # ── No signal ─────────────────────────────────────────────────────────────
    if sig["signal"] == "NONE":
        log.info(f"No signal: {sig['reason']}")
        tg.alert_no_signal(sig, candle_date)
        log.info("═══ Cycle complete (no signal) ═══")
        return

    # ── Already in trade ──────────────────────────────────────────────────────
    if trader.has_open_trade():
        log.info("Open trade exists — skipping new signal")
        log.info("═══ Cycle complete (trade open) ═══")
        return

    # ── Place order ───────────────────────────────────────────────────────────
    log.info(f"Signal: {sig['signal']} @ {sig['entry']}  score={sig.get('score',{}).get('total','?')}")
    tg.alert_signal(sig, candle_date, balance_sgd=balance_sgd)

    # Paper mode: log the signal but do NOT send a real order.
    # Balance is still fetched from the real OANDA demo account above.
    if cfg.BOT_MODE == "paper":
        log.info(f"[PAPER] Signal only — no order placed: {sig['signal']} @ {sig['entry']} TP={sig['tp']} SL={sig['sl']}")
        log.info("═══ Cycle complete (paper — signal only) ═══")
        return

    # demo mode and live mode both proceed to place orders below

    fill = trader.place_order(
        direction = sig["signal"],
        entry     = sig["entry"],
        tp        = sig["tp"],
        sl        = sig["sl"],
    )

    if fill.get("status") == "FILLED":
        acct2       = trader.get_account_summary()
        bal_after   = acct2.get("balance_sgd") if acct2.get("balance_sgd") is not None \
                      else acct2.get("balance")
        log.info(f"Order filled: {fill.get('trade_id')} @ {fill.get('fill_price')}")
        tg.alert_order_filled(fill, balance_sgd=bal_after)
    else:
        log.error(f"Order failed: {fill}")
        tg.alert_error(f"Order failed: {fill.get('status')}")

    log.info("═══ Cycle complete ═══")

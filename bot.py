"""bot.py — JPY Day Scalper cycle orchestration"""
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
    now = datetime.now(timezone.utc)
    log.info(f"═══ Scalper cycle: {now.strftime('%Y-%m-%d %H:%M UTC')} ═══")
    trader = get_trader()

    acct        = trader.get_account_summary()
    balance_sgd = acct.get("balance_sgd") or acct.get("balance")
    open_trades = acct.get("open_trades", 0)
    wk          = journal.weekly_stats()
    session_lbl = get_session_label(now)

    tg.alert_session_start(
        session_label = session_lbl,
        balance_sgd   = balance_sgd,
        open_trades   = open_trades,
        weekly_pnl    = wk["net_sgd"],
        weekly_wins   = wk["wins"],
        weekly_losses = wk["losses"],
    )

    df = trader.get_candles()
    if df is None or df.empty or len(df) < 20:
        log.error("No candle data"); tg.alert_error("No candle data")
        log.info("═══ Cycle complete (no data) ═══"); return

    candle_date = df["Date"].iloc[-1]
    sig = get_signal(df)
    print_signal(sig, candle_date)
    journal.log_signal(sig, candle_date)

    safe, reason = is_safe_to_trade(now)
    if not safe:
        log.info(f"Paused: {reason}"); tg.alert_risk_pause(reason)
        log.info("═══ Cycle complete (paused) ═══"); return

    risk_ok, risk_reason = check_risk_limits()
    if not risk_ok:
        log.warning(f"Risk limit: {risk_reason}"); tg.alert_risk_pause(risk_reason)
        log.info("═══ Cycle complete (risk) ═══"); return

    if sig["signal"] == "NONE":
        log.info(f"No signal: {sig['reason']}")
        tg.alert_no_signal(sig, candle_date)
        log.info("═══ Cycle complete (no signal) ═══"); return

    if trader.has_open_trade():
        log.info("Trade already open — skipping")
        log.info("═══ Cycle complete (open trade) ═══"); return

    log.info(f"Signal: {sig['signal']} @ {sig['entry']}")
    tg.alert_signal(sig, candle_date, balance_sgd=balance_sgd)

    if cfg.BOT_MODE == "paper":
        log.info(f"[PAPER] {sig['signal']} @ {sig['entry']} TP={sig['tp']} SL={sig['sl']}")
        log.info("═══ Cycle complete (paper) ═══"); return

    fill = trader.place_order(direction=sig["signal"], entry=sig["entry"],
                              tp=sig["tp"], sl=sig["sl"])
    if fill.get("status") == "FILLED":
        acct2 = trader.get_account_summary()
        tg.alert_order_filled(fill, balance_sgd=acct2.get("balance_sgd") or acct2.get("balance"))
        log.info(f"Filled: {fill.get('trade_id')} @ {fill.get('fill_price')}")
    else:
        log.error(f"Order failed: {fill}")
        tg.alert_error(f"Order failed: {fill.get('status')}")
    log.info("═══ Cycle complete ═══")

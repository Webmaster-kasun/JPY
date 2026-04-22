"""telegram_alert.py — SGD-only alerts for JPY Day Scalper"""
import requests
from datetime import datetime, timezone, timedelta
import settings as cfg
import logger as log

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

def _sgt():
    return (datetime.now(timezone.utc)+timedelta(hours=8)).strftime("%d %b %Y  %H:%M SGT")

def _send(text):
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured"); return False
    try:
        r = requests.post(TELEGRAM_API.format(token=cfg.TELEGRAM_TOKEN),
                          json={"chat_id":cfg.TELEGRAM_CHAT_ID,"text":text,"parse_mode":"HTML"}, timeout=8)
        r.raise_for_status(); return True
    except Exception as e:
        log.error(f"Telegram error: {e}"); return False

def alert_startup(balance_sgd=None, open_trades=0, weekly_wins=0, weekly_losses=0, weekly_pnl=0.0):
    bal  = f"💰 Balance   : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd is not None else ""
    wkly = f"📊 This week : {weekly_wins}W {weekly_losses}L  SGD {weekly_pnl:+.0f}\n" if (weekly_wins+weekly_losses)>0 else "📊 This week : No trades yet\n"
    return _send(
        f"🟢 <b>JPY Day Scalper — Online</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt()}\n"
        f"⚙️ Mode : {cfg.BOT_MODE.upper()}  |  {cfg.OANDA_ENV.upper()}\n"
        f"{bal}"
        f"🔓 Open trades : {open_trades}\n"
        f"{wkly}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ 06:05 SGT — Tokyo open\n"
        f"⏰ 22:35 SGT — NY/London overlap\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 TP {cfg.TP_PIPS} pip = <b>+SGD {cfg.TP_SGD}</b>  "
        f"🛑 SL {cfg.SL_PIPS} pip = <b>-SGD {cfg.SL_SGD}</b>\n"
        f"📈 Backtest: 78.6% WR  |  +SGD 151/week avg"
    )

def alert_session_start(session_label, balance_sgd=None, open_trades=0, weekly_pnl=0.0, weekly_wins=0, weekly_losses=0):
    bal  = f"💰 Balance   : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd is not None else ""
    wkly = f"📊 This week : {weekly_wins}W {weekly_losses}L  SGD {weekly_pnl:+.0f}" if (weekly_wins+weekly_losses)>0 else "📊 This week : No trades yet"
    return _send(
        f"🔍 <b>Scanning — {session_label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt()}\n"
        f"{bal}"
        f"🔓 Open trades : {open_trades}\n"
        f"{wkly}"
    )

def alert_signal(sig, candle_date=None, balance_sgd=None):
    date_str = str(candle_date)[:10] if candle_date else "Today"
    bal  = f"💰 Balance  : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd is not None else ""
    arrow= "↑ LONG" if sig['signal']=="LONG" else "↓ SHORT"
    checks = sig.get("checks",{})
    ck = "".join(f"{'✅' if v else '❌'} {k.replace('_',' ')}\n" for k,v in checks.items())
    return _send(
        f"{'🟢' if sig['signal']=='LONG' else '🔴'} <b>{arrow} SIGNAL — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {date_str}  |  🕐 {_sgt()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Entry  : <code>{sig['entry']:.4f}</code>\n"
        f"🎯 TP     : <code>{sig['tp']:.4f}</code>  → <b>+SGD {cfg.TP_SGD}</b>\n"
        f"🛑 SL     : <code>{sig['sl']:.4f}</code>  → <b>-SGD {cfg.SL_SGD}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 RSI    : <code>{sig['rsi']:.1f}</code>   Stoch: <code>{sig['stoch_k']:.1f}</code>\n"
        f"📈 EMA9   : <code>{sig['ema_fast']:.4f}</code>  EMA21: <code>{sig['ema_slow']:.4f}</code>\n"
        f"📐 ATR    : <code>{sig['atr_pips']:.1f} pips</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ck}"
        f"{bal}"
        f"📦 Units  : {cfg.UNITS:,}  ({cfg.UNITS//10000} mini lots)\n"
        f"⚙️ Mode   : {cfg.BOT_MODE.upper()}"
    )

def alert_no_signal(sig, candle_date=None):
    date_str = str(candle_date)[:10] if candle_date else "Today"
    rsi_v  = f"{sig['rsi']:.1f}"    if sig.get('rsi')     else "?"
    sk_v   = f"{sig['stoch_k']:.1f}" if sig.get('stoch_k') else "?"
    ef_v   = f"{sig['ema_fast']:.4f}" if sig.get('ema_fast') else "?"
    es_v   = f"{sig['ema_slow']:.4f}" if sig.get('ema_slow') else "?"
    atr_v  = f"{sig['atr_pips']:.1f}" if sig.get('atr_pips') else "?"
    checks = sig.get("checks", {})
    ck = "".join(f"{'✅' if v else '❌'} {k.replace('_',' ')}\n" for k,v in checks.items())
    return _send(
        f"⚪ <b>No Signal — {date_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 RSI   : <code>{rsi_v}</code>   Stoch: <code>{sk_v}</code>\n"
        f"📈 EMA9  : <code>{ef_v}</code>  EMA21: <code>{es_v}</code>\n"
        f"📐 ATR   : <code>{atr_v} pips</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ck}"
        f"⏳ <b>{sig.get('reason','Waiting')}</b>"
    )

def alert_order_filled(fill, balance_sgd=None):
    bal = f"💰 Balance after : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd is not None else ""
    return _send(
        f"✅ <b>ORDER FILLED — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt()}\n"
        f"{'🔼' if fill['direction']=='LONG' else '🔽'} {fill['direction']}\n"
        f"💵 Fill  : <code>{fill['fill_price']:.4f}</code>\n"
        f"🎯 TP    : <code>{fill['tp']:.4f}</code>  → <b>+SGD {cfg.TP_SGD}</b>\n"
        f"🛑 SL    : <code>{fill['sl']:.4f}</code>  → <b>-SGD {cfg.SL_SGD}</b>\n"
        f"📦 Units : {abs(fill['units']):,}\n"
        f"🆔 ID    : <code>{fill['trade_id']}</code>\n"
        f"{bal}"
    )

def alert_trade_closed(result, pnl_sgd, running_sgd, entry, close_price, balance_sgd=None):
    emoji = "🏆" if result=="WIN" else "❌"
    bal   = f"💰 Balance : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd is not None else ""
    return _send(
        f"{emoji} <b>TRADE {result} — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt()}\n"
        f"📥 Entry   : <code>{entry:.4f}</code>\n"
        f"📤 Close   : <code>{close_price:.4f}</code>\n"
        f"💵 P&L     : <b>SGD {pnl_sgd:+.0f}</b>\n"
        f"📊 Running : <b>SGD {running_sgd:+.0f}</b>\n"
        f"{bal}"
    )

def alert_weekly_summary(total, wins, losses, net_sgd, win_rate, balance_sgd=None):
    emoji = "📈" if net_sgd>=0 else "📉"
    bal   = f"💰 Balance : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd is not None else ""
    return _send(
        f"{emoji} <b>Weekly Summary — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Trades  : {total}  ({wins}W / {losses}L)\n"
        f"📊 Win rate: {win_rate:.1f}%\n"
        f"💵 Net P&L : <b>SGD {net_sgd:+.0f}</b>\n"
        f"{bal}"
    )

def alert_risk_pause(reason):
    return _send(f"⚠️ <b>Bot Paused</b>\n━━━━━━━━━━━━━━━━━━━━━━\n🚫 {reason}\n▶️ Resumes next Monday.")

def alert_error(message):
    return _send(f"🔴 <b>Bot Error</b>\n━━━━━━━━━━━━━━━━━━━━━━\n<code>{message}</code>\n🕐 {_sgt()}")

def test_connection():
    return _send(f"🤖 <b>JPY Day Scalper — Connected</b>\nMode: {cfg.BOT_MODE.upper()}  |  {cfg.PAIR_LABEL}\n🕐 {_sgt()}")

"""
telegram_alert.py — Telegram notification system
=================================================
Sends trade signals, fills, and P&L summaries to your Telegram chat.

Setup:
  1. Create a bot via @BotFather on Telegram
  2. Get your chat ID from @userinfobot
  3. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env

All messages are optional — bot runs fine without Telegram configured.
"""

import requests
import settings as cfg
import logger as log


TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send(text: str, parse_mode: str = "HTML") -> bool:
    """Core send function. Returns True on success."""
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — skipping alert")
        return False

    url     = TELEGRAM_API.format(token=cfg.TELEGRAM_TOKEN)
    payload = {
        "chat_id"   : cfg.TELEGRAM_CHAT_ID,
        "text"      : text,
        "parse_mode": parse_mode,
    }

    try:
        r = requests.post(url, json=payload, timeout=8)
        r.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        return False


# ── Alert templates ───────────────────────────────────────────────────────────

def alert_signal(sig: dict, candle_date=None):
    """Send LONG signal alert with entry/TP/SL levels."""
    date_str = str(candle_date)[:10] if candle_date else "Today"
    text = (
        f"<b>🟢 USD/JPY LONG SIGNAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Date   : <code>{date_str}</code>\n"
        f"💰 Entry  : <code>{sig['entry']:.4f}</code>\n"
        f"🎯 TP     : <code>{sig['tp']:.4f}</code>  (+{cfg.TP_PIPS} pips | ~SGD {cfg.TP_SGD:.0f})\n"
        f"🛑 SL     : <code>{sig['sl']:.4f}</code>  (-{cfg.SL_PIPS} pips | ~SGD {cfg.SL_SGD:.0f})\n"
        f"📊 RSI    : <code>{sig['rsi']:.1f}</code>\n"
        f"📈 EMA9   : <code>{sig['ema_fast']:.4f}</code>  EMA21: <code>{sig['ema_slow']:.4f}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Units: {cfg.UNITS:,}  |  Mode: {cfg.BOT_MODE.upper()}"
    )
    return _send(text)


def alert_no_signal(reason: str, candle_date=None):
    """Send no-signal update (once daily)."""
    date_str = str(candle_date)[:10] if candle_date else "Today"
    text = (
        f"<b>⚪ USD/JPY — No Signal</b>\n"
        f"📅 {date_str}\n"
        f"💬 {reason}"
    )
    return _send(text)


def alert_order_filled(fill: dict):
    """Send order fill confirmation."""
    text = (
        f"<b>✅ ORDER FILLED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔼 Direction : {fill['direction']}\n"
        f"💰 Fill price: <code>{fill['fill_price']:.4f}</code>\n"
        f"🎯 TP        : <code>{fill['tp']:.4f}</code>\n"
        f"🛑 SL        : <code>{fill['sl']:.4f}</code>\n"
        f"📦 Units     : {fill['units']:,}\n"
        f"🆔 Trade ID  : {fill['trade_id']}"
    )
    return _send(text)


def alert_trade_closed(result: str, pnl_sgd: float, running_sgd: float,
                       entry: float, close_price: float):
    """Send trade result (WIN/LOSS)."""
    emoji = "🏆" if result == "WIN" else "❌"
    sign  = "+" if pnl_sgd >= 0 else ""
    text = (
        f"<b>{emoji} TRADE {result}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 Entry  : <code>{entry:.4f}</code>\n"
        f"📤 Close  : <code>{close_price:.4f}</code>\n"
        f"💵 P&L    : <b>SGD {sign}{pnl_sgd:.2f}</b>\n"
        f"📊 Running: SGD {running_sgd:+.2f}"
    )
    return _send(text)


def alert_weekly_summary(total: int, wins: int, losses: int,
                         net_sgd: float, win_rate: float):
    """Weekly P&L digest."""
    emoji = "📈" if net_sgd >= 0 else "📉"
    text = (
        f"<b>{emoji} WEEKLY SUMMARY — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Trades  : {total}  ({wins}W / {losses}L)\n"
        f"📊 Win rate: {win_rate:.1f}%\n"
        f"💰 Net P&L : <b>SGD {net_sgd:+.2f}</b>"
    )
    return _send(text)


def alert_risk_pause(reason: str):
    """Alert when bot pauses due to risk limits."""
    text = (
        f"<b>⚠️ BOT PAUSED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🚫 Reason: {reason}\n"
        f"Bot will resume next week."
    )
    return _send(text)


def alert_error(message: str):
    """Send error notification."""
    text = f"<b>🔴 BOT ERROR</b>\n<code>{message}</code>"
    return _send(text)


def test_connection():
    """Send a test ping to verify Telegram is working."""
    return _send(
        f"<b>🤖 USD/JPY Bot connected</b>\n"
        f"Mode: {cfg.BOT_MODE.upper()} | Pair: {cfg.PAIR_LABEL}"
    )

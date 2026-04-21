"""
telegram_alert.py — Telegram notifications (SGD only)
======================================================
All P&L shown in SGD — no USD references.
Rich startup message with balance + schedule.
Suppressed routine no-signal spam.
"""

import requests
from datetime import datetime, timezone
import settings as cfg
import logger as log

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
SGT_OFFSET   = 8   # SGT = UTC+8


def _sgt_now() -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(hours=SGT_OFFSET)).strftime("%d %b %Y  %H:%M SGT")


def _send(text: str, parse_mode: str = "HTML") -> bool:
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — skipping alert")
        return False
    url     = TELEGRAM_API.format(token=cfg.TELEGRAM_TOKEN)
    payload = {"chat_id": cfg.TELEGRAM_CHAT_ID, "text": text, "parse_mode": parse_mode}
    try:
        r = requests.post(url, json=payload, timeout=8)
        r.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        return False


# ── Startup ───────────────────────────────────────────────────────────────────

def alert_startup(balance_sgd: float = None, open_trades: int = 0,
                  weekly_wins: int = 0, weekly_losses: int = 0,
                  weekly_pnl: float = 0.0):
    """Rich startup message sent when bot boots — includes balance + schedule."""
    mode_icon = "🟢" if cfg.BOT_MODE == "live" else "🟡"
    bal_line  = f"💰 Balance  : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd else ""
    week_line = (
        f"📊 This week: {weekly_wins}W {weekly_losses}L  "
        f"<b>SGD {weekly_pnl:+.2f}</b>\n"
        if (weekly_wins + weekly_losses) > 0 else
        f"📊 This week: No trades yet\n"
    )
    text = (
        f"{mode_icon} <b>USD/JPY Bot — Online</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt_now()}\n"
        f"⚙️ Mode      : {cfg.BOT_MODE.upper()}  |  {cfg.OANDA_ENV.upper()}\n"
        f"📈 Pair      : {cfg.PAIR_LABEL}\n"
        f"{bal_line}"
        f"🔓 Open trades: {open_trades}\n"
        f"{week_line}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ Schedule  :\n"
        f"   06:00 SGT — Tokyo open\n"
        f"   22:30 SGT — NY/London overlap\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 TP {cfg.TP_PIPS} pip = <b>+SGD {cfg.TP_SGD:.0f}</b>  "
        f"🛑 SL {cfg.SL_PIPS} pip = <b>-SGD {cfg.SL_SGD:.0f}</b>"
    )
    return _send(text)


# ── Session start ─────────────────────────────────────────────────────────────

def alert_session_start(session_label: str, balance_sgd: float = None,
                        open_trades: int = 0, weekly_pnl: float = 0.0,
                        weekly_wins: int = 0, weekly_losses: int = 0):
    """Sent at the start of EACH scan session (06:00 and 22:30 SGT)."""
    bal_line = f"💰 Balance   : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd else ""
    wk_total = weekly_wins + weekly_losses
    wk_line  = (
        f"📊 This week : {weekly_wins}W {weekly_losses}L  SGD {weekly_pnl:+.2f}\n"
        if wk_total > 0 else "📊 This week : No trades yet\n"
    )
    text = (
        f"🔍 <b>Scanning — {session_label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt_now()}\n"
        f"{bal_line}"
        f"🔓 Open trades: {open_trades}\n"
        f"{wk_line}"
    )
    return _send(text)


# ── Signal ────────────────────────────────────────────────────────────────────

def alert_signal(sig: dict, candle_date=None, balance_sgd: float = None):
    """LONG signal — full detail, SGD only."""
    date_str = str(candle_date)[:10] if candle_date else "Today"
    bal_line = f"💰 Balance  : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd else ""
    checks   = sig.get("checks", {})
    c1 = "✅" if checks.get("uptrend")    else "❌"
    c2 = "✅" if checks.get("prev_red")   else "❌"
    c3 = "✅" if checks.get("curr_green") else "❌"
    c4 = "✅" if checks.get("rsi_band")   else "❌"
    text = (
        f"🟢 <b>LONG SIGNAL — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Date    : <code>{date_str}</code>\n"
        f"🕐 {_sgt_now()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Entry   : <code>{sig['entry']:.4f}</code>\n"
        f"🎯 TP      : <code>{sig['tp']:.4f}</code>  → <b>+SGD {cfg.TP_SGD:.0f}</b>\n"
        f"🛑 SL      : <code>{sig['sl']:.4f}</code>  → <b>-SGD {cfg.SL_SGD:.0f}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 RSI     : <code>{sig['rsi']:.1f}</code>\n"
        f"📈 EMA9    : <code>{sig['ema_fast']:.4f}</code>   EMA21: <code>{sig['ema_slow']:.4f}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{c1} Uptrend (EMA9 > EMA21)\n"
        f"{c2} Prev candle RED\n"
        f"{c3} Curr candle GREEN\n"
        f"{c4} RSI {cfg.RSI_MIN}–{cfg.RSI_MAX}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{bal_line}"
        f"📦 Units   : {cfg.UNITS:,}  ({cfg.UNITS//10000} mini lots)\n"
        f"⚙️ Mode    : {cfg.BOT_MODE.upper()}"
    )
    return _send(text)


def alert_no_signal(sig: dict, candle_date=None):
    """
    No-signal update — shows WHY with indicator values.
    Only sends when at least one check JUST flipped (not pure spam).
    """
    date_str = str(candle_date)[:10] if candle_date else "Today"
    checks   = sig.get("checks", {})
    c1 = "✅" if checks.get("uptrend")    else "❌"
    c2 = "✅" if checks.get("prev_red")   else "❌"
    c3 = "✅" if checks.get("curr_green") else "❌"
    c4 = "✅" if checks.get("rsi_band")   else "❌"

    rsi_val   = sig.get("rsi", "?")
    ema_f     = sig.get("ema_fast", "?")
    ema_s     = sig.get("ema_slow", "?")
    rsi_str   = f"{rsi_val:.1f}" if isinstance(rsi_val, float) else str(rsi_val)
    ema_f_str = f"{ema_f:.4f}"   if isinstance(ema_f, float)   else str(ema_f)
    ema_s_str = f"{ema_s:.4f}"   if isinstance(ema_s, float)   else str(ema_s)

    failed = [k for k, v in checks.items() if not v]
    reason = ", ".join(failed) if failed else sig.get("reason", "unknown")

    text = (
        f"⚪ <b>No Signal — {date_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 RSI  : <code>{rsi_str}</code>   (need 50–77)\n"
        f"📈 EMA9 : <code>{ema_f_str}</code>   EMA21: <code>{ema_s_str}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{c1} Uptrend\n"
        f"{c2} Prev RED\n"
        f"{c3} Curr GREEN\n"
        f"{c4} RSI band\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ Waiting for: <b>{reason}</b>"
    )
    return _send(text)


# ── Order filled ──────────────────────────────────────────────────────────────

def alert_order_filled(fill: dict, balance_sgd: float = None):
    """Order confirmed — SGD targets only."""
    bal_line = f"💰 Balance after : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd else ""
    text = (
        f"✅ <b>ORDER FILLED — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt_now()}\n"
        f"🔼 Direction : {fill['direction']}\n"
        f"💵 Fill price: <code>{fill['fill_price']:.4f}</code>\n"
        f"🎯 TP target : <code>{fill['tp']:.4f}</code>  → <b>+SGD {cfg.TP_SGD:.0f}</b>\n"
        f"🛑 SL target : <code>{fill['sl']:.4f}</code>  → <b>-SGD {cfg.SL_SGD:.0f}</b>\n"
        f"📦 Units     : {abs(fill['units']):,}\n"
        f"🆔 Trade ID  : <code>{fill['trade_id']}</code>\n"
        f"{bal_line}"
    )
    return _send(text)


# ── Trade closed ──────────────────────────────────────────────────────────────

def alert_trade_closed(result: str, pnl_sgd: float, running_sgd: float,
                       entry: float, close_price: float, balance_sgd: float = None):
    """Trade result — SGD P&L only."""
    emoji    = "🏆" if result == "WIN" else "❌"
    bal_line = f"💰 Balance   : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd else ""
    text = (
        f"{emoji} <b>TRADE {result} — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt_now()}\n"
        f"📥 Entry   : <code>{entry:.4f}</code>\n"
        f"📤 Close   : <code>{close_price:.4f}</code>\n"
        f"💵 P&L     : <b>SGD {pnl_sgd:+.2f}</b>\n"
        f"📊 Running : <b>SGD {running_sgd:+.2f}</b>\n"
        f"{bal_line}"
    )
    return _send(text)


# ── Weekly summary ────────────────────────────────────────────────────────────

def alert_weekly_summary(total: int, wins: int, losses: int,
                         net_sgd: float, win_rate: float,
                         balance_sgd: float = None):
    emoji    = "📈" if net_sgd >= 0 else "📉"
    bal_line = f"💰 Balance : <b>SGD {balance_sgd:,.2f}</b>\n" if balance_sgd else ""
    text = (
        f"{emoji} <b>Weekly Summary — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Trades  : {total}  ({wins}W / {losses}L)\n"
        f"📊 Win rate: {win_rate:.1f}%\n"
        f"💵 Net P&L : <b>SGD {net_sgd:+.2f}</b>\n"
        f"{bal_line}"
    )
    return _send(text)


# ── Risk / error ──────────────────────────────────────────────────────────────

def alert_risk_pause(reason: str):
    text = (
        f"⚠️ <b>Bot Paused — Risk Limit</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚫 {reason}\n"
        f"▶️ Resumes next Monday."
    )
    return _send(text)


def alert_error(message: str):
    text = (
        f"🔴 <b>Bot Error</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<code>{message}</code>\n"
        f"🕐 {_sgt_now()}"
    )
    return _send(text)


def alert_open_trade_exists(trade_info: dict = None):
    """Alert when a signal fires but a trade is already open."""
    text = (
        f"ℹ️ <b>Signal found — trade already open</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt_now()}\n"
        f"Skipping new entry. Waiting for current trade to close."
    )
    return _send(text)


def test_connection():
    """Startup ping — minimal, just confirms bot is alive."""
    text = (
        f"🤖 <b>USD/JPY Bot — Connected</b>\n"
        f"Mode: {cfg.BOT_MODE.upper()}  |  {cfg.PAIR_LABEL}\n"
        f"🕐 {_sgt_now()}"
    )
    return _send(text)

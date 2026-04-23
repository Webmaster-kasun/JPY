"""
telegram_alert.py — Telegram notifications for JPY Day Scalper
===============================================================
All P&L in SGD only.
Signal messages include score (0-100) and grade.
Balance shown directly from OANDA (live) or paper starting capital.
"""

import requests
from datetime import datetime, timezone, timedelta
import settings as cfg
import logger as log

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _sgt() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%d %b %Y  %H:%M SGT")


def _send(text: str) -> bool:
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — skipping")
        return False
    try:
        r = requests.post(
            TELEGRAM_API.format(token=cfg.TELEGRAM_TOKEN),
            json={"chat_id": cfg.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=8
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Telegram error: {e}")
        return False


def _bal_line(balance_sgd, open_pl=None) -> str:
    """Format balance line — always shows real OANDA balance (no fake paper label)."""
    if balance_sgd is None:
        return ""
    pl_str = f"  unrealised {open_pl:+.2f}" if open_pl and open_pl != 0 else ""
    return f"💰 Balance   : <b>SGD {balance_sgd:,.2f}</b>{pl_str}\n"


# ── Startup ───────────────────────────────────────────────────────────────────

def alert_startup(balance_sgd=None, open_trades=0,
                  weekly_wins=0, weekly_losses=0, weekly_pnl=0.0):
    """Sent when Railway boots the container."""
    bal  = _bal_line(balance_sgd)
    wkly = (f"📊 This week : {weekly_wins}W {weekly_losses}L  SGD {weekly_pnl:+.0f}\n"
            if (weekly_wins + weekly_losses) > 0 else "📊 This week : No trades yet\n")
    if cfg.BOT_MODE == "live":
        mode_icon = "🟢"
    elif cfg.BOT_MODE == "demo":
        mode_icon = "🟠"
    else:
        mode_icon = "🟡"
    return _send(
        f"{mode_icon} <b>JPY Day Scalper — Online</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt()}\n"
        f"⚙️ Mode     : {cfg.BOT_MODE.upper()}  |  {cfg.OANDA_ENV.upper()}\n"
        f"📈 Pair     : {cfg.PAIR_LABEL}\n"
        f"{bal}"
        f"🔓 Open trades : {open_trades}\n"
        f"{wkly}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ 06:05 SGT — Tokyo open\n"
        f"⏰ 22:35 SGT — NY/London overlap\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 TP {cfg.TP_PIPS} pip = <b>+SGD {cfg.TP_SGD}</b>  "
        f"🛑 SL {cfg.SL_PIPS} pip = <b>-SGD {cfg.SL_SGD}</b>\n"
        f"📊 Backtest: 82.7% WR  |  +SGD 227/week"
    )


# ── Session start ─────────────────────────────────────────────────────────────

def alert_session_start(session_label, balance_sgd=None, open_trades=0,
                        open_pl=0.0, weekly_pnl=0.0,
                        weekly_wins=0, weekly_losses=0):
    """Sent at the start of each scan (06:05 SGT and 22:35 SGT)."""
    bal  = _bal_line(balance_sgd, open_pl)
    wkly = (f"📊 This week : {weekly_wins}W {weekly_losses}L  SGD {weekly_pnl:+.0f}"
            if (weekly_wins + weekly_losses) > 0 else "📊 This week : No trades yet")
    return _send(
        f"🔍 <b>Scanning — {session_label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt()}\n"
        f"{bal}"
        f"🔓 Open trades : {open_trades}\n"
        f"{wkly}"
    )


# ── Signal ────────────────────────────────────────────────────────────────────

def alert_signal(sig: dict, candle_date=None, balance_sgd=None):
    """LONG/SHORT signal — includes score, all levels in SGD."""
    date_str = str(candle_date)[:10] if candle_date else "Today"
    bal      = _bal_line(balance_sgd)
    arrow    = "↑ LONG" if sig["signal"] == "LONG" else "↓ SHORT"
    icon     = "🟢" if sig["signal"] == "LONG" else "🔴"

    # Signal score block
    score = sig.get("score") or {}
    total = score.get("total", 0)
    grade = score.get("grade", "")
    stars = score.get("stars", "")
    ema_s = score.get("ema_score", 0)
    rsi_s = score.get("rsi_score", 0)
    stk_s = score.get("stoch_score", 0)

    # Progress bar for score
    filled = round(total / 10)
    bar    = "█" * filled + "░" * (10 - filled)

    checks = sig.get("checks", {})
    CHECK_LABELS = {
        "uptrend"             : "EMA9 > EMA21",
        "downtrend"           : "EMA9 < EMA21",
        "rsi_not_overbought"  : f"RSI < {cfg.RSI_LONG_MAX}",
        "rsi_not_oversold"    : f"RSI > {cfg.RSI_SHORT_MIN}",
        "stoch_not_overbought": f"Stoch < {cfg.STOCH_LONG_MAX}",
        "stoch_not_oversold"  : f"Stoch > {cfg.STOCH_SHORT_MIN}",
    }
    ck = "".join(
        f"{'✅' if v else '❌'} {CHECK_LABELS.get(k, k.replace('_',' '))}\n"
        for k, v in checks.items()
    )

    return _send(
        f"{icon} <b>{arrow} SIGNAL — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {date_str}  |  🕐 {_sgt()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📶 Score : <b>{total}/100</b>  {grade}\n"
        f"     [{bar}]\n"
        f"     EMA:{ema_s}  RSI:{rsi_s}  Stoch:{stk_s}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Entry : <code>{sig['entry']:.4f}</code>\n"
        f"🎯 TP    : <code>{sig['tp']:.4f}</code>  → <b>+SGD {cfg.TP_SGD}</b>\n"
        f"🛑 SL    : <code>{sig['sl']:.4f}</code>  → <b>-SGD {cfg.SL_SGD}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 RSI   : <code>{sig['rsi']:.1f}</code>   "
        f"Stoch: <code>{sig['stoch_k']:.1f}</code>   "
        f"ATR: <code>{sig['atr_pips']:.1f}pip</code>\n"
        f"📈 EMA9  : <code>{sig['ema_fast']:.4f}</code>  "
        f"EMA21: <code>{sig['ema_slow']:.4f}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ck}"
        f"{bal}"
        f"📦 Units : {cfg.UNITS:,}  ({cfg.UNITS//10000} mini lots)\n"
        f"⚙️ Mode  : {cfg.BOT_MODE.upper()}"
    )


# ── No signal ─────────────────────────────────────────────────────────────────

def alert_no_signal(sig: dict, candle_date=None):
    """No-signal update — shows indicator values and what's missing."""
    date_str = str(candle_date)[:10] if candle_date else "Today"
    rsi_v  = f"{sig['rsi']:.1f}"     if sig.get("rsi")      else "?"
    sk_v   = f"{sig['stoch_k']:.1f}" if sig.get("stoch_k")  else "?"
    ef_v   = f"{sig['ema_fast']:.4f}" if sig.get("ema_fast") else "?"
    es_v   = f"{sig['ema_slow']:.4f}" if sig.get("ema_slow") else "?"
    atr_v  = f"{sig['atr_pips']:.1f}" if sig.get("atr_pips") else "?"

    checks = sig.get("checks", {})
    CHECK_LABELS = {
        "uptrend"             : "EMA9 > EMA21",
        "downtrend"           : "EMA9 < EMA21",
        "rsi_not_overbought"  : f"RSI < {cfg.RSI_LONG_MAX}",
        "rsi_not_oversold"    : f"RSI > {cfg.RSI_SHORT_MIN}",
        "stoch_not_overbought": f"Stoch < {cfg.STOCH_LONG_MAX}",
        "stoch_not_oversold"  : f"Stoch > {cfg.STOCH_SHORT_MIN}",
    }
    ck = "".join(
        f"{'✅' if v else '❌'} {CHECK_LABELS.get(k, k.replace('_',' '))}\n"
        for k, v in checks.items()
    )
    return _send(
        f"⚪ <b>No Signal — {date_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 RSI   : <code>{rsi_v}</code>   Stoch: <code>{sk_v}</code>\n"
        f"📈 EMA9  : <code>{ef_v}</code>  EMA21: <code>{es_v}</code>\n"
        f"📐 ATR   : <code>{atr_v} pips</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ck}"
        f"⏳ <b>{sig.get('reason', 'Waiting')}</b>"
    )



# ── Weak signal (score below threshold) ───────────────────────────────────────

def alert_weak_signal(sig: dict, candle_date=None, score_val: int = 0, min_score: int = 50):
    """Sent when signal fires but score is too weak to place an order."""
    date_str = str(candle_date)[:10] if candle_date else "Today"
    arrow    = "↑ LONG" if sig["signal"] == "LONG" else "↓ SHORT"
    filled   = round(score_val / 10)
    bar      = "█" * filled + "░" * (10 - filled)
    return _send(
        f"⚠️ <b>Weak Signal — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {date_str}  |  🕐 {_sgt()}\n"
        f"📶 Score : <b>{score_val}/100</b>  [{bar}]\n"
        f"ℹ️ Minimum to trade: {min_score}/100\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Signal : {arrow}  @  <code>{sig.get('entry', ''):.5f}</code>\n"
        f"📊 RSI: <code>{sig.get('rsi', '')}</code>   Stoch: <code>{sig.get('stoch_k', '')}</code>\n"
        f"⛔ No order placed — score too weak"
    )


# ── Order filled ──────────────────────────────────────────────────────────────

def alert_order_filled(fill: dict, balance_sgd=None):
    """Confirmation after OANDA fills the order."""
    bal = _bal_line(balance_sgd)
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


# ── Trade closed ──────────────────────────────────────────────────────────────

def alert_trade_closed(result: str, pnl_sgd: float, running_sgd: float,
                       entry: float, close_price: float, balance_sgd=None):
    """Sent when TP or SL is hit."""
    emoji = "🏆" if result == "WIN" else "❌"
    bal   = _bal_line(balance_sgd)
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


# ── Weekly summary ────────────────────────────────────────────────────────────

def alert_weekly_summary(total: int, wins: int, losses: int,
                         net_sgd: float, win_rate: float, balance_sgd=None):
    emoji = "📈" if net_sgd >= 0 else "📉"
    bal   = _bal_line(balance_sgd)
    return _send(
        f"{emoji} <b>Weekly Summary — USD/JPY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Trades   : {total}  ({wins}W / {losses}L)\n"
        f"📊 Win rate : {win_rate:.1f}%\n"
        f"💵 Net P&L  : <b>SGD {net_sgd:+.0f}</b>\n"
        f"{bal}"
    )


# ── Risk / error ──────────────────────────────────────────────────────────────

def alert_risk_pause(reason: str):
    return _send(
        f"⚠️ <b>Bot Paused</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚫 {reason}\n"
        f"▶️ Resumes next Monday."
    )

def alert_error(message: str):
    return _send(
        f"🔴 <b>Bot Error</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<code>{message}</code>\n"
        f"🕐 {_sgt()}"
    )

def test_connection():
    return _send(
        f"🤖 <b>JPY Day Scalper — Connected</b>\n"
        f"Mode: {cfg.BOT_MODE.upper()}  |  {cfg.PAIR_LABEL}\n"
        f"🕐 {_sgt()}"
    )

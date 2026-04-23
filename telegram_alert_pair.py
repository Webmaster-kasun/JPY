"""
telegram_alert_pair.py — Per-pair Telegram notifications
=========================================================
Same messages as telegram_alert.py but prefixes each message with the
pair label (EUR/USD or GBP/USD) and reads TP/SL/pip values from cfg.

USD/JPY still uses the original telegram_alert.py — untouched.
"""

import requests
from datetime import datetime, timezone, timedelta
import logger as log

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _sgt() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%d %b %Y  %H:%M SGT")


def _send(cfg, text: str) -> bool:
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        log.warning(f"[{cfg.PAIR_LABEL}] Telegram not configured — skipping")
        return False
    try:
        r = requests.post(
            TELEGRAM_API.format(token=cfg.TELEGRAM_TOKEN),
            json={"chat_id": cfg.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log.error(f"[{cfg.PAIR_LABEL}] Telegram error: {e}")
        return False


def _bal_line(cfg, balance_sgd, open_pl=None) -> str:
    """Format balance line — always shows real OANDA balance (no mode label)."""
    if balance_sgd is None:
        return ""
    pl_str = f"  unrealised {open_pl:+.2f}" if open_pl and open_pl != 0 else ""
    return f"💰 Balance   : <b>SGD {balance_sgd:,.2f}</b>{pl_str}\n"


# ── Startup ───────────────────────────────────────────────────────────────────

def alert_startup(cfg, balance_sgd=None, open_trades=0,
                  weekly_wins=0, weekly_losses=0, weekly_pnl=0.0):
    bal  = _bal_line(cfg, balance_sgd)
    wkly = (f"📊 This week : {weekly_wins}W {weekly_losses}L  SGD {weekly_pnl:+.0f}\n"
            if (weekly_wins + weekly_losses) > 0 else "📊 This week : No trades yet\n")
    if cfg.BOT_MODE == "live":
        mode_icon = "🟢"
    elif cfg.BOT_MODE == "demo":
        mode_icon = "🟠"
    else:
        mode_icon = "🟡"
    return _send(cfg,
        f"{mode_icon} <b>{cfg.PAIR_LABEL} Bot — Online</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt()}\n"
        f"⚙️ Mode     : {cfg.BOT_MODE.upper()}  |  {cfg.OANDA_ENV.upper()}\n"
        f"📈 Pair     : {cfg.PAIR_LABEL}  |  TP {cfg.TP_PIPS}p / SL {cfg.SL_PIPS}p\n"
        f"{bal}"
        f"{wkly}"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


# ── Session start ─────────────────────────────────────────────────────────────

def alert_session_start(cfg, session_label="", balance_sgd=None,
                        open_trades=0, open_pl=0.0,
                        weekly_pnl=0.0, weekly_wins=0, weekly_losses=0):
    bal  = _bal_line(cfg, balance_sgd, open_pl)
    wkly = (f"📊 This week : {weekly_wins}W {weekly_losses}L  SGD {weekly_pnl:+.0f}\n"
            if (weekly_wins + weekly_losses) > 0 else "")
    return _send(cfg,
        f"🔔 <b>{cfg.PAIR_LABEL} — Cycle Start</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt()}\n"
        f"📍 {session_label}\n"
        f"{bal}"
        f"{wkly}"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


# ── Signal alert ──────────────────────────────────────────────────────────────

def alert_signal(cfg, sig: dict, candle_date=None, balance_sgd=None):
    direction = sig.get("signal", "?")
    arrow     = "↑ LONG" if direction == "LONG" else "↓ SHORT"
    score     = sig.get("score") or {}
    grade     = score.get("grade", "")
    stars     = score.get("stars", "")
    total     = score.get("total", 0)
    ema_s     = score.get("ema_score", 0)
    rsi_s     = score.get("rsi_score", 0)
    stk_s     = score.get("stoch_score", 0)
    bal       = _bal_line(cfg, balance_sgd)
    date_str  = f"📅 {str(candle_date)[:10]}  |  " if candle_date else ""
    filled    = round(total / 10)
    bar       = "█" * filled + "░" * (10 - filled)

    return _send(cfg,
        f"{'🟢' if direction == 'LONG' else '🔴'} "
        f"<b>{cfg.PAIR_LABEL} — {arrow}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {date_str}{_sgt()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📶 Score    : <b>{total}/100</b>  {grade}\n"
        f"     [{bar}]\n"
        f"     EMA:{ema_s}  RSI:{rsi_s}  Stoch:{stk_s}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💹 Entry    : <code>{sig.get('entry', ''):.5f}</code>\n"
        f"🎯 TP       : <code>{sig.get('tp', ''):.5f}</code>  (+{cfg.TP_PIPS}p  SGD +{cfg.TP_SGD})\n"
        f"🛑 SL       : <code>{sig.get('sl', ''):.5f}</code>  (-{cfg.SL_PIPS}p  SGD -{cfg.SL_SGD})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 RSI      : <code>{sig.get('rsi', '')}</code>   Stoch: <code>{sig.get('stoch_k', '')}</code>\n"
        f"📈 EMA9/21  : <code>{sig.get('ema_fast', ''):.5f}</code> / <code>{sig.get('ema_slow', ''):.5f}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{bal}"
        f"📦 Units : {cfg.UNITS:,}  ({cfg.UNITS//10000} mini lots)\n"
        f"⚙️ Mode  : {cfg.BOT_MODE.upper()}"
    )


# ── No signal ─────────────────────────────────────────────────────────────────

def alert_no_signal(cfg, sig: dict, candle_date=None):
    date_str = str(candle_date)[:10] if candle_date else "Today"
    rsi_v  = f"{sig['rsi']:.1f}"     if sig.get("rsi")      else "?"
    sk_v   = f"{sig['stoch_k']:.1f}" if sig.get("stoch_k")  else "?"
    ef_v   = f"{sig['ema_fast']:.5f}" if sig.get("ema_fast") else "?"
    es_v   = f"{sig['ema_slow']:.5f}" if sig.get("ema_slow") else "?"
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
    return _send(cfg,
        f"⚪ <b>{cfg.PAIR_LABEL} — No signal</b>  {date_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 RSI   : <code>{rsi_v}</code>   Stoch: <code>{sk_v}</code>\n"
        f"📈 EMA9  : <code>{ef_v}</code>  EMA21: <code>{es_v}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{ck}"
        f"⏳ <b>{sig.get('reason', 'Waiting')}</b>"
    )



# ── Weak signal (score below threshold) ───────────────────────────────────────

def alert_weak_signal(cfg, sig: dict, candle_date=None, score_val: int = 0, min_score: int = 50):
    """Sent when signal fires but score is too weak to place an order."""
    date_str = str(candle_date)[:10] if candle_date else "Today"
    arrow    = "↑ LONG" if sig.get("signal") == "LONG" else "↓ SHORT"
    filled   = round(score_val / 10)
    bar      = "█" * filled + "░" * (10 - filled)
    return _send(cfg,
        f"⚠️ <b>{cfg.PAIR_LABEL} — Weak Signal</b>\n"
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

def alert_order_filled(cfg, fill: dict, balance_sgd=None):
    direction = fill.get("direction", "?")
    bal       = _bal_line(cfg, balance_sgd)
    return _send(cfg,
        f"✅ <b>{cfg.PAIR_LABEL} — Order Filled</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {_sgt()}\n"
        f"📈 {direction}  @  {fill.get('fill_price', '')}\n"
        f"🎯 TP: {fill.get('tp', '')}   🛑 SL: {fill.get('sl', '')}\n"
        f"🔖 Trade ID : {fill.get('trade_id', '')}\n"
        f"{bal}"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


# ── Risk pause ────────────────────────────────────────────────────────────────

def alert_risk_pause(cfg, reason: str):
    return _send(cfg,
        f"⏸ <b>{cfg.PAIR_LABEL} — Paused</b>\n"
        f"ℹ️ {reason}"
    )


# ── Error ─────────────────────────────────────────────────────────────────────

def alert_error(cfg, message: str):
    return _send(cfg,
        f"🚨 <b>{cfg.PAIR_LABEL} — Error</b>\n"
        f"{message}"
    )

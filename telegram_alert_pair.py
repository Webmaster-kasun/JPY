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
    if balance_sgd is None:
        return ""
    mode   = " (paper)" if cfg.BOT_MODE == "paper" else ""
    pl_str = f"  unrealised {open_pl:+.2f}" if open_pl and open_pl != 0 else ""
    return f"💰 Balance   : <b>SGD {balance_sgd:,.2f}{mode}</b>{pl_str}\n"


# ── Startup ───────────────────────────────────────────────────────────────────

def alert_startup(cfg, balance_sgd=None, open_trades=0,
                  weekly_wins=0, weekly_losses=0, weekly_pnl=0.0):
    bal  = _bal_line(cfg, balance_sgd)
    wkly = (f"📊 This week : {weekly_wins}W {weekly_losses}L  SGD {weekly_pnl:+.0f}\n"
            if (weekly_wins + weekly_losses) > 0 else "📊 This week : No trades yet\n")
    mode_icon = "🟡" if cfg.BOT_MODE == "paper" else "🟢"
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
    total     = score.get("total", "")
    bal       = _bal_line(cfg, balance_sgd)
    date_str  = f"📅 Candle   : {str(candle_date)[:10]}\n" if candle_date else ""

    return _send(cfg,
        f"{'🟢' if direction == 'LONG' else '🔴'} "
        f"<b>{cfg.PAIR_LABEL} — {arrow}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{date_str}"
        f"📊 Score    : {total}/100  {stars}  {grade}\n"
        f"💹 Entry    : {sig.get('entry', ''):.5f}\n"
        f"✅ TP       : {sig.get('tp', ''):.5f}  (+{cfg.TP_PIPS}p  SGD +{cfg.TP_SGD})\n"
        f"❌ SL       : {sig.get('sl', ''):.5f}  (-{cfg.SL_PIPS}p  SGD -{cfg.SL_SGD})\n"
        f"📐 EMA9/21  : {sig.get('ema_fast', ''):.5f} / {sig.get('ema_slow', ''):.5f}\n"
        f"📉 RSI      : {sig.get('rsi', '')}   Stoch: {sig.get('stoch_k', '')}\n"
        f"{bal}"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


# ── No signal ─────────────────────────────────────────────────────────────────

def alert_no_signal(cfg, sig: dict, candle_date=None):
    date_str = f"📅 {str(candle_date)[:10]}  " if candle_date else ""
    return _send(cfg,
        f"⚪ <b>{cfg.PAIR_LABEL} — No signal</b>  {date_str}\n"
        f"ℹ️ {sig.get('reason', '')}\n"
        f"RSI {sig.get('rsi', '')}  Stoch {sig.get('stoch_k', '')}"
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

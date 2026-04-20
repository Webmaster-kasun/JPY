"""
settings.py — Load and expose all configuration
================================================
Reads settings.json + .env secrets into one place.
Import this everywhere instead of hardcoding values.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_BASE = Path(__file__).parent
_CFG  = json.loads((_BASE / "settings.json").read_text())

# ── OANDA credentials (from .env / Railway env vars) ──────────────────────────
OANDA_API_KEY    = os.getenv("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
OANDA_ENV        = os.getenv("OANDA_ENV", "practice")   # practice | live
BOT_MODE         = os.getenv("BOT_MODE",  "paper")      # paper | live

OANDA_BASE_URL = (
    _CFG["oanda"]["base_url_live"]
    if OANDA_ENV == "live"
    else _CFG["oanda"]["base_url_practice"]
)

# ── Telegram ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Pair ───────────────────────────────────────────────────────────────────────
PAIR          = _CFG["pair"]           # "USD_JPY"
PAIR_LABEL    = _CFG["pair_label"]     # "USD/JPY"
SYMBOL_YF     = _CFG["symbol_yf"]     # "USDJPY=X"

# ── Strategy ───────────────────────────────────────────────────────────────────
EMA_FAST      = _CFG["strategy"]["ema_fast"]
EMA_SLOW      = _CFG["strategy"]["ema_slow"]
RSI_PERIOD    = _CFG["strategy"]["rsi_period"]
RSI_MIN       = _CFG["strategy"]["rsi_min"]
RSI_MAX       = _CFG["strategy"]["rsi_max"]
GRANULARITY   = _CFG["strategy"]["granularity"]
CANDLES       = _CFG["strategy"]["candles"]

# ── Trade params ───────────────────────────────────────────────────────────────
TP_PIPS       = _CFG["trade"]["tp_pips"]
SL_PIPS       = _CFG["trade"]["sl_pips"]
PIP_SIZE      = _CFG["trade"]["pip_size"]
UNITS         = _CFG["trade"]["units"]
USD_SGD       = _CFG["trade"]["usd_sgd_rate"]
MAX_TRADES    = _CFG["trade"]["max_open_trades"]

# Derived SGD values
SGD_PER_PIP   = round(0.91 * USD_SGD, 4)      # per pip per mini lot
TP_SGD        = round(TP_PIPS * (UNITS / 10000) * SGD_PER_PIP, 2)
SL_SGD        = round(SL_PIPS * (UNITS / 10000) * SGD_PER_PIP, 2)

# ── Risk limits ────────────────────────────────────────────────────────────────
MAX_LOSS_WEEK = _CFG["risk"]["max_loss_per_week_sgd"]
MAX_TRADES_WK = _CFG["risk"]["max_trades_per_week"]
PAUSE_STREAK  = _CFG["risk"]["pause_on_loss_streak"]

# ── Schedule ───────────────────────────────────────────────────────────────────
RUN_HOUR_UTC  = _CFG["schedule"]["run_hour_utc"]
RUN_MIN_UTC   = _CFG["schedule"]["run_minute_utc"]

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_DIR       = _BASE / "logs"
SIGNAL_LOG    = str(LOG_DIR / "signal_log.csv")
TRADE_LOG     = str(LOG_DIR / "trade_journal.csv")
BOT_LOG       = str(LOG_DIR / "bot.log")


def summary():
    print(f"""
╔══════════════════════════════════════════╗
║  USD/JPY BOT  —  CONFIG SUMMARY         ║
╠══════════════════════════════════════════╣
║  Mode      : {BOT_MODE:<28}║
║  OANDA env : {OANDA_ENV:<28}║
║  Pair      : {PAIR_LABEL:<28}║
║  Units     : {UNITS:<28,}║
║  TP / SL   : {TP_PIPS} pips / {SL_PIPS} pips{' '*17}║
║  TP SGD    : ~SGD {TP_SGD:<23.2f}║
║  SL SGD    : ~SGD {SL_SGD:<23.2f}║
║  EMA       : {EMA_FAST}/{EMA_SLOW}  RSI: {RSI_MIN}–{RSI_MAX}{' '*14}║
╚══════════════════════════════════════════╝
""")


if __name__ == "__main__":
    summary()

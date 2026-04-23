"""
settings.py — USD/JPY Day Scalper configuration
================================================
Reads all values from environment variables (Railway) or falls back to
sensible defaults. Credentials are never hard-coded here.
"""

import os
from dotenv import load_dotenv

load_dotenv(override=False)   # Railway env vars always win over .env file

# ── OANDA credentials ─────────────────────────────────────────────────────────
OANDA_API_KEY    = os.environ.get("OANDA_API_KEY",    "").strip()
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "").strip()
OANDA_ENV        = os.environ.get("OANDA_ENV",        "practice").strip()
OANDA_BASE_URL   = (
    "https://api-fxtrade.oanda.com"
    if OANDA_ENV == "live"
    else "https://api-fxpractice.oanda.com"
)

# ── Bot mode ──────────────────────────────────────────────────────────────────
BOT_MODE = os.environ.get("BOT_MODE", "paper").strip()   # paper | demo | live

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = (os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
                    or os.environ.get("TELEGRAM_TOKEN", "").strip() or "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# ── Pair identity ─────────────────────────────────────────────────────────────
PAIR       = "USD_JPY"
PAIR_LABEL = "USD/JPY"
SYMBOL_YF  = "USDJPY=X"
GRANULARITY = "D"
CANDLES     = 100

# ── Strategy parameters ───────────────────────────────────────────────────────
EMA_FAST  = 9
EMA_SLOW  = 21
RSI_PERIOD    = 14
RSI_LONG_MAX  = 70
RSI_SHORT_MIN = 30
STOCH_K        = 14
STOCH_D        = 3
STOCH_LONG_MAX  = 80
STOCH_SHORT_MIN = 20

# ── Trade sizing ──────────────────────────────────────────────────────────────
TP_PIPS  = 15
SL_PIPS  = 10
PIP_SIZE = 0.01       # JPY pairs: 1 pip = 0.01
UNITS    = 50000      # 5 mini lots
USD_SGD  = 1.35       # approximate — used for P&L display only

TP_SGD = round(TP_PIPS * (UNITS / 10_000) * 0.91 * USD_SGD, 0)
SL_SGD = round(SL_PIPS * (UNITS / 10_000) * 0.91 * USD_SGD, 0)

# ── Risk gates ────────────────────────────────────────────────────────────────
MAX_TRADES_WK  = 7
MAX_LOSS_WEEK  = 500    # SGD
PAUSE_STREAK   = 3

# ── Paper trading ─────────────────────────────────────────────────────────────
PAPER_STARTING_CAPITAL = 10_000   # SGD

# ── Schedule (UTC) ────────────────────────────────────────────────────────────
RUN_TIMES_UTC = ["22:05", "14:35"]   # 06:05 SGT, 22:35 SGT
RUN_LABELS    = ["06:05 SGT — Tokyo open", "22:35 SGT — NY/London overlap"]

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR      = "logs"
BOT_LOG      = "logs/bot.log"
JOURNAL_FILE = "logs/trade_journal.csv"
SIGNAL_LOG   = "logs/signal_log.csv"

"""settings.py — Config loader for JPY Day Scalper"""
import os, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=False)  # Railway env vars always win

_BASE = Path(__file__).parent
_CFG  = json.loads((_BASE / "settings.json").read_text())

OANDA_API_KEY    = os.getenv("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
OANDA_ENV        = os.getenv("OANDA_ENV", "practice")   # "practice" = demo, "live" = real money
BOT_MODE         = os.getenv("BOT_MODE", "demo")       # "paper"=no orders, "demo"=orders on demo, "live"=orders on live
OANDA_BASE_URL   = (_CFG["oanda"]["base_url_live"] if OANDA_ENV == "live"
                    else _CFG["oanda"]["base_url_practice"])

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

PAIR       = _CFG["pair"]
PAIR_LABEL = _CFG["pair_label"]
SYMBOL_YF  = _CFG["symbol_yf"]

EMA_FAST        = _CFG["strategy"]["ema_fast"]
EMA_SLOW        = _CFG["strategy"]["ema_slow"]
RSI_PERIOD      = _CFG["strategy"]["rsi_period"]
RSI_LONG_MAX    = _CFG["strategy"]["rsi_long_max"]
RSI_SHORT_MIN   = _CFG["strategy"]["rsi_short_min"]
STOCH_K         = _CFG["strategy"]["stoch_k"]
STOCH_D         = _CFG["strategy"]["stoch_d"]
STOCH_LONG_MAX  = _CFG["strategy"]["stoch_long_max"]
STOCH_SHORT_MIN = _CFG["strategy"]["stoch_short_min"]
GRANULARITY     = _CFG["strategy"]["timeframe"]
CANDLES         = _CFG["strategy"]["candles"]

TP_PIPS    = _CFG["trade"]["tp_pips"]
SL_PIPS    = _CFG["trade"]["sl_pips"]
PIP_SIZE   = _CFG["trade"]["pip_size"]
UNITS      = _CFG["trade"]["units"]
USD_SGD    = _CFG["trade"]["usd_sgd_rate"]
MAX_TRADES_DAY          = _CFG["trade"]["max_trades_day"]
PAPER_STARTING_CAPITAL  = _CFG["trade"].get("paper_starting_capital", 10000)  # SGD — set to your actual account size

SGD_PER_PIP = round(0.91 * USD_SGD * (UNITS/10000), 4)
TP_SGD      = round(TP_PIPS * SGD_PER_PIP)
SL_SGD      = round(SL_PIPS * SGD_PER_PIP)

MAX_LOSS_WEEK = _CFG["risk"]["max_loss_per_week_sgd"]
MAX_TRADES_WK = _CFG["risk"]["max_trades_per_week"]
PAUSE_STREAK  = _CFG["risk"]["pause_on_loss_streak"]

RUN_TIMES_UTC = _CFG["schedule"]["run_times_utc"]
RUN_LABELS    = _CFG["schedule"]["labels"]

LOG_DIR    = _BASE / "logs"
SIGNAL_LOG = str(LOG_DIR / "signal_log.csv")
TRADE_LOG  = str(LOG_DIR / "trade_journal.csv")
BOT_LOG    = str(LOG_DIR / "bot.log")

def summary():
    tg = "configured" if TELEGRAM_TOKEN else "NOT SET"
    print(f"""
╔══════════════════════════════════════════════╗
║   JPY Day Scalper — CONFIG                  ║
╠══════════════════════════════════════════════╣
║  Mode      : {BOT_MODE:<30}║
║  OANDA env : {OANDA_ENV:<30}║
║  Units     : {UNITS:<30,}║
║  TP        : {TP_PIPS} pips  =  SGD {TP_SGD:<18}║
║  SL        : {SL_PIPS} pips  =  SGD {SL_SGD:<18}║
║  RR ratio  : 1:{TP_PIPS/SL_PIPS:.2f}{' '*25}║
║  Strategy  : EMA9/21 + RSI + Stochastic     ║
║  Telegram  : {tg:<30}║
╚══════════════════════════════════════════════╝
""")

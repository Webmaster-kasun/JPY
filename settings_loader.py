"""
settings_loader.py — Per-pair config loader
============================================
Loads a named settings JSON and returns a config object identical in shape
to what settings.py exposes, so all existing modules (signals.py, risk.py,
oanda_trader.py, telegram_alert.py) work without modification.

Usage:
    from settings_loader import load_pair_cfg
    cfg = load_pair_cfg("eurusd")   # loads settings_eurusd.json
    cfg = load_pair_cfg("gbpusd")   # loads settings_gbpusd.json
    cfg = load_pair_cfg("usdjpy")   # loads settings.json  (original JPY bot)
"""

import os, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=False)  # Railway env vars always win

_BASE = Path(__file__).parent

_JSON_MAP = {
    "usdjpy": "settings.json",
    "eurusd": "settings_eurusd.json",
    "gbpusd": "settings_gbpusd.json",
    "audusd": "settings_audusd.json",
    "usdchf": "settings_usdchf.json",
    "nzdusd": "settings_nzdusd.json",
    "usdcad": "settings_usdcad.json",
}


class PairConfig:
    """Attribute-style config object — mirrors the globals in settings.py."""

    def __init__(self, json_path: Path):
        _CFG = json.loads(json_path.read_text())

        # ── OANDA credentials — read from os.environ directly at instantiation ──
        # Using os.environ (not os.getenv) ensures we get Railway vars,
        # not any cached values from import-time load_dotenv()
        self.OANDA_API_KEY    = os.environ.get("OANDA_API_KEY", "").strip()
        self.OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "").strip()
        self.OANDA_ENV        = os.environ.get("OANDA_ENV", "practice").strip()
        self.BOT_MODE         = os.environ.get("BOT_MODE", "paper").strip()
        self.OANDA_BASE_URL   = (
            _CFG["oanda"]["base_url_live"]
            if self.OANDA_ENV == "live"
            else _CFG["oanda"]["base_url_practice"]
        )

        # ── Telegram ──────────────────────────────────────────────────────────
        self.TELEGRAM_TOKEN   = (os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
                                 or os.environ.get("TELEGRAM_TOKEN", "").strip() or "")
        self.TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

        # ── Pair identity ─────────────────────────────────────────────────────
        self.PAIR        = _CFG["pair"]           # e.g. "EUR_USD"
        self.PAIR_LABEL  = _CFG["pair_label"]     # e.g. "EUR/USD"
        self.SYMBOL_YF   = _CFG["symbol_yf"]      # e.g. "EURUSD=X"

        # ── Strategy ─────────────────────────────────────────────────────────
        s = _CFG["strategy"]
        self.EMA_FAST        = s["ema_fast"]
        self.EMA_SLOW        = s["ema_slow"]
        self.RSI_PERIOD      = s["rsi_period"]
        self.RSI_LONG_MAX    = s["rsi_long_max"]
        self.RSI_SHORT_MIN   = s["rsi_short_min"]
        self.STOCH_K         = s["stoch_k"]
        self.STOCH_D         = s["stoch_d"]
        self.STOCH_LONG_MAX  = s["stoch_long_max"]
        self.STOCH_SHORT_MIN = s["stoch_short_min"]
        self.GRANULARITY     = s["timeframe"]
        self.CANDLES         = s["candles"]
        self.MIN_SCORE       = s.get("min_score_to_trade", 50)

        # ── Trade ─────────────────────────────────────────────────────────────
        t = _CFG["trade"]
        self.TP_PIPS   = t["tp_pips"]
        self.SL_PIPS   = t["sl_pips"]
        self.PIP_SIZE  = t["pip_size"]
        self.UNITS     = t["units"]
        self.USD_SGD   = t["usd_sgd_rate"]
        self.MAX_TRADES_DAY         = t["max_trades_day"]
        self.PAPER_STARTING_CAPITAL = t.get("paper_starting_capital", 10000)

        # ── Derived P&L values ────────────────────────────────────────────────
        # For JPY pairs pip value = 0.91 × USD_SGD × lots  (JPY pip = 0.01, 1 pip ≈ $0.91 at 110)
        # For USD-quoted pairs (EUR/USD, GBP/USD) 1 pip = $10 per 100k, so 0.91 * USD_SGD * lots
        # The formula is the same; accuracy depends on PIP_SIZE being set correctly per pair.
        # SGD per pip calculation differs by pair type:
        # JPY pairs (USD/JPY): pip = 0.01, value ≈ 0.91 USD per 10k units
        # USD-quoted pairs (EUR/USD, GBP/USD): pip = 0.0001, value = units × pip_size × USD_SGD
        import math
        if self.PIP_SIZE >= 0.01:   # JPY pair
            self.SGD_PER_PIP = round(0.91 * self.USD_SGD * (self.UNITS / 10000), 4)
        else:                        # EUR/USD, GBP/USD — pip value =  per 10k units
            self.SGD_PER_PIP = round(self.UNITS * self.PIP_SIZE * self.USD_SGD, 4)
        self.TP_SGD      = round(self.TP_PIPS * self.SGD_PER_PIP)
        self.SL_SGD      = round(self.SL_PIPS * self.SGD_PER_PIP)

        # ── Risk ──────────────────────────────────────────────────────────────
        r = _CFG["risk"]
        self.MAX_LOSS_WEEK = r["max_loss_per_week_sgd"]
        self.MAX_TRADES_WK = r["max_trades_per_week"]
        self.PAUSE_STREAK  = r["pause_on_loss_streak"]

        # ── Schedule ──────────────────────────────────────────────────────────
        sc = _CFG["schedule"]
        self.RUN_TIMES_UTC = sc["run_times_utc"]
        self.RUN_LABELS    = sc["labels"]

        # ── Logging ───────────────────────────────────────────────────────────
        self.LOG_DIR    = _BASE / "logs"
        os.makedirs(self.LOG_DIR, exist_ok=True)  # ensure logs/ dir exists
        lg = _CFG.get("logging", {})
        self.SIGNAL_LOG = str(self.LOG_DIR / Path(lg.get("signal_log",   "logs/signal_log.csv")).name)
        self.TRADE_LOG  = str(self.LOG_DIR / Path(lg.get("trade_journal", "logs/trade_journal.csv")).name)
        self.BOT_LOG    = str(self.LOG_DIR / Path(lg.get("bot_log",       "logs/bot.log")).name)

    def summary(self):
        tg = "configured" if self.TELEGRAM_TOKEN else "NOT SET"
        print(f"""
╔══════════════════════════════════════════════╗
║   {self.PAIR_LABEL} Day Scalper — CONFIG          ║
╠══════════════════════════════════════════════╣
║  Mode      : {self.BOT_MODE:<30}║
║  OANDA env : {self.OANDA_ENV:<30}║
║  Pair      : {self.PAIR:<30}║
║  Units     : {self.UNITS:<30,}║
║  pip_size  : {self.PIP_SIZE:<30}║
║  TP        : {self.TP_PIPS} pips  =  SGD {self.TP_SGD:<18}║
║  SL        : {self.SL_PIPS} pips  =  SGD {self.SL_SGD:<18}║
║  RR ratio  : 1:{self.TP_PIPS/self.SL_PIPS:.2f}{' '*25}║
║  Strategy  : EMA9/21 + RSI + Stochastic     ║
║  Telegram  : {tg:<30}║
╚══════════════════════════════════════════════╝
""")


def load_pair_cfg(pair_key: str) -> PairConfig:
    """
    Load config for a given pair key: 'usdjpy', 'eurusd', or 'gbpusd'.
    Raises ValueError for unknown keys.
    """
    pair_key = pair_key.lower().replace("/", "").replace("_", "")
    if pair_key not in _JSON_MAP:
        raise ValueError(
            f"Unknown pair key '{pair_key}'. "
            f"Valid keys: {list(_JSON_MAP.keys())}"
        )
    json_path = _BASE / _JSON_MAP[pair_key]
    if not json_path.exists():
        raise FileNotFoundError(f"Settings file not found: {json_path}")
    return PairConfig(json_path)

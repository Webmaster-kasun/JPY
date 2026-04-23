# USD/JPY Pullback Bot

**Strategy:** EMA9/21 Pullback on Daily Chart  
**Backtest:** 83% WR — 5W/1L — SGD +399 over Jan–Apr 2026  
**Target:** SGD +92 per win / SGD −61 per loss (50,000 units)

---

## Folder Structure

```
jpyusd_live/
├── .github/
│   └── workflows/
│       └── daily_trade.yml   ← GitHub Actions daily runner
│
├── main.py                   ← Entry point (Railway + CLI)
├── bot.py                    ← Core orchestration logic
├── signals.py                ← Indicators + signal generation
├── oanda_trader.py           ← OANDA API + PaperTrader
├── calendar_filter.py        ← News blackout filter
├── telegram_alert.py         ← Telegram notifications
├── risk.py                   ← Position sizing + risk gates
├── journal.py                ← Trade logging (CSV)
├── logger.py                 ← Unified logging
├── backtest_usdjpy.py        ← Walk-forward backtester
├── settings.py               ← Config loader
│
├── settings.json             ← All strategy parameters
├── requirements.txt
├── Procfile                  ← Railway worker
├── railway.json              ← Railway deployment config
├── .env.example              ← Secrets template
├── .gitignore
│
├── logs/                     ← Auto-created
│   ├── bot.log
│   ├── signal_log.csv
│   ├── trade_journal.csv
│   └── backtest_usdjpy.csv
└── outputs/                  ← Reports & exports
```

---

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Copy and fill in credentials
cp .env.example .env
# Edit .env with your OANDA keys + Telegram details

# 3. Test Telegram
python main.py --test-tg

# 4. Run backtest
python main.py --backtest

# 5. Paper trade (no real orders)
python main.py --once         # BOT_MODE=paper in .env

# 6. View journal
python main.py --journal

# 7. Risk summary
python main.py --risk
```

---

## Strategy Rules

| Condition | Value |
|---|---|
| Trend | EMA9 > EMA21 (uptrend only) |
| Pullback | Previous candle RED |
| Bounce | Current candle GREEN |
| RSI filter | RSI(14) between 50 and 77 |
| TP | 15 pips |
| SL | 10 pips |
| Units | 50,000 (5 mini lots) |
| RR | 1.5 : 1 |

---

## Deployment Options

### Option A — GitHub Actions (free, recommended to start)
1. Push repo to GitHub
2. Go to Settings → Secrets → add: `OANDA_API_KEY`, `OANDA_ACCOUNT_ID`, `OANDA_ENV`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `BOT_MODE`
3. Runs automatically at 16:10 UTC Mon–Fri
4. Manual trigger available in Actions tab

### Option B — Railway (always-on)
1. Connect repo to Railway
2. Add env vars in Railway dashboard
3. Deploy — `Procfile` sets the start command

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `OANDA_API_KEY` | OANDA REST API token | `abc123...` |
| `OANDA_ACCOUNT_ID` | OANDA account number | `101-001-...` |
| `OANDA_ENV` | `practice` or `live` | `practice` |
| `TELEGRAM_BOT_TOKEN` | From @BotFather | `123:ABC...` |
| `TELEGRAM_CHAT_ID` | From @userinfobot | `-100...` |
| `BOT_MODE` | `paper` or `live` | `paper` |

---

## Going Live Checklist

- [ ] Backtest passes on fresh data
- [ ] Paper mode running cleanly for 1+ weeks
- [ ] Telegram alerts working
- [ ] OANDA practice account tested
- [ ] Set `BOT_MODE=live` and `OANDA_ENV=live`
- [ ] Fund live OANDA account
- [ ] Monitor first 5 live trades closely

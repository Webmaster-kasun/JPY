"""
oanda_trader.py — OANDA v20 REST API integration
=================================================
BOT_MODE=paper  -> PaperTrader (yfinance, no real orders)
BOT_MODE=live   -> OandaTrader (real OANDA API)
"""

import requests
import pandas as pd
import settings as cfg
import logger as log


class OandaTrader:

    def __init__(self):
        self.api_key    = cfg.OANDA_API_KEY
        self.account_id = cfg.OANDA_ACCOUNT_ID
        self.base_url   = cfg.OANDA_BASE_URL
        self.headers    = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type" : "application/json",
        }

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}{endpoint}"
        try:
            r = requests.get(url, headers=self.headers, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"OANDA GET error: {e}")
            return {}

    def _post(self, endpoint, payload):
        url = f"{self.base_url}{endpoint}"
        try:
            r = requests.post(url, headers=self.headers, json=payload, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"OANDA POST error: {e}")
            return {}

    def get_account_summary(self):
        data = self._get(f"/v3/accounts/{self.account_id}/summary")
        acc  = data.get("account", {})
        return {
            "balance"    : float(acc.get("balance", 0)),
            "nav"        : float(acc.get("NAV", 0)),
            "open_pl"    : float(acc.get("unrealizedPL", 0)),
            "open_trades": int(acc.get("openTradeCount", 0)),
        }

    def get_candles(self, instrument=None, granularity=None, count=None):
        instrument  = instrument  or cfg.PAIR
        granularity = granularity or cfg.GRANULARITY
        count       = count       or cfg.CANDLES
        params = {"granularity": granularity, "count": count, "price": "M"}
        data   = self._get(f"/v3/instruments/{instrument}/candles", params)
        rows   = []
        for c in data.get("candles", []):
            if not c.get("complete", True):
                continue
            mid = c["mid"]
            rows.append({
                "Date"  : pd.to_datetime(c["time"]).tz_localize(None),
                "Open"  : float(mid["o"]),
                "High"  : float(mid["h"]),
                "Low"   : float(mid["l"]),
                "Close" : float(mid["c"]),
                "Volume": int(c.get("volume", 0)),
            })
        df = pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)
        log.info(f"Fetched {len(df)} candles ({instrument} {granularity})")
        return df

    def get_price(self, instrument=None):
        instrument = instrument or cfg.PAIR
        data = self._get(f"/v3/accounts/{self.account_id}/pricing",
                         params={"instruments": instrument})
        prices = data.get("prices", [])
        if not prices:
            return {}
        p   = prices[0]
        bid = float(p["bids"][0]["price"])
        ask = float(p["asks"][0]["price"])
        return {"bid": bid, "ask": ask, "mid": round((bid + ask) / 2, 5)}

    def place_order(self, direction, entry, tp, sl, units=None):
        units        = units or cfg.UNITS
        signed_units = units if direction == "LONG" else -units
        payload = {
            "order": {
                "type"       : "MARKET",
                "instrument" : cfg.PAIR,
                "units"      : str(signed_units),
                "timeInForce": "FOK",
                "takeProfitOnFill": {"price": str(tp), "timeInForce": "GTC"},
                "stopLossOnFill"  : {"price": str(sl), "timeInForce": "GTC"},
            }
        }
        log.info(f"Placing {direction} | {signed_units:+,} units | TP={tp} SL={sl}")
        result = self._post(f"/v3/accounts/{self.account_id}/orders", payload)
        if result.get("orderFillTransaction"):
            fill = result["orderFillTransaction"]
            return {
                "status"    : "FILLED",
                "trade_id"  : fill.get("tradeOpened", {}).get("tradeID"),
                "fill_price": float(fill.get("price", entry)),
                "direction" : direction,
                "units"     : signed_units,
                "tp"        : tp,
                "sl"        : sl,
            }
        log.warning(f"Order not filled: {result}")
        return {"status": "FAILED", "raw": result}

    def get_open_trades(self, instrument=None):
        instrument = instrument or cfg.PAIR
        data   = self._get(f"/v3/accounts/{self.account_id}/openTrades")
        trades = data.get("trades", [])
        return [t for t in trades if t.get("instrument") == instrument]

    def has_open_trade(self):
        return len(self.get_open_trades()) > 0

    def close_trade(self, trade_id):
        result = self._post(
            f"/v3/accounts/{self.account_id}/trades/{trade_id}/close", {})
        log.info(f"Closed trade {trade_id}")
        return result

    def close_all(self):
        result = self._post(
            f"/v3/accounts/{self.account_id}/positions/{cfg.PAIR}/close",
            {"longUnits": "ALL", "shortUnits": "ALL"})
        log.info("Closed all positions")
        return result


class PaperTrader:
    """No-op trader for paper mode — uses yfinance for candles."""

    def __init__(self):
        log.info("PaperTrader active — no real orders")
        self._trades = []

    def get_account_summary(self):
        return {"balance": 10000.0, "nav": 10000.0,
                "open_pl": 0.0, "open_trades": len(self._trades)}

    def get_candles(self, instrument=None, granularity=None, count=None):
        """FIX BUG 4: robust yfinance MultiIndex handling."""
        import yfinance as yf
        try:
            raw = yf.download(
                cfg.SYMBOL_YF, period="6mo", interval="1d",
                progress=False, auto_adjust=True
            )
            if raw.empty:
                log.error("yfinance returned empty dataframe")
                return pd.DataFrame()

            # FIX: flatten MultiIndex properly — handles both (col,) and (col, ticker)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)

            # Keep only OHLCV columns
            needed = ["Open", "High", "Low", "Close", "Volume"]
            raw = raw[[c for c in needed if c in raw.columns]]

            raw.index.name = "Date"
            df = raw.reset_index()
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            df = df.dropna(subset=["Close"])
            df = df.sort_values("Date").reset_index(drop=True)

            log.info(f"[PAPER] yfinance fetched {len(df)} candles")
            return df

        except Exception as e:
            log.error(f"[PAPER] yfinance error: {e}")
            return pd.DataFrame()

    def get_price(self, instrument=None):
        df = self.get_candles()
        if df.empty:
            return {}
        c = float(df["Close"].iloc[-1])
        return {"bid": c - 0.001, "ask": c + 0.001, "mid": c}

    def place_order(self, direction, entry, tp, sl, units=None):
        units = units or cfg.UNITS
        trade = {
            "status"    : "FILLED",
            "trade_id"  : f"PAPER_{len(self._trades)+1:03d}",
            "fill_price": entry,
            "direction" : direction,
            "units"     : units,
            "tp"        : tp,
            "sl"        : sl,
        }
        self._trades.append(trade)
        log.info(f"[PAPER] {direction} {units:,} @ {entry} | TP={tp} SL={sl}")
        return trade

    def get_open_trades(self, instrument=None):
        return self._trades

    def has_open_trade(self):
        return len(self._trades) > 0

    def close_trade(self, trade_id):
        self._trades = [t for t in self._trades if t["trade_id"] != trade_id]
        return {"status": "CLOSED"}

    def close_all(self):
        self._trades = []
        return {"status": "ALL_CLOSED"}


def get_trader():
    if cfg.BOT_MODE == "live":
        log.info("LIVE mode — OandaTrader")
        return OandaTrader()
    log.info("PAPER mode — PaperTrader")
    return PaperTrader()

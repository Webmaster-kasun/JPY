"""
oanda_trader_pair.py — Per-pair OANDA REST API integration
===========================================================
Same logic as oanda_trader.py but all cfg references use an explicit cfg
object so EUR/USD and GBP/USD use the correct PAIR, PIP_SIZE, TP/SL.

USD/JPY still uses the original oanda_trader.py — untouched.
"""

import requests
import pandas as pd
import logger as log


class OandaTrader:

    def __init__(self, cfg):
        import os as _os
        self.cfg        = cfg
        # Read credentials from os.environ at instantiation — never from cached cfg
        self.api_key    = _os.environ.get("OANDA_API_KEY", "").strip() or cfg.OANDA_API_KEY
        self.account_id = _os.environ.get("OANDA_ACCOUNT_ID", "").strip() or cfg.OANDA_ACCOUNT_ID
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
            log.error(f"[{self.cfg.PAIR_LABEL}] OANDA GET error [{endpoint}]: {e}")
            return {}

    def _post(self, endpoint, payload):
        url = f"{self.base_url}{endpoint}"
        try:
            r = requests.post(url, headers=self.headers, json=payload, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"[{self.cfg.PAIR_LABEL}] OANDA POST error [{endpoint}]: {e}")
            return {}

    def _put(self, endpoint, payload):
        url = f"{self.base_url}{endpoint}"
        try:
            r = requests.put(url, headers=self.headers, json=payload, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"[{self.cfg.PAIR_LABEL}] OANDA PUT error [{endpoint}]: {e}")
            return {}

    def get_account_summary(self):
        data = self._get(f"/v3/accounts/{self.account_id}/summary")
        if not data:
            return {"balance": None, "balance_sgd": None,
                    "currency": "SGD", "nav": None,
                    "open_pl": 0.0, "open_trades": 0}

        acc      = data.get("account", {})
        balance  = acc.get("balance")
        currency = acc.get("currency", "SGD")
        nav      = acc.get("NAV")
        open_pl  = acc.get("unrealizedPL", 0)
        open_trades = int(acc.get("openTradeCount", 0))

        try:
            balance = round(float(balance), 2) if balance is not None else None
        except (ValueError, TypeError):
            balance = None
        try:
            nav = round(float(nav), 2) if nav is not None else balance
        except (ValueError, TypeError):
            nav = balance
        try:
            open_pl = round(float(open_pl), 2)
        except (ValueError, TypeError):
            open_pl = 0.0

        return {
            "balance"    : balance,
            "balance_sgd": balance,
            "currency"   : currency,
            "nav"        : nav,
            "open_pl"    : open_pl,
            "open_trades": open_trades,
        }

    def get_candles(self, instrument=None, granularity=None, count=None):
        instrument  = instrument  or self.cfg.PAIR
        granularity = granularity or self.cfg.GRANULARITY
        count       = count       or self.cfg.CANDLES
        data = self._get(
            f"/v3/instruments/{instrument}/candles",
            params={"granularity": granularity, "count": count, "price": "M"}
        )
        candles = data.get("candles", [])
        if not candles:
            log.error(f"[{self.cfg.PAIR_LABEL}] get_candles: empty response")
            return pd.DataFrame()
        rows = []
        for c in candles:
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
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)
        log.info(f"[{self.cfg.PAIR_LABEL}] Fetched {len(df)} candles ({instrument} {granularity})")
        return df

    def get_price(self, instrument=None):
        instrument = instrument or self.cfg.PAIR
        data = self._get(
            f"/v3/accounts/{self.account_id}/pricing",
            params={"instruments": instrument},
        )
        prices = data.get("prices", [])
        if not prices:
            return {}
        p   = prices[0]
        bid = float(p["bids"][0]["price"])
        ask = float(p["asks"][0]["price"])
        return {"bid": bid, "ask": ask, "mid": round((bid + ask) / 2, 5)}

    def place_order(self, direction, entry, tp, sl, units=None):
        """
        Place a MARKET order then recalculate TP/SL from the ACTUAL fill price.

        Why: TP/SL passed in are calculated from the daily candle close.
        The actual fill price can differ by 5-30 pips due to time elapsed.
        Recalculating from fill price guarantees correct pip distances always.
        """
        units        = units or self.cfg.UNITS
        signed_units = units if direction == "LONG" else -units
        pip          = self.cfg.PIP_SIZE

        # Step 1: Place plain market order WITHOUT TP/SL attached
        payload = {
            "order": {
                "type"       : "MARKET",
                "instrument" : self.cfg.PAIR,
                "units"      : str(signed_units),
                "timeInForce": "FOK",
            }
        }
        log.info(f"[{self.cfg.PAIR_LABEL}] Placing {direction} | {signed_units:+,} units")
        result = self._post(f"/v3/accounts/{self.account_id}/orders", payload)

        if not result.get("orderFillTransaction"):
            log.warning(f"[{self.cfg.PAIR_LABEL}] Order not filled: {result}")
            return {"status": "FAILED", "raw": result}

        # Step 2: Get actual fill price from OANDA response
        fill_tx    = result["orderFillTransaction"]
        trade_id   = fill_tx.get("tradeOpened", {}).get("tradeID")
        fill_price = round(float(fill_tx.get("price", entry)), 5)
        log.info(f"[{self.cfg.PAIR_LABEL}] Filled @ {fill_price}  (signal entry was {entry})")

        drift_pips = abs(fill_price - entry) / pip
        if drift_pips > 0.5:
            log.info(f"[{self.cfg.PAIR_LABEL}] Price drift: {drift_pips:.1f} pips — "
                     f"recalculating TP/SL from fill price {fill_price}")

        # Step 3: Recalculate TP/SL from FILL PRICE (not signal entry)
        if direction == "LONG":
            tp_from_fill = round(fill_price + self.cfg.TP_PIPS * pip, 5)
            sl_from_fill = round(fill_price - self.cfg.SL_PIPS * pip, 5)
        else:
            tp_from_fill = round(fill_price - self.cfg.TP_PIPS * pip, 5)
            sl_from_fill = round(fill_price + self.cfg.SL_PIPS * pip, 5)

        log.info(f"[{self.cfg.PAIR_LABEL}] TP={tp_from_fill} (+{self.cfg.TP_PIPS}pip from fill) "
                 f"SL={sl_from_fill} (-{self.cfg.SL_PIPS}pip from fill)")

        # Step 4: Attach TP/SL via trade modify endpoint
        modify_payload = {
            "takeProfit": {"price": f"{tp_from_fill:.5f}", "timeInForce": "GTC"},
            "stopLoss"  : {"price": f"{sl_from_fill:.5f}", "timeInForce": "GTC"},
        }
        modify_result = self._put(
            f"/v3/accounts/{self.account_id}/trades/{trade_id}/orders",
            modify_payload
        )
        if modify_result.get("relatedTransactionIDs"):
            log.info(f"[{self.cfg.PAIR_LABEL}] TP/SL attached to trade {trade_id} ✅")
        else:
            log.warning(f"[{self.cfg.PAIR_LABEL}] TP/SL attach may have failed: {modify_result}")

        return {
            "status"    : "FILLED",
            "trade_id"  : trade_id,
            "fill_price": fill_price,
            "direction" : direction,
            "units"     : signed_units,
            "tp"        : tp_from_fill,
            "sl"        : sl_from_fill,
        }

    def get_open_trades(self, instrument=None):
        instrument = instrument or self.cfg.PAIR
        data   = self._get(f"/v3/accounts/{self.account_id}/openTrades")
        trades = data.get("trades", [])
        return [t for t in trades if t.get("instrument") == instrument]

    def has_open_trade(self):
        return len(self.get_open_trades()) > 0

    def close_trade(self, trade_id):
        result = self._post(
            f"/v3/accounts/{self.account_id}/trades/{trade_id}/close", {})
        log.info(f"[{self.cfg.PAIR_LABEL}] Closed trade {trade_id}")
        return result

    def close_all(self):
        result = self._post(
            f"/v3/accounts/{self.account_id}/positions/{self.cfg.PAIR}/close",
            {"longUnits": "ALL", "shortUnits": "ALL"},
        )
        log.info(f"[{self.cfg.PAIR_LABEL}] Closed all positions")
        return result


class PaperTrader:
    """Paper mode — uses yfinance for candles, no real orders."""

    def __init__(self, cfg):
        self.cfg     = cfg
        self._trades = []
        log.info(f"[{cfg.PAIR_LABEL}] PaperTrader active — no real orders")

    def _put(self, endpoint, payload):
        url = f"{self.base_url}{endpoint}"
        try:
            r = requests.put(url, headers=self.headers, json=payload, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"[{self.cfg.PAIR_LABEL}] OANDA PUT error [{endpoint}]: {e}")
            return {}

    def get_account_summary(self):
        try:
            import journal_pair as jp
            pnl = jp.running_sgd(self.cfg)
        except Exception:
            pnl = 0.0
        bal = round(self.cfg.PAPER_STARTING_CAPITAL + pnl, 2)
        return {
            "balance"    : bal,
            "balance_sgd": bal,
            "currency"   : "SGD",
            "nav"        : bal,
            "open_pl"    : 0.0,
            "open_trades": len(self._trades),
        }

    def get_candles(self, instrument=None, granularity=None, count=None):
        import yfinance as yf
        try:
            raw = yf.download(self.cfg.SYMBOL_YF, period="6mo", interval="1d",
                              progress=False, auto_adjust=True)
            if raw.empty:
                return pd.DataFrame()
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            needed = ["Open", "High", "Low", "Close", "Volume"]
            raw = raw[[c for c in needed if c in raw.columns]]
            raw.index.name = "Date"
            df = raw.reset_index()
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            return df.dropna(subset=["Close"]).sort_values("Date").reset_index(drop=True)
        except Exception as e:
            log.error(f"[{self.cfg.PAIR_LABEL}] yfinance error: {e}")
            return pd.DataFrame()

    def get_price(self, instrument=None):
        df = self.get_candles()
        if df.empty:
            return {}
        c = float(df["Close"].iloc[-1])
        return {"bid": c - 0.0001, "ask": c + 0.0001, "mid": c}

    def place_order(self, direction, entry, tp, sl, units=None):
        units = units or self.cfg.UNITS
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


def get_trader(cfg=None):
    """
    SIMPLE RULE:
    If OANDA_API_KEY and OANDA_ACCOUNT_ID exist in environment → OandaTrader (real balance).
    If credentials missing → PaperTrader (fake balance).
    BOT_MODE only controls whether orders are placed, not which balance is shown.
    """
    import os, sys
    # Read DIRECTLY from os.environ at call time — bypasses any import-time caching
    api_key    = os.environ.get("OANDA_API_KEY", "").strip()
    account_id = os.environ.get("OANDA_ACCOUNT_ID", "").strip()

    if api_key and account_id:
        mode = (cfg.BOT_MODE if cfg else None) or os.environ.get("BOT_MODE", "paper")
        log.info(f"{mode.upper()} mode — OandaTrader (OANDA API | real balance)")
        if cfg:
            return OandaTrader(cfg)
        return OandaTrader()

    log.warning("No OANDA credentials in environment — using PaperTrader (fake balance)")
    if cfg:
        return PaperTrader(cfg)
    return PaperTrader()

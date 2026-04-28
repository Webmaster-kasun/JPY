"""
bot_pair.py — Pair-agnostic bot cycle
======================================
Identical logic to bot.py but accepts an explicit cfg object instead of
importing the global settings module.  This lets multi_pair_main.py run
EUR/USD and GBP/USD through the same engine while leaving the original
bot.py + settings.py (USD/JPY) completely untouched.

Called by:
    multi_pair_main.py   — the new 3-pair scheduler
    main_eurusd.py       — standalone EUR/USD runner
    main_gbpusd.py       — standalone GBP/USD runner
"""

from datetime import datetime, timezone

import logger as log
import journal_pair as jp
import telegram_alert_pair as tgp
from signals_pair import get_signal, print_signal
from calendar_filter import is_safe_to_trade, get_session_label
from risk_pair import check_risk_limits
from oanda_trader_pair import get_trader


def run(cfg):
    """Execute one full bot cycle for the given pair config."""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        day = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][now.weekday()]
        log.info(f"[{cfg.PAIR_LABEL}] Weekend ({day}) — skipping, forex markets closed")
        return

    # Block Friday NY session (14:00 UTC = 22:00 SGT onwards)
    # Trades placed Friday night stay open over weekend → Monday gap risk
    if now.weekday() == 4 and now.hour >= 14:
        log.info(f"[{cfg.PAIR_LABEL}] Friday NY session ({now.strftime('%H:%M UTC')}) — "
                 f"skipping to avoid weekend gap risk")
        return
    log.info(f"═══ {cfg.PAIR_LABEL} cycle: {now.strftime('%Y-%m-%d %H:%M UTC')} ═══")

    trader = get_trader(cfg)

    # ── Account status ────────────────────────────────────────────────────────
    acct        = trader.get_account_summary()
    balance_sgd = acct.get("balance_sgd") if acct.get("balance_sgd") is not None \
                  else acct.get("balance")
    open_trades = acct.get("open_trades", 0)
    open_pl     = acct.get("open_pl", 0.0)
    currency    = acct.get("currency", "SGD")

    if balance_sgd is not None:
        log.info(f"[{cfg.PAIR_LABEL}] Balance: {currency} {balance_sgd:.2f}  "
                 f"open_pl={open_pl:+.2f}  trades={open_trades}")
    else:
        log.warning(f"[{cfg.PAIR_LABEL}] Could not fetch account balance from OANDA")

    # ── Weekly stats ──────────────────────────────────────────────────────────
    wk = jp.weekly_stats(cfg)

    tgp.alert_session_start(
        cfg           = cfg,
        session_label = get_session_label(now),
        balance_sgd   = balance_sgd,
        open_trades   = open_trades,
        open_pl       = open_pl,
        weekly_pnl    = wk["net_sgd"],
        weekly_wins   = wk["wins"],
        weekly_losses = wk["losses"],
    )

    # ── Fetch candles ─────────────────────────────────────────────────────────
    df = trader.get_candles()
    if df is None or df.empty or len(df) < 20:
        log.error(f"[{cfg.PAIR_LABEL}] No candle data — aborting cycle")
        tgp.alert_error(cfg, "Could not fetch candle data from OANDA")
        log.info(f"═══ {cfg.PAIR_LABEL} cycle complete (no data) ═══")
        return

    candle_date = df["Date"].iloc[-1]

    # ── Signal ────────────────────────────────────────────────────────────────
    sig = get_signal(df, cfg)
    print_signal(sig, cfg, candle_date)
    jp.log_signal(sig, candle_date, cfg)

    # ── Safety checks ─────────────────────────────────────────────────────────
    safe, reason = is_safe_to_trade(now)
    if not safe:
        log.info(f"[{cfg.PAIR_LABEL}] Paused: {reason}")
        tgp.alert_risk_pause(cfg, reason)
        log.info(f"═══ {cfg.PAIR_LABEL} cycle complete (paused) ═══")
        return

    risk_ok, risk_reason = check_risk_limits(cfg)
    if not risk_ok:
        log.warning(f"[{cfg.PAIR_LABEL}] Risk limit: {risk_reason}")
        tgp.alert_risk_pause(cfg, risk_reason)
        log.info(f"═══ {cfg.PAIR_LABEL} cycle complete (risk) ═══")
        return

    # ── No signal ─────────────────────────────────────────────────────────────
    if sig["signal"] == "NONE":
        log.info(f"[{cfg.PAIR_LABEL}] No signal: {sig['reason']}")
        tgp.alert_no_signal(cfg, sig, candle_date)
        log.info(f"═══ {cfg.PAIR_LABEL} cycle complete (no signal) ═══")
        return

    # ── Already in trade ──────────────────────────────────────────────────────
    if trader.has_open_trade():
        log.info(f"[{cfg.PAIR_LABEL}] Open trade exists — skipping new signal")
        log.info(f"═══ {cfg.PAIR_LABEL} cycle complete (trade open) ═══")
        return

    # ── Score filter ─────────────────────────────────────────────────────────
    score_val = (sig.get('score') or {}).get('total', 0)
    if score_val < cfg.MIN_SCORE:
        log.info(f"[{cfg.PAIR_LABEL}] Score {score_val}/100 below minimum {cfg.MIN_SCORE} — skipping")
        tgp.alert_weak_signal(cfg, sig, candle_date, score_val, cfg.MIN_SCORE)
        log.info(f"═══ {cfg.PAIR_LABEL} cycle complete (weak signal) ═══")
        return

    # ── Price drift filter ───────────────────────────────────────────────────
    # Check live price hasn't drifted more than MAX_DRIFT_PIPS from signal entry
    # If it has, the candle-based signal is stale — skip to avoid bad entry
    MAX_DRIFT_PIPS = 20
    try:
        live = trader.get_price()
        if live:
            live_mid = (live["bid"] + live["ask"]) / 2
            drift_pips = abs(live_mid - sig["entry"]) / cfg.PIP_SIZE
            if drift_pips > MAX_DRIFT_PIPS:
                log.info(f"[{cfg.PAIR_LABEL}] Price drifted {drift_pips:.1f} pips from signal entry "
                         f"({sig['entry']:.5f} → {live_mid:.5f}) — signal stale, skipping")
                tgp.alert_drift_skip(cfg, sig, candle_date, drift_pips, MAX_DRIFT_PIPS)
                log.info(f"═══ {cfg.PAIR_LABEL} cycle complete (stale signal — price drift) ═══")
                return
            log.info(f"[{cfg.PAIR_LABEL}] Price drift OK: {drift_pips:.1f} pips (max {MAX_DRIFT_PIPS})")
    except Exception as e:
        log.warning(f"[{cfg.PAIR_LABEL}] Could not check live price for drift: {e}")

    # ── Place order ───────────────────────────────────────────────────────────
    log.info(f"[{cfg.PAIR_LABEL}] Signal: {sig['signal']} @ {sig['entry']}  score={score_val}")
    tgp.alert_signal(cfg, sig, candle_date, balance_sgd=balance_sgd)

    if cfg.BOT_MODE == "paper":
        log.info(f"[{cfg.PAIR_LABEL}][PAPER] Signal only — no order placed: "
                 f"{sig['signal']} @ {sig['entry']} TP={sig['tp']} SL={sig['sl']}")
        log.info(f"═══ {cfg.PAIR_LABEL} cycle complete (paper — signal only) ═══")
        return

    fill = trader.place_order(
        direction = sig["signal"],
        entry     = sig["entry"],
        tp        = sig["tp"],
        sl        = sig["sl"],
    )

    if fill.get("status") == "FILLED":
        acct2       = trader.get_account_summary()
        bal_after   = acct2.get("balance_sgd") if acct2.get("balance_sgd") is not None \
                      else acct2.get("balance")
        log.info(f"[{cfg.PAIR_LABEL}] Order filled: {fill.get('trade_id')} @ {fill.get('fill_price')}")
        tgp.alert_order_filled(cfg, fill, balance_sgd=bal_after)
    else:
        log.error(f"[{cfg.PAIR_LABEL}] Order failed: {fill}")
        tgp.alert_error(cfg, f"Order failed: {fill.get('status')}")

    log.info(f"═══ {cfg.PAIR_LABEL} cycle complete ═══")

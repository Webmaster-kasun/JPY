"""
bot.py — JPY Day Scalper cycle orchestration
=============================================
Fixed:
  - Balance uses explicit None check (not 'or' which breaks on 0.0)
  - Score passed to Telegram signal alert
  - Open P&L shown in session message
"""

from datetime import datetime, timezone
import settings as cfg
import logger as log
import journal
import telegram_alert as tg
from signals import get_signal, print_signal
from calendar_filter import is_safe_to_trade, get_session_label
from usd_filter import get_dxy_direction, is_trade_allowed
from oanda_trader import get_trader
from risk import check_risk_limits


def run():
    """Execute one full bot cycle."""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        day = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][now.weekday()]
        log.info(f"[USD/JPY] Weekend ({day}) — skipping, forex markets closed")
        return

    # Block Friday NY session (14:00 UTC = 22:00 SGT onwards)
    # Trades placed Friday night stay open over weekend → Monday gap risk
    if now.weekday() == 4 and now.hour >= 14:
        log.info(f"[USD/JPY] Friday NY session ({now.strftime('%H:%M UTC')}) — "
                 f"skipping to avoid weekend gap risk")
        return
    log.info(f"═══ Scalper cycle: {now.strftime('%Y-%m-%d %H:%M UTC')} ═══")

    trader = get_trader()

    # ── Account status ────────────────────────────────────────────────────────
    acct        = trader.get_account_summary()
    # Explicit None check — 'or' breaks when balance is legitimately 0.0
    balance_sgd = acct.get("balance_sgd") if acct.get("balance_sgd") is not None \
                  else acct.get("balance")
    open_trades = acct.get("open_trades", 0)
    open_pl     = acct.get("open_pl", 0.0)
    currency    = acct.get("currency", "SGD")

    if balance_sgd is not None:
        log.info(f"Balance: {currency} {balance_sgd:.2f}  open_pl={open_pl:+.2f}  trades={open_trades}")
    else:
        log.warning("Could not fetch account balance from OANDA")

    # ── Weekly stats ──────────────────────────────────────────────────────────
    wk          = journal.weekly_stats()
    session_lbl = get_session_label(now)

    tg.alert_session_start(
        session_label = session_lbl,
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
        log.error("No candle data — aborting cycle")
        tg.alert_error("Could not fetch candle data from OANDA")
        log.info("═══ Cycle complete (no data) ═══")
        return

    candle_date = df["Date"].iloc[-1]

    # ── Signal ────────────────────────────────────────────────────────────────
    sig = get_signal(df)
    print_signal(sig, candle_date)
    journal.log_signal(sig, candle_date)

    # ── Safety checks ─────────────────────────────────────────────────────────
    safe, reason = is_safe_to_trade(now)
    if not safe:
        log.info(f"Paused: {reason}")
        tg.alert_risk_pause(reason)
        log.info("═══ Cycle complete (paused) ═══")
        return

    risk_ok, risk_reason = check_risk_limits()
    if not risk_ok:
        log.warning(f"Risk limit: {risk_reason}")
        tg.alert_risk_pause(risk_reason)
        log.info("═══ Cycle complete (risk) ═══")
        return

    # ── No signal ─────────────────────────────────────────────────────────────
    if sig["signal"] == "NONE":
        log.info(f"No signal: {sig['reason']}")
        tg.alert_no_signal(sig, candle_date)
        log.info("═══ Cycle complete (no signal) ═══")
        return

    # ── Already in trade ──────────────────────────────────────────────────────
    if trader.has_open_trade():
        log.info("Open trade exists — skipping new signal")
        log.info("═══ Cycle complete (trade open) ═══")
        return

    # ── Score filter ─────────────────────────────────────────────────────────
    score_val = (sig.get('score') or {}).get('total', 0)
    if score_val < cfg.MIN_SCORE:
        log.info(f"Score {score_val}/100 below minimum {cfg.MIN_SCORE} — signal too weak, skipping")
        tg.alert_weak_signal(sig, candle_date, score_val, cfg.MIN_SCORE)
        log.info("═══ Cycle complete (weak signal) ═══")
        return

    # ── Price drift filter ───────────────────────────────────────────────────
    # Signal entry = daily candle close. Fill price = live market now.
    # If price has drifted > 20 pips, SL ends up in wrong place → skip.
    MAX_DRIFT_PIPS = 20
    try:
        live = trader.get_price()
        if live:
            live_mid  = (live["bid"] + live["ask"]) / 2
            drift_pips = abs(live_mid - sig["entry"]) / cfg.PIP_SIZE
            if drift_pips > MAX_DRIFT_PIPS:
                log.info(f"[USD/JPY] Price drifted {drift_pips:.1f} pips from signal "
                         f"entry ({sig['entry']:.3f} → {live_mid:.3f}) — stale signal, skipping")
                tg.alert_error(f"Stale signal skipped — price drifted {drift_pips:.0f} pips "
                               f"(max {MAX_DRIFT_PIPS}). No order placed.")
                log.info("═══ Cycle complete (stale signal — price drift) ═══")
                return
            log.info(f"[USD/JPY] Price drift OK: {drift_pips:.1f} pips")
    except Exception as e:
        log.warning(f"[USD/JPY] Could not check live price: {e}")

    # ── USD Strength Filter (DXY) ────────────────────────────────────────────
    dxy_dir = get_dxy_direction(trader)
    allowed, dxy_reason = is_trade_allowed(cfg.PAIR, sig["signal"], dxy_dir)
    if not allowed:
        log.info(f"[USD/JPY] DXY filter blocked: {dxy_reason}")
        tg.alert_error(f"DXY filter blocked trade: {dxy_reason}")
        log.info("═══ Cycle complete (DXY filter) ═══")
        return
    log.info(f"[USD/JPY] DXY OK: {dxy_reason}")


    # ── US Session extra filters (22:35 SGT = 14:35 UTC only) ───────────────
    # Candle structure, breakout retest, ATR expansion
    # These apply ONLY at the NY/London overlap session for highest conviction
    is_us_session = (now.hour == 14 and 30 <= now.minute <= 45)
    if is_us_session:
        df_last = df.iloc[-1]
        o_  = float(df_last["Open"])
        h_  = float(df_last["High"])
        l_  = float(df_last["Low"])
        c_  = float(df_last["Close"])
        atr_val = float(sig.get("atr") or 0)
        pip = cfg.PIP_SIZE

        # ① Candle structure — body must be strong and close in right zone
        body     = abs(c_ - o_)
        rng      = h_ - l_
        body_pct = body / rng if rng > 0 else 0
        close_pct = (c_ - l_) / rng if rng > 0 else 0.5
        cs_fail = None
        if sig["signal"] == "LONG":
            if c_ <= o_:
                cs_fail = "red candle — no upward close confirmation"
            elif body_pct < 0.40:
                cs_fail = f"weak candle body ({body_pct:.0%} < 40%)"
            elif close_pct < 0.60:
                cs_fail = f"close in lower half ({close_pct:.0%}) — no bullish strength"
        else:
            if c_ >= o_:
                cs_fail = "green candle — no downward close confirmation"
            elif body_pct < 0.40:
                cs_fail = f"weak candle body ({body_pct:.0%} < 40%)"
            elif close_pct > 0.40:
                cs_fail = f"close in upper half ({close_pct:.0%}) — no bearish strength"
        if cs_fail:
            log.info(f"[US session] Candle structure fail: {cs_fail}")
            us_msg = f"US session filter: candle structure — {cs_fail}"
            tg.alert_error(us_msg)
            log.info("Cycle complete (US session - candle structure)")
            return

        # ② Breakout retest — entry must be within 25 pips of EMA9
        ema9_val   = float(sig.get("ema_fast", sig["entry"]))
        dist_pips  = abs(sig["entry"] - ema9_val) / pip
        MAX_DIST   = 25
        if dist_pips > MAX_DIST:
            log.info(f"[US session] Retest fail: entry {dist_pips:.1f}pip from EMA9 (max {MAX_DIST})")
            us_msg = f"US session filter: chasing signal — {dist_pips:.0f}pip from EMA9 (max {MAX_DIST})"
            tg.alert_error(us_msg)
            log.info("Cycle complete (US session - retest)")
            return

        # ③ ATR expansion — market must have enough range but not too wild
        atr_pips   = atr_val / pip
        tp_pips    = cfg.TP_PIPS
        MIN_ATR    = tp_pips * 1.5   # at least 1.5× TP in daily range
        MAX_ATR    = 150
        if atr_pips < MIN_ATR:
            log.info(f"[US session] ATR fail: {atr_pips:.0f}pip < min {MIN_ATR:.0f}pip")
            us_msg = f"US session filter: ATR too low ({atr_pips:.0f}pip < {MIN_ATR:.0f}pip)"
            tg.alert_error(us_msg)
            log.info("Cycle complete (US session - ATR too low)")
            return
        if atr_pips > MAX_ATR:
            log.info(f"[US session] ATR fail: {atr_pips:.0f}pip > max {MAX_ATR}pip")
            us_msg = f"US session filter: ATR too high ({atr_pips:.0f}pip > {MAX_ATR}pip, too volatile)"
            tg.alert_error(us_msg)
            log.info("Cycle complete (US session - ATR too high)")
            return

        log.info(f"[US session] All 3 extra filters passed — candle ✅  retest {dist_pips:.0f}pip ✅  ATR {atr_pips:.0f}pip ✅")

    # ── Place order ───────────────────────────────────────────────────────────
    log.info(f"Signal: {sig['signal']} @ {sig['entry']}  score={score_val}")
    tg.alert_signal(sig, candle_date, balance_sgd=balance_sgd)

    # Paper mode: log the signal but do NOT send a real order.
    # Balance is still fetched from the real OANDA demo account above.
    if cfg.BOT_MODE == "paper":
        log.info(f"[PAPER] Signal only — no order placed: {sig['signal']} @ {sig['entry']} TP={sig['tp']} SL={sig['sl']}")
        log.info("═══ Cycle complete (paper — signal only) ═══")
        return

    # demo mode and live mode both proceed to place orders below

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
        log.info(f"Order filled: {fill.get('trade_id')} @ {fill.get('fill_price')}")
        tg.alert_order_filled(fill, balance_sgd=bal_after)
    else:
        log.error(f"Order failed: {fill}")
        tg.alert_error(f"Order failed: {fill.get('status')}")

    log.info("═══ Cycle complete ═══")

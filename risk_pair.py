"""
risk_pair.py — Per-pair risk gate and P&L calculator
=====================================================
Same logic as risk.py but accepts an explicit cfg object so EUR/USD and
GBP/USD have their own TP/SL/pip_size values.

USD/JPY still uses the original risk.py — untouched.
"""

import journal_pair as jp


def calc_pnl_sgd(result: str, cfg,
                 tp_pips: int = None, sl_pips: int = None,
                 units: int = None) -> float:
    tp_pips = tp_pips or cfg.TP_PIPS
    sl_pips = sl_pips or cfg.SL_PIPS
    lots    = (units or cfg.UNITS) / 10_000
    # For EUR/USD and GBP/USD, 1 pip = $10 per standard lot (100k units).
    # At 50k units (5 mini lots): 1 pip = USD 5.00 → SGD 5 × USD_SGD.
    # The formula 0.91 × USD_SGD × lots gives a slight approximation (~5% off
    # vs exact spot conversion) but matches what the rest of the codebase uses.
    sgd_pip = 0.91 * cfg.USD_SGD
    if result == "WIN":
        return  round(tp_pips * lots * sgd_pip, 2)
    return     -round(sl_pips * lots * sgd_pip, 2)


def check_risk_limits(cfg) -> tuple:
    """Return (True, 'OK') or (False, reason)."""
    stats = jp.weekly_stats(cfg)

    if stats["total"] >= cfg.MAX_TRADES_WK:
        return False, f"Max trades/week reached ({cfg.MAX_TRADES_WK})"

    if stats["net_sgd"] <= -cfg.MAX_LOSS_WEEK:
        return False, f"Weekly loss limit hit (SGD {stats['net_sgd']:.0f})"

    if stats["loss_streak"] >= cfg.PAUSE_STREAK:
        return False, f"Loss streak = {stats['loss_streak']} — pausing"

    return True, "OK"


def print_risk_summary(cfg):
    tp_sgd = calc_pnl_sgd("WIN",  cfg)
    sl_sgd = calc_pnl_sgd("LOSS", cfg)
    print(f"""
  Risk Summary — {cfg.PAIR_LABEL} ({cfg.UNITS:,} units)
  TP {cfg.TP_PIPS} pips = SGD {tp_sgd:+.2f}
  SL {cfg.SL_PIPS} pips = SGD {sl_sgd:.2f}
  RR 1:{cfg.TP_PIPS / cfg.SL_PIPS:.1f}
  pip_size = {cfg.PIP_SIZE}
  Weekly scenarios (5 trades):
    4W 1L  SGD {4*tp_sgd + 1*sl_sgd:+.0f}
    3W 2L  SGD {3*tp_sgd + 2*sl_sgd:+.0f}  <- 75-80% WR target
    2W 3L  SGD {2*tp_sgd + 3*sl_sgd:+.0f}
""")

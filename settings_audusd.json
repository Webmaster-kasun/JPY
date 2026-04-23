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
    pip_size = cfg.PIP_SIZE
    # JPY pairs (pip_size=0.01): 1 pip ≈ /bin/sh.91 per 10k units (JPY correction factor)
    # USD-quoted pairs (pip_size=0.0001): 1 pip = units × pip_size × USD_SGD exactly
    if pip_size >= 0.01:
        sgd_pip = 0.91 * cfg.USD_SGD
    else:
        sgd_pip = (units or cfg.UNITS) * pip_size * cfg.USD_SGD / lots
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

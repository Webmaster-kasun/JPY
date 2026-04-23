"""
risk.py — Position sizing and risk gate checks
==============================================
"""

import settings as cfg
import journal


def calc_pnl_sgd(result: str, tp_pips: int = None, sl_pips: int = None,
                 units: int = None) -> float:
    tp_pips = tp_pips or cfg.TP_PIPS
    sl_pips = sl_pips or cfg.SL_PIPS
    lots    = (units or cfg.UNITS) / 10_000
    sgd_pip = 0.91 * cfg.USD_SGD
    if result == "WIN":
        return  round(tp_pips * lots * sgd_pip, 2)
    return     -round(sl_pips * lots * sgd_pip, 2)


def check_risk_limits() -> tuple:
    """
    Return (True, "OK") if safe to trade,
    or (False, reason) if limits are breached.
    """
    stats = journal.weekly_stats()

    # Too many losses this week
    if stats["total"] >= cfg.MAX_TRADES_WK:
        return False, f"Max trades/week reached ({cfg.MAX_TRADES_WK})"

    # Weekly loss exceeded
    if stats["net_sgd"] <= -cfg.MAX_LOSS_WEEK:
        return False, f"Weekly loss limit hit (SGD {stats['net_sgd']:.0f})"

    # Loss streak
    if stats["loss_streak"] >= cfg.PAUSE_STREAK:
        return False, f"Loss streak = {stats['loss_streak']} — pausing"

    return True, "OK"


def print_risk_summary():
    tp_sgd  = calc_pnl_sgd("WIN")
    sl_sgd  = calc_pnl_sgd("LOSS")
    print(f"""
  Risk Summary — USD/JPY ({cfg.UNITS:,} units)
  TP {cfg.TP_PIPS} pips = SGD {tp_sgd:+.2f}
  SL {cfg.SL_PIPS} pips = SGD {sl_sgd:.2f}
  RR 1:{cfg.TP_PIPS/cfg.SL_PIPS:.1f}
  Weekly scenarios (5 trades):
    4W 1L  SGD {4*tp_sgd + 1*sl_sgd:+.0f}
    3W 2L  SGD {3*tp_sgd + 2*sl_sgd:+.0f}  <- 80% WR target
    2W 3L  SGD {2*tp_sgd + 3*sl_sgd:+.0f}
""")


if __name__ == "__main__":
    print_risk_summary()

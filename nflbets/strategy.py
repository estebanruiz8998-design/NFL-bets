"""Bet selection: turn model predictions + market lines into ranked candidate
bets for a game, and pick the single best one.

Probabilities come from logistic calibrations fit on training seasons (see
tune.py), not from a distributional assumption. Spread and total bets are
priced at standard -110: the historical odds columns in the dataset contain
alt-line artifacts in some seasons, and -110 is the conservative, realistic
assumption. Moneyline bets use the dataset's actual moneyline prices.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import market
from .calibration import sigmoid
from .config import Config


@dataclass
class Candidate:
    bet_type: str      # "spread" | "total" | "moneyline"
    side: str          # team abbreviation, or "over"/"under"
    line: float | None # line from the bettor's perspective (negative = laying points)
    odds: float        # American odds used for EV (and settlement)
    p_win: float
    p_push: float
    ev: float          # expected value per unit staked
    stake: float       # fractional-Kelly stake (fraction of bankroll)

    def label(self) -> str:
        if self.bet_type == "spread":
            return f"{self.side} {self.line:+g}"
        if self.bet_type == "total":
            return f"{self.side.capitalize()} {self.line:g}"
        return f"{self.side} ML {self.odds:+.0f}"


def _isnum(v) -> bool:
    try:
        return not math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def _mk(cfg: Config, bet_type: str, side: str, line: float | None,
        odds: float, p_decided: float, p_push: float) -> Candidate:
    """p_decided is P(win | bet is decided); pushes carved out separately."""
    p_win = p_decided * (1.0 - p_push)
    ev = market.bet_ev(p_win, p_push, odds)
    stake = min(cfg.max_stake, cfg.kelly_fraction * market.kelly_stake(p_win, p_push, odds))
    return Candidate(bet_type, side, line, odds, p_win, p_push, ev, stake)


def candidates(cfg: Config, row, pred_margin: float, pred_total: float) -> list[Candidate]:
    """All candidate bets for one game row (nflverse conventions).

    ``pred_margin``/``pred_total`` are the RAW model outputs; calibration maps
    their disagreement with the market line into win probabilities.
    """
    out: list[Candidate] = []
    home, away = row.home_team, row.away_team

    spread_ok = _isnum(row.spread_line)
    edge_s = (pred_margin - float(row.spread_line)) if spread_ok else 0.0

    if spread_ok:
        spread = float(row.spread_line)
        p_home = sigmoid(cfg.cal_spread_b * edge_s)
        p_push = cfg.push_spread if float(spread).is_integer() else 0.0
        out.append(_mk(cfg, "spread", home, -spread, market.DEFAULT_PRICE, p_home, p_push))
        out.append(_mk(cfg, "spread", away, spread, market.DEFAULT_PRICE, 1.0 - p_home, p_push))

    if _isnum(row.total_line):
        total = float(row.total_line)
        edge_t = pred_total - total
        p_over = sigmoid(cfg.cal_total_b * edge_t)
        p_push = cfg.push_total if float(total).is_integer() else 0.0
        out.append(_mk(cfg, "total", "over", total, market.DEFAULT_PRICE, p_over, p_push))
        out.append(_mk(cfg, "total", "under", total, market.DEFAULT_PRICE, 1.0 - p_over, p_push))

    hml = getattr(row, "home_moneyline", None)
    aml = getattr(row, "away_moneyline", None)
    if cfg.allow_moneyline and spread_ok and _isnum(hml) and _isnum(aml):
        hml, aml = float(hml), float(aml)
        p_home_win = sigmoid(cfg.cal_ml_a + cfg.cal_ml_b0 * float(row.spread_line)
                             + cfg.cal_ml_b1 * edge_s)
        if abs(hml) <= cfg.max_ml_odds:
            out.append(_mk(cfg, "moneyline", home, None, hml, p_home_win, cfg.p_tie))
        if abs(aml) <= cfg.max_ml_odds:
            out.append(_mk(cfg, "moneyline", away, None, aml, 1.0 - p_home_win, cfg.p_tie))
    return out


def threshold(cfg: Config, bet_type: str) -> float:
    return {"spread": cfg.min_ev_spread,
            "total": cfg.min_ev_total,
            "moneyline": cfg.min_ev_moneyline}[bet_type]


def best_bet(cfg: Config, cands: list[Candidate]) -> tuple[Candidate | None, str]:
    """Highest-EV candidate and its tier: STRONG (clears threshold),
    LEAN (positive EV, below threshold), or PASS (no positive-EV bet)."""
    if not cands:
        return None, "PASS"
    best = max(cands, key=lambda c: c.ev)
    if best.ev >= threshold(cfg, best.bet_type):
        return best, "STRONG"
    if best.ev > 0:
        return best, "LEAN"
    return best, "PASS"


def anchored(cfg: Config, row, pred_margin: float, pred_total: float) -> tuple[float, float]:
    """Market-anchored margin/total predictions for display."""
    m, t = pred_margin, pred_total
    if _isnum(row.spread_line):
        s = float(row.spread_line)
        m = s + cfg.beta_spread * (pred_margin - s)
    if _isnum(row.total_line):
        tl = float(row.total_line)
        t = tl + cfg.beta_total * (pred_total - tl)
    return m, t

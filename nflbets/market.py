"""Odds math: American odds conversions, de-vigging, and cover probabilities."""

from __future__ import annotations

import math

DEFAULT_PRICE = -110.0  # standard spread/total juice when the dataset lacks prices


def american_to_prob(odds: float) -> float:
    """Implied probability (vig included) of American odds."""
    if odds < 0:
        return -odds / (-odds + 100.0)
    return 100.0 / (odds + 100.0)


def american_payout(odds: float) -> float:
    """Net profit per unit staked if the bet wins."""
    if odds < 0:
        return 100.0 / -odds
    return odds / 100.0


def devig_pair(prob_a: float, prob_b: float) -> tuple[float, float]:
    """Remove vig from a two-way market by proportional normalization."""
    s = prob_a + prob_b
    if s <= 0:
        return 0.5, 0.5
    return prob_a / s, prob_b / s


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def prob_over_line(pred: float, line: float, sigma: float) -> tuple[float, float]:
    """P(actual > line) and P(push) when actual ~ Normal(pred, sigma).

    Works for both margins vs spreads and totals vs total lines. Push
    probability is approximated as the mass within +-0.5 of an integer line.
    """
    p_over = 1.0 - _norm_cdf((line - pred) / sigma)
    p_push = 0.0
    if float(line).is_integer():
        lo = _norm_cdf((line - 0.5 - pred) / sigma)
        hi = _norm_cdf((line + 0.5 - pred) / sigma)
        p_push = max(0.0, hi - lo)
        # Split the push mass out of both sides proportionally.
        p_over = max(0.0, p_over - p_push / 2.0)
    return p_over, p_push


def bet_ev(p_win: float, p_push: float, odds: float) -> float:
    """Expected value per unit staked. Pushes return the stake."""
    p_lose = max(0.0, 1.0 - p_win - p_push)
    return p_win * american_payout(odds) - p_lose


def kelly_stake(p_win: float, p_push: float, odds: float) -> float:
    """Full-Kelly fraction for a bet with pushes treated as no-bets."""
    denom = p_win + max(0.0, 1.0 - p_win - p_push)
    if denom <= 0:
        return 0.0
    p = p_win / denom  # win prob conditional on no push
    b = american_payout(odds)
    f = (b * p - (1.0 - p)) / b
    return max(0.0, f)

import math

import numpy as np
import pandas as pd
import pytest

from nflbets import market, strategy
from nflbets.calibration import fit_logistic, sigmoid
from nflbets.config import Config
from nflbets.elo import EloModel
from nflbets.totals import TotalsModel


def test_american_odds_roundtrip():
    assert market.american_to_prob(-110) == pytest.approx(110 / 210)
    assert market.american_to_prob(+150) == pytest.approx(0.4)
    assert market.american_payout(-110) == pytest.approx(100 / 110)
    assert market.american_payout(+150) == pytest.approx(1.5)


def test_devig():
    a, b = market.devig_pair(0.55, 0.55)
    assert a == pytest.approx(0.5)
    assert a + b == pytest.approx(1.0)


def test_bet_ev_breakeven():
    # At -110, EV is zero exactly at p = 11/21.
    p = 11 / 21
    assert market.bet_ev(p, 0.0, -110) == pytest.approx(0.0, abs=1e-12)
    assert market.bet_ev(p + 0.01, 0.0, -110) > 0
    assert market.bet_ev(p - 0.01, 0.0, -110) < 0


def test_kelly_positive_only_with_edge():
    assert market.kelly_stake(0.5, 0.0, -110) == 0.0
    assert market.kelly_stake(0.6, 0.0, -110) > 0.0


def test_elo_update_symmetry_and_hfa():
    cfg = Config()
    elo = EloModel(cfg)
    _, margin, p = elo.pregame(2020, "A", "B")
    assert margin == pytest.approx(cfg.elo_hfa / cfg.elo_points_per)
    assert p > 0.5  # home edge
    before = sum(elo.ratings.values())
    elo.update(2020, "A", "B", 7)
    assert sum(elo.ratings.values()) == pytest.approx(before)  # zero-sum
    assert elo.ratings["A"] > elo.ratings["B"]


def test_elo_qb_penalty_direction():
    cfg = Config(elo_qb_penalty=60)
    elo = EloModel(cfg)
    _, m_base, _ = elo.pregame(2020, "A", "B")
    _, m_qb, _ = elo.pregame(2020, "A", "B", home_qb_change=True)
    assert m_qb < m_base


def test_elo_preseason_regression():
    cfg = Config(elo_preseason_regress=0.5)
    elo = EloModel(cfg)
    elo.ratings["A"] = 1700.0
    elo.last_season["A"] = 2020
    assert elo._get("A", 2021) == pytest.approx(1600.0)


def test_totals_tracks_scoring():
    cfg = Config()
    tot = TotalsModel(cfg)
    base = tot.pregame(2020, "A", "B")
    for _ in range(10):
        tot.update(2020, "A", "B", 35, 30)
    assert tot.pregame(2020, "A", "B") > base


def test_logistic_recovers_slope():
    rng = np.random.default_rng(7)
    x = rng.normal(0, 5, 20000)[:, None]
    y = (rng.random(20000) < sigmoid(0.15 * x[:, 0])).astype(float)
    w = fit_logistic(x, y)
    assert w[0] == pytest.approx(0.15, abs=0.02)


def _row(**kw):
    d = dict(home_team="H", away_team="A", spread_line=3.0, total_line=44.0,
             home_moneyline=-160.0, away_moneyline=140.0)
    d.update(kw)
    return pd.Series(d)


def test_candidates_and_tiers():
    cfg = Config(allow_moneyline=False)
    row = _row()
    cands = strategy.candidates(cfg, row, pred_margin=3.0, pred_total=44.0)
    # spread home/away + total over/under, no moneylines
    assert len(cands) == 4
    assert all(c.bet_type != "moneyline" for c in cands)
    # Zero edge => every candidate is -EV at -110 => PASS
    best, tier = strategy.best_bet(cfg, cands)
    assert tier == "PASS"
    # A huge model/market gap should clear the conservative STRONG threshold.
    cands = strategy.candidates(cfg, row, pred_margin=18.0, pred_total=44.0)
    best, tier = strategy.best_bet(cfg, cands)
    assert best.bet_type == "spread" and best.side == "H"
    assert tier == "STRONG"


def test_spread_settlement_convention():
    from nflbets.backtest import settle
    cfg = Config()
    row = _row(result=7.0, total=45.0)
    cands = strategy.candidates(cfg, row, pred_margin=10.0, pred_total=44.0)
    home_spread = next(c for c in cands if c.bet_type == "spread" and c.side == "H")
    outcome, profit = settle(home_spread, row)
    assert outcome == "win"          # home -3 with a 7-point win covers
    away_spread = next(c for c in cands if c.bet_type == "spread" and c.side == "A")
    outcome, profit = settle(away_spread, row)
    assert outcome == "loss"

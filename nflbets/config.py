"""Model and strategy configuration, serializable to JSON so the tuner can save
a champion config that the weekly card loads at season time."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "champion.json"


@dataclass
class Config:
    # --- Elo rating model ---
    elo_k: float = 20.0                 # update speed
    elo_hfa: float = 48.0               # home-field advantage, Elo points
    elo_preseason_regress: float = 0.33 # fraction regressed to mean each offseason
    elo_rest_bonus: float = 25.0        # Elo bonus when a team is off a bye (rest >= 9 days)
    elo_playoff_mult: float = 1.2       # rating-diff multiplier in playoff games
    elo_qb_penalty: float = 40.0        # Elo penalty when starting a different QB than last game
    elo_points_per: float = 25.0        # Elo points per point of scoreboard margin
    elo_initial: float = 1500.0
    elo_expansion: float = 1300.0       # initial rating for expansion teams (HOU 2002)

    # --- Totals model ---
    tot_halflife: float = 8.0           # games; EWMA halflife for team scoring rates
    tot_season_regress: float = 0.30    # offseason regression of scoring rates to league mean

    # --- Market anchoring (for displayed predictions) ---
    # Displayed prediction = market line + beta * (model - market line), where
    # beta is the fraction of model/market disagreement that is real signal.
    beta_spread: float = 0.07
    beta_total: float = 0.08

    # --- Distributions (informational; betting probs use the calibrations) ---
    sigma_margin: float = 13.4
    sigma_total: float = 13.4

    # --- Calibrated betting probabilities (fit on train seasons) ---
    # P(home covers)  = sigmoid(cal_spread_b * spread_edge)
    # P(over)         = sigmoid(cal_total_b * total_edge)
    # P(home wins)    = sigmoid(cal_ml_a + cal_ml_b0*spread_line + cal_ml_b1*spread_edge)
    # where spread_edge = raw model margin - spread_line (points).
    cal_spread_b: float = 0.025
    cal_total_b: float = 0.020
    cal_ml_a: float = 0.0
    cal_ml_b0: float = 0.105
    cal_ml_b1: float = 0.010

    # Push probabilities on integer lines (empirical constants) and tie rate.
    push_spread: float = 0.025
    push_total: float = 0.015
    p_tie: float = 0.004

    # --- Bet selection ---
    min_ev_spread: float = 0.02         # minimum EV (per unit staked) to flag a spread bet
    min_ev_total: float = 0.03
    min_ev_moneyline: float = 0.05
    max_ml_odds: float = 400.0          # don't recommend moneyline dogs longer than this
    # Moneylines are excluded from the betting engine by default: the model
    # contributes essentially no game-specific signal to them (see tune.py),
    # so ML "edges" are market-structure bets we can't defend prospectively.
    allow_moneyline: bool = False
    kelly_fraction: float = 0.25        # fraction of full Kelly for stake sizing
    max_stake: float = 0.02             # cap stake at 2% of bankroll

    def save(self, path: Path | str = CONFIG_PATH) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dataclasses.asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, path: Path | str = CONFIG_PATH) -> "Config":
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

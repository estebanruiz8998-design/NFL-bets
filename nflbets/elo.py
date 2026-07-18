"""FiveThirtyEight-style Elo rating model for NFL teams.

Sequential by design: ratings before game i depend only on games < i, which is
what makes the walk-forward backtest leak-free.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import Config


@dataclass
class EloModel:
    cfg: Config
    ratings: dict[str, float] = field(default_factory=dict)
    last_season: dict[str, int] = field(default_factory=dict)

    def _get(self, team: str, season: int) -> float:
        if team not in self.ratings:
            # HOU 2002 is the only expansion team in the 1999+ window.
            self.ratings[team] = (
                self.cfg.elo_expansion if season >= 2002 else self.cfg.elo_initial
            )
            self.last_season[team] = season
        elif self.last_season[team] != season:
            # Offseason: regress toward the mean once per team per season.
            r = self.ratings[team]
            self.ratings[team] = r + self.cfg.elo_preseason_regress * (
                self.cfg.elo_initial - r
            )
            self.last_season[team] = season
        return self.ratings[team]

    def pregame(
        self,
        season: int,
        home: str,
        away: str,
        neutral: bool = False,
        home_rest: float | None = None,
        away_rest: float | None = None,
        playoff: bool = False,
        home_qb_change: bool = False,
        away_qb_change: bool = False,
    ) -> tuple[float, float, float]:
        """Return (elo_diff, predicted home margin, home win prob) before a game."""
        rh = self._get(home, season)
        ra = self._get(away, season)
        diff = rh - ra
        if not neutral:
            diff += self.cfg.elo_hfa
        if home_rest is not None and home_rest >= 9:
            diff += self.cfg.elo_rest_bonus
        if away_rest is not None and away_rest >= 9:
            diff -= self.cfg.elo_rest_bonus
        if home_qb_change:
            diff -= self.cfg.elo_qb_penalty
        if away_qb_change:
            diff += self.cfg.elo_qb_penalty
        if playoff:
            diff *= self.cfg.elo_playoff_mult
        margin = diff / self.cfg.elo_points_per
        win_prob = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
        return diff, margin, win_prob

    def update(
        self,
        season: int,
        home: str,
        away: str,
        result: float,
        neutral: bool = False,
        home_rest: float | None = None,
        away_rest: float | None = None,
        playoff: bool = False,
        home_qb_change: bool = False,
        away_qb_change: bool = False,
    ) -> None:
        """Update ratings after a game. `result` is home margin (home - away)."""
        diff, _, win_prob = self.pregame(
            season, home, away, neutral, home_rest, away_rest, playoff,
            home_qb_change, away_qb_change,
        )
        outcome = 0.5 if result == 0 else (1.0 if result > 0 else 0.0)
        # Margin-of-victory multiplier (538 formula): big wins move ratings more,
        # damped when the favorite wins big (autocorrelation guard). Ties use
        # log(max(|margin|,1)+1) with no damping so the favorite is pulled
        # toward parity rather than the update silently zeroing out.
        winner_diff = diff if result > 0 else (-diff if result < 0 else 0.0)
        mov = math.log(max(abs(result), 1.0) + 1.0) * (2.2 / (winner_diff * 0.001 + 2.2))
        delta = self.cfg.elo_k * mov * (outcome - win_prob)
        self.ratings[home] += delta
        self.ratings[away] -= delta

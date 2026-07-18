"""Totals model: exponentially-weighted scoring rates per team.

Predicted total = expected home points + expected away points, where each
team's expected points blend its EWMA offense with the opponent's EWMA defense,
centered on a league-average EWMA that tracks scoring-environment drift.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import Config


@dataclass
class TotalsModel:
    cfg: Config
    off: dict[str, float] = field(default_factory=dict)   # EWMA points scored
    dfn: dict[str, float] = field(default_factory=dict)   # EWMA points allowed
    last_season: dict[str, int] = field(default_factory=dict)
    league: float = 21.5                                   # EWMA league points/team/game

    @property
    def _alpha(self) -> float:
        return 1.0 - math.exp(math.log(0.5) / self.cfg.tot_halflife)

    def _get(self, team: str, season: int) -> tuple[float, float]:
        if team not in self.off:
            self.off[team] = self.league
            self.dfn[team] = self.league
            self.last_season[team] = season
        elif self.last_season[team] != season:
            r = self.cfg.tot_season_regress
            self.off[team] += r * (self.league - self.off[team])
            self.dfn[team] += r * (self.league - self.dfn[team])
            self.last_season[team] = season
        return self.off[team], self.dfn[team]

    def pregame(self, season: int, home: str, away: str) -> float:
        ho, hd = self._get(home, season)
        ao, ad = self._get(away, season)
        # Team offense vs opponent defense, expressed as offsets from league avg.
        exp_home = self.league + (ho - self.league) + (ad - self.league)
        exp_away = self.league + (ao - self.league) + (hd - self.league)
        return exp_home + exp_away

    def update(
        self, season: int, home: str, away: str, home_score: float, away_score: float
    ) -> None:
        self._get(home, season)
        self._get(away, season)
        a = self._alpha
        self.off[home] += a * (home_score - self.off[home])
        self.dfn[home] += a * (away_score - self.dfn[home])
        self.off[away] += a * (away_score - self.off[away])
        self.dfn[away] += a * (home_score - self.dfn[away])
        game_avg = (home_score + away_score) / 2.0
        # League environment moves slowly: ~1/16 the team-level speed.
        self.league += (a / 16.0) * (game_avg - self.league)

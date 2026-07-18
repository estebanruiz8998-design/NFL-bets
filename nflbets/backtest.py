"""Walk-forward backtest: replay history in order, predict each game with only
prior information, place the strategy's bets against the recorded closing
lines, then reveal the result and update the models.

Run:  python -m nflbets.backtest --bet-start 2008 --bet-end 2025
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import data, strategy
from .config import Config
from .elo import EloModel
from .totals import TotalsModel


@dataclass
class BetRecord:
    season: int
    week: int
    game_id: str
    bet_type: str
    label: str
    odds: float
    ev: float
    stake: float
    outcome: str   # "win" | "loss" | "push"
    profit: float  # per 1 unit flat stake


@dataclass
class BacktestResult:
    predictions: pd.DataFrame
    bets: list[BetRecord] = field(default_factory=list)
    candidates: pd.DataFrame | None = None
    bet_start: int | None = None
    bet_end: int | None = None

    def bets_df(self) -> pd.DataFrame:
        return pd.DataFrame([vars(b) for b in self.bets])

    def summary(self) -> dict:
        # Model-quality metrics are scoped to the bet window so "train" and
        # "validation" summaries report on their own seasons, not 1999-2025.
        p = self.predictions
        if self.bet_start is not None:
            p = p[p.season.between(self.bet_start, self.bet_end)]
        graded = p[p.result.notna()]
        out = {
            "games": len(graded),
            "model_margin_mae": float((graded.result - graded.pred_margin).abs().mean()),
            "market_margin_mae": float((graded.result - graded.spread_line).abs().mean()),
            "model_total_mae": float((graded.total - graded.pred_total).abs().mean()),
            "market_total_mae": float((graded.total - graded.total_line).abs().mean()),
            "su_accuracy": float(
                ((graded.pred_margin > 0) == (graded.result > 0)).mean()
            ),
            "brier": float(
                ((graded.home_win_prob - (graded.result > 0)) ** 2).mean()
            ),
        }
        b = self.bets_df()
        if len(b):
            wins = (b.outcome == "win").sum()
            losses = (b.outcome == "loss").sum()
            decided = wins + losses
            flat_profit = b.profit.sum()
            out.update({
                "bets": len(b),
                "wins": int(wins),
                "losses": int(losses),
                "pushes": int((b.outcome == "push").sum()),
                "hit_rate": float(wins / decided) if decided else float("nan"),
                "flat_roi": float(flat_profit / len(b)) if len(b) else float("nan"),
                "flat_profit_units": float(flat_profit),
            })
            # Kelly bankroll path (compounding, stake = fraction of bankroll)
            bank, peak, max_dd = 1.0, 1.0, 0.0
            for r in self.bets:
                bank += bank * r.stake * r.profit
                peak = max(peak, bank)
                max_dd = max(max_dd, 1.0 - bank / peak)
            out["kelly_bankroll"] = float(bank)
            out["kelly_max_drawdown"] = float(max_dd)
        else:
            out["bets"] = 0
        return out

    def per_season(self) -> pd.DataFrame:
        b = self.bets_df()
        if not len(b):
            return pd.DataFrame()
        g = b.groupby("season").agg(
            bets=("profit", "size"),
            wins=("outcome", lambda s: (s == "win").sum()),
            losses=("outcome", lambda s: (s == "loss").sum()),
            pushes=("outcome", lambda s: (s == "push").sum()),
            flat_profit=("profit", "sum"),
        )
        g["hit_rate"] = g.wins / (g.wins + g.losses)
        g["roi"] = g.flat_profit / g.bets
        return g


def settle(cand: strategy.Candidate, row) -> tuple[str, float]:
    """Grade a bet against the actual result. Returns (outcome, flat profit)."""
    result, total = row.result, row.total
    if cand.bet_type == "spread":
        margin = result if cand.side == row.home_team else -result
        need = -cand.line  # line is from bettor perspective
        if margin > need:
            o = "win"
        elif margin == need:
            o = "push"
        else:
            o = "loss"
    elif cand.bet_type == "total":
        if total == cand.line:
            o = "push"
        elif (total > cand.line) == (cand.side == "over"):
            o = "win"
        else:
            o = "loss"
    else:  # moneyline
        winner_margin = result if cand.side == row.home_team else -result
        o = "win" if winner_margin > 0 else ("push" if winner_margin == 0 else "loss")
    from . import market
    profit = market.american_payout(cand.odds) if o == "win" else (0.0 if o == "push" else -1.0)
    return o, profit


def run(
    cfg: Config,
    games: pd.DataFrame | None = None,
    bet_start: int = 2008,
    bet_end: int = 2025,
    bet_playoffs: bool = False,
    collect_candidates: bool = False,
) -> BacktestResult:
    if games is None:
        games = data.load()
    games = data.completed(games)

    elo = EloModel(cfg)
    tot = TotalsModel(cfg)
    preds = []
    result = BacktestResult(predictions=pd.DataFrame(),
                            bet_start=bet_start, bet_end=bet_end)
    all_cands = []

    for row in games.itertuples(index=False):
        _, pred_margin, p_home = elo.pregame(
            row.season, row.home_team, row.away_team, row.neutral,
            row.home_rest, row.away_rest, row.playoff,
            row.home_qb_change, row.away_qb_change,
        )
        pred_total = tot.pregame(row.season, row.home_team, row.away_team)

        preds.append({
            "game_id": row.game_id, "season": row.season, "week": row.week,
            "home_team": row.home_team, "away_team": row.away_team,
            "pred_margin": pred_margin, "home_win_prob": p_home,
            "pred_total": pred_total,
            "spread_line": row.spread_line, "total_line": row.total_line,
            "result": row.result, "total": row.total,
        })

        in_window = bet_start <= row.season <= bet_end and (bet_playoffs or not row.playoff)
        if in_window and not (isinstance(row.spread_line, float) and np.isnan(row.spread_line)):
            cands = strategy.candidates(cfg, row, pred_margin, pred_total)
            if collect_candidates:
                for c in cands:
                    o, pr = settle(c, row)
                    all_cands.append({
                        "season": row.season, "game_id": row.game_id,
                        "bet_type": c.bet_type, "label": c.label(), "odds": c.odds,
                        "p_win": c.p_win, "ev": c.ev, "outcome": o, "profit": pr,
                    })
            best, tier = strategy.best_bet(cfg, cands)
            if best is not None and tier == "STRONG":
                outcome, profit = settle(best, row)
                result.bets.append(BetRecord(
                    row.season, row.week, row.game_id, best.bet_type, best.label(),
                    best.odds, best.ev, best.stake, outcome, profit,
                ))

        elo.update(row.season, row.home_team, row.away_team, row.result,
                   row.neutral, row.home_rest, row.away_rest, row.playoff,
                   row.home_qb_change, row.away_qb_change)
        tot.update(row.season, row.home_team, row.away_team,
                   row.home_score, row.away_score)

    result.predictions = pd.DataFrame(preds)
    if collect_candidates:
        result.candidates = pd.DataFrame(all_cands)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Walk-forward NFL betting backtest")
    ap.add_argument("--bet-start", type=int, default=2008)
    ap.add_argument("--bet-end", type=int, default=2025)
    ap.add_argument("--config", default=None, help="path to a config JSON")
    args = ap.parse_args()

    cfg = Config.load(args.config) if args.config else Config.load()
    res = run(cfg, bet_start=args.bet_start, bet_end=args.bet_end)
    s = res.summary()
    print("== Model quality (all predicted games) ==")
    for k in ("games", "model_margin_mae", "market_margin_mae",
              "model_total_mae", "market_total_mae", "su_accuracy", "brier"):
        print(f"  {k:>20}: {s[k]:.4f}" if isinstance(s[k], float) else f"  {k:>20}: {s[k]}")
    if s.get("bets"):
        print(f"== Betting ({args.bet_start}-{args.bet_end}, STRONG best-bets only) ==")
        for k in ("bets", "wins", "losses", "pushes", "hit_rate", "flat_roi",
                  "flat_profit_units", "kelly_bankroll", "kelly_max_drawdown"):
            v = s[k]
            print(f"  {k:>20}: {v:.4f}" if isinstance(v, float) else f"  {k:>20}: {v}")
        print("\n== Per season ==")
        print(res.per_season().to_string(float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()

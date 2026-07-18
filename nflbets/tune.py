"""Tuning pipeline with strict train/validation separation.

Protocol:
  warm-up   1999-2007  ratings only, never scored or bet
  train     2008-2019  all hyperparameters fit here
  validate  2020-2025  touched exactly once, with the final champion config

Stages:
  1. Elo hyperparameters      -> minimize margin MAE on train
  2. Totals hyperparameters   -> minimize total MAE on train
  3. Market-anchoring betas   -> OLS of actual-vs-line on model-vs-line (train)
  4. Sigmas                   -> residual std of anchored predictions (train)
  5. EV thresholds            -> maximize train flat profit of best-bet-per-game
  6. Save config/champion.json, then report validation performance once.

Run:  python -m nflbets.tune
"""

from __future__ import annotations

import dataclasses
import itertools

import numpy as np
import pandas as pd

from . import backtest, data
from .config import CONFIG_PATH, Config

TRAIN = (2008, 2019)
VALID = (2020, 2025)


def _margin_mae(games: pd.DataFrame, cfg: Config, lo: int, hi: int) -> float:
    from .elo import EloModel

    elo = EloModel(cfg)
    errs = []
    for row in games.itertuples(index=False):
        _, pred, _ = elo.pregame(
            row.season, row.home_team, row.away_team, row.neutral,
            row.home_rest, row.away_rest, row.playoff,
            row.home_qb_change, row.away_qb_change,
        )
        if lo <= row.season <= hi:
            errs.append(abs(row.result - pred))
        elo.update(row.season, row.home_team, row.away_team, row.result,
                   row.neutral, row.home_rest, row.away_rest, row.playoff,
                   row.home_qb_change, row.away_qb_change)
    return float(np.mean(errs))


def _total_mae(games: pd.DataFrame, cfg: Config, lo: int, hi: int) -> float:
    from .totals import TotalsModel

    tot = TotalsModel(cfg)
    errs = []
    for row in games.itertuples(index=False):
        pred = tot.pregame(row.season, row.home_team, row.away_team)
        if lo <= row.season <= hi:
            errs.append(abs(row.total - pred))
        tot.update(row.season, row.home_team, row.away_team,
                   row.home_score, row.away_score)
    return float(np.mean(errs))


def tune_elo(games: pd.DataFrame, cfg: Config) -> Config:
    grid = itertools.product(
        [12.0, 16.0, 20.0, 24.0],      # elo_k
        [35.0, 48.0, 60.0],            # elo_hfa
        [0.25, 0.33, 0.50],            # elo_preseason_regress
        [0.0, 15.0, 25.0],             # elo_rest_bonus
        [0.0, 30.0, 60.0, 90.0],       # elo_qb_penalty
    )
    best, best_mae = None, np.inf
    for k, hfa, reg, rest, qb in grid:
        c = dataclasses.replace(cfg, elo_k=k, elo_hfa=hfa,
                                elo_preseason_regress=reg, elo_rest_bonus=rest,
                                elo_qb_penalty=qb)
        mae = _margin_mae(games, c, *TRAIN)
        if mae < best_mae:
            best, best_mae = c, mae
    print(f"[elo] best margin MAE {best_mae:.4f} @ k={best.elo_k} hfa={best.elo_hfa} "
          f"regress={best.elo_preseason_regress} rest={best.elo_rest_bonus} "
          f"qb_penalty={best.elo_qb_penalty}")
    return best


def tune_totals(games: pd.DataFrame, cfg: Config) -> Config:
    grid = itertools.product([5.0, 8.0, 12.0, 16.0], [0.2, 0.3, 0.5])
    best, best_mae = None, np.inf
    for hl, reg in grid:
        c = dataclasses.replace(cfg, tot_halflife=hl, tot_season_regress=reg)
        mae = _total_mae(games, c, *TRAIN)
        if mae < best_mae:
            best, best_mae = c, mae
    print(f"[totals] best total MAE {best_mae:.4f} @ halflife={best.tot_halflife} "
          f"regress={best.tot_season_regress}")
    return best


def fit_calibrations(preds: pd.DataFrame, cfg: Config) -> Config:
    """Fit the display anchoring (OLS) and the betting probability models
    (logistic regressions) on train-season predictions only."""
    from .calibration import fit_logistic

    t = preds[preds.season.between(*TRAIN)
              & preds.spread_line.notna() & preds.result.notna()].copy()
    t["edge_s"] = t.pred_margin - t.spread_line
    t["edge_t"] = t.pred_total - t.total_line

    # Display anchoring betas (OLS through the origin) + residual sigmas.
    beta_s = float(np.clip((t.edge_s * (t.result - t.spread_line)).sum()
                           / (t.edge_s ** 2).sum(), 0.0, 1.0))
    tt = t[t.total_line.notna() & t.total.notna()]
    beta_t = float(np.clip((tt.edge_t * (tt.total - tt.total_line)).sum()
                           / (tt.edge_t ** 2).sum(), 0.0, 1.0))
    sig_m = float((t.result - (t.spread_line + beta_s * t.edge_s)).std())
    sig_t = float((tt.total - (tt.total_line + beta_t * tt.edge_t)).std())

    # P(home covers) ~ sigmoid(b * edge_s), pushes dropped.
    dec = t[t.result != t.spread_line]
    w = fit_logistic(dec[["edge_s"]].to_numpy(),
                     (dec.result > dec.spread_line).to_numpy())
    cal_spread_b = float(w[0])

    # P(over) ~ sigmoid(b * edge_t), pushes dropped.
    dtt = tt[tt.total != tt.total_line]
    w = fit_logistic(dtt[["edge_t"]].to_numpy(),
                     (dtt.total > dtt.total_line).to_numpy())
    cal_total_b = float(w[0])

    # P(home wins) ~ sigmoid(a + b0*spread + b1*edge_s), ties dropped.
    dml = t[t.result != 0].copy()
    dml["one"] = 1.0
    w = fit_logistic(dml[["one", "spread_line", "edge_s"]].to_numpy(),
                     (dml.result > 0).to_numpy())
    cal_ml_a, cal_ml_b0, cal_ml_b1 = (float(x) for x in w)

    # Empirical push/tie rates on integer lines.
    ints = t[t.spread_line % 1 == 0]
    push_spread = float((ints.result == ints.spread_line).mean()) if len(ints) else 0.025
    intt = tt[tt.total_line % 1 == 0]
    push_total = float((intt.total == intt.total_line).mean()) if len(intt) else 0.015
    p_tie = float((t.result == 0).mean())

    print(f"[calib] beta_s={beta_s:.3f} beta_t={beta_t:.3f} "
          f"sigma_m={sig_m:.2f} sigma_t={sig_t:.2f}")
    print(f"[calib] cover_b={cal_spread_b:.4f} over_b={cal_total_b:.4f} "
          f"ml=({cal_ml_a:.3f},{cal_ml_b0:.4f},{cal_ml_b1:.4f}) "
          f"push_s={push_spread:.3f} push_t={push_total:.3f} tie={p_tie:.4f}")
    return dataclasses.replace(
        cfg, beta_spread=beta_s, beta_total=beta_t,
        sigma_margin=sig_m, sigma_total=sig_t,
        cal_spread_b=cal_spread_b, cal_total_b=cal_total_b,
        cal_ml_a=cal_ml_a, cal_ml_b0=cal_ml_b0, cal_ml_b1=cal_ml_b1,
        push_spread=push_spread, push_total=push_total, p_tie=p_tie,
    )


def tune_thresholds(games: pd.DataFrame, cfg: Config) -> Config:
    """Sweep per-type EV thresholds over the train best-bet-per-game stream.

    Anti-overfit criteria (pre-registered, in this order): a candidate
    threshold pair must produce at least ~5 bets/season, be profitable in both
    halves of the train window, be profitable in a majority of individual
    seasons, and its total profit must clear a t-statistic of 2.0
    (profit / (per-bet std * sqrt(n))) — betting noise produces small positive
    train ROIs for free; only a statistically significant one earns the STRONG
    tier. Among survivors, pick the highest total profit. If nothing survives,
    fall back to conservative fixed thresholds.
    """
    res = backtest.run(cfg, games, bet_start=TRAIN[0], bet_end=TRAIN[1],
                       collect_candidates=True)
    cands = res.candidates
    # The product bets at most one bet per game: the highest-EV candidate.
    top = cands.loc[cands.groupby("game_id").ev.idxmax()].copy()
    mid = (TRAIN[0] + TRAIN[1]) // 2
    n_seasons = TRAIN[1] - TRAIN[0] + 1

    grid = itertools.product(
        [0.001, 0.005, 0.01, 0.015, 0.02, 0.03],  # min_ev_spread
        [0.005, 0.01, 0.02, 0.03, 0.05, 9.9],     # min_ev_total (9.9 = off)
    )
    best, best_profit, best_row = None, -np.inf, None
    for ts, tt in grid:
        thr = {"spread": ts, "total": tt, "moneyline": 9.9}
        sel = top[top.apply(lambda r: r.ev >= thr[r.bet_type], axis=1)]
        n = len(sel)
        if n < 5 * n_seasons:
            continue
        by_season = sel.groupby("season").profit.sum()
        first = by_season[by_season.index <= mid].sum()
        second = by_season[by_season.index > mid].sum()
        if first <= 0 or second <= 0:
            continue
        if (by_season > 0).sum() < 0.55 * len(by_season):
            continue
        profit = sel.profit.sum()
        t_stat = profit / (sel.profit.std(ddof=1) * np.sqrt(n)) if n > 1 else 0.0
        if t_stat < 2.0:
            continue
        if profit > best_profit:
            best_profit, best = profit, (ts, tt)
            wins = (sel.outcome == "win").sum()
            dec = wins + (sel.outcome == "loss").sum()
            best_row = (n, wins / dec if dec else np.nan, profit / n)

    if best is None:
        # No setting was consistently profitable vs closing lines. Fall back to
        # conservative fixed thresholds: STRONG then requires a very large
        # model/market disagreement (~8+ points), which historical data can
        # neither prove nor rule out as +EV. Documented in the backtest report.
        print("[thresholds] no robust threshold found -> conservative fallback "
              "(spread>=0.02, total>=0.03, ml off)")
        return dataclasses.replace(cfg, min_ev_spread=0.02, min_ev_total=0.03,
                                   min_ev_moneyline=9.9)
    ts, tt = best
    print(f"[thresholds] spread>={ts} total>={tt} (ml off) -> "
          f"n={best_row[0]} hit={best_row[1]:.4f} roi={best_row[2]:.4f} "
          f"profit={best_profit:.1f}u on train")
    return dataclasses.replace(cfg, min_ev_spread=ts, min_ev_total=tt,
                               min_ev_moneyline=9.9)


def main() -> None:
    games = data.completed(data.load())
    cfg = Config()

    cfg = tune_elo(games, cfg)
    cfg = tune_totals(games, cfg)

    # Raw model predictions (no betting) for the calibration fits.
    preds = backtest.run(cfg, games, bet_start=3000, bet_end=3000).predictions
    cfg = fit_calibrations(preds, cfg)

    cfg = tune_thresholds(games, cfg)
    cfg.save()
    print(f"[saved] {CONFIG_PATH}")

    print("\n=== TRAIN (2008-2019, in-sample) ===")
    tr = backtest.run(cfg, games, bet_start=TRAIN[0], bet_end=TRAIN[1])
    for k, v in tr.summary().items():
        print(f"  {k:>20}: {v:.4f}" if isinstance(v, float) else f"  {k:>20}: {v}")

    print("\n=== VALIDATION (2020-2025, out-of-sample) ===")
    va = backtest.run(cfg, games, bet_start=VALID[0], bet_end=VALID[1])
    for k, v in va.summary().items():
        print(f"  {k:>20}: {v:.4f}" if isinstance(v, float) else f"  {k:>20}: {v}")
    print("\nper-season validation:")
    print(va.per_season().to_string(float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()

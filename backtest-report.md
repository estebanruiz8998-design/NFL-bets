# Backtest Report — nflbets model, July 2026

**Goal:** a system that, for every NFL game, finds the best available bet — built and validated before the 2026 season (kickoff Sept. 9, 2026).

## Data

[nflverse `games.csv`](https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv): every game 1999–present with final scores, rest days, actual starting QBs, and market data (closing spread, total, moneylines). The 2026 season rows carry current lines, refreshed upstream — the same file powers both the backtest and the live weekly card.

Data caveats found during the build:
- The per-bet **price columns** (`*_spread_odds`, `over/under_odds`) contain alt-line artifacts in several seasons (2021–22 means of −52 to −87 instead of ~−110). The backtest therefore prices all spread/total bets at standard **−110**, which is realistic and conservative.
- Historical lines are **closing** lines. Opening/early-week lines are not in the dataset, so "beat the opener" strategies cannot be backtested here (see Limitations).

## Architecture

```
data.py        nflverse loader, franchise normalization, QB-change flags
elo.py         538-style Elo: K, MOV multiplier, HFA, rest, playoff mult,
               preseason regression, QB-change penalty
totals.py      EWMA scoring rates (off/def per team + league drift)
calibration.py logistic fits: model edges -> win probabilities
market.py      odds math: EV, de-vig, Kelly
strategy.py    candidate bets per game -> best bet + STRONG/LEAN/PASS tier
backtest.py    walk-forward simulation (leak-free by construction)
tune.py        hyperparameter search + calibration fitting + threshold sweep
weekly.py      live orchestration: refresh data -> ratings -> weekly card
config/champion.json   the tuned configuration the card runs on
```

**Protocol:** warm-up 1999–2007 (ratings only) · train 2008–2019 (every parameter fit here) · validation 2020–2025 (held out).

## Iteration log

| Iteration | Change | Train ROI | Validation ROI | Verdict |
|-----------|--------|-----------|----------------|---------|
| v0 | Raw Elo + Normal probs, dataset odds, all bet types | −1.6% (4,508 bets, 2008–25) | — | Bets almost every game; model treats its own noise as edge |
| v1 | Market anchoring (β≈0.06 fit by OLS) + EV thresholds | +4.7% (2,073) | −8.6% (731) | In-sample profit was underdog-moneyline structure, collapsed OOS |
| v2 | Logistic calibration, −110 pricing, kill odds-column exploit | +8.2% (952) | −7.5% (396) | Still ML-dominated: model adds ~no signal to ML (b₁≈0.02) |
| v3 (final) | Moneylines removed, QB-change Elo feature, robust threshold sweep (both train halves + majority of seasons must profit) | −12.7% (58) | **+2.7% (53)** | Honest: no robust edge exists vs closing lines; conservative fallback thresholds |

Final model quality (validation-inclusive window, walk-forward):

| Metric | Model | Market (close) |
|--------|-------|----------------|
| Margin MAE | 10.50 | 10.27 |
| Total MAE | 10.85 | 10.62 |
| Straight-up accuracy | 64.7% | — |
| Brier (home win) | 0.220 | — |

Calibration fits (train): P(cover) = σ(0.0166 × edge_pts) — a 6-point model/market gap ⇒ ~52.5% cover probability; ~breakeven at −110. The QB-change penalty (30 Elo ≈ 1.2 pts) improved MAE and straight-up accuracy but does not flip the economics.

## The honest headline

**This system does not beat NFL closing lines.** Nobody's public-feature Elo does; the closing line is the strongest publicly available predictor of NFL games, and our anchoring fit measures that directly: only ~6% of model/market disagreement is real signal. The final config makes ≈9 STRONG bets/season (requiring an 8+ point model/market gap); train −12.7% and validation +2.7% on those are both statistically zero on samples this small.

Two overfitting traps were caught and removed by the holdout protocol, which is the report's second headline: *any* backtest of this kind that shows large in-sample ROI is almost certainly exploiting a data artifact (v1: pre-2020 underdog-ML mispricing that no longer exists; v2: alt-line price artifacts).

## So what is it good for in 2026?

1. **Calibrated best-bet ranking for every game.** The card always names the least-bad/best option per game with an honest probability and EV — useful for deciding *which* games to bet and *which side*, and for sizing (fractional Kelly, capped 2%).
2. **Discipline.** PASS on ~95% of slates is a feature: the tiers stop you from paying vig on coin flips. The v1/v2 iterations are a demonstration of what "trust me, +8% ROI" backtests are usually made of.
3. **Stale-line detection.** The model is anchored to *efficient closing* lines. When a *posted current* line diverges 6+ points from the model — early-summer openers, lines that haven't moved after injury news — the STRONG tier fires. That's where a genuine edge can live, and it's exactly what the backtest cannot measure (closing lines only) but the live card is built to catch.

## Limitations & roadmap

- **No opening-line history** in the free dataset → line-movement/CLV strategies untested. In-season, track the card's picks against closing lines (CLV is the fastest feedback loop on whether the live edge is real).
- **No player-level features** beyond QB starts (injuries, weather, EPA-based team strength from play-by-play would be next; nflverse play-by-play is fetchable from the same host).
- **Totals model is thin** (scoring rates only); weather/roof/pace features are the known upgrades.
- Push probabilities use train-era constants; per-key-number push models (3, 7) would sharpen spread EV slightly.

## How to run

```bash
pip install -r requirements.txt
python -m nflbets.weekly              # card for the next week with posted lines
python -m nflbets.weekly --all        # every posted 2026 line
python -m nflbets.backtest            # reproduce the walk-forward backtest
python -m nflbets.tune                # re-tune (rewrites config/champion.json)
python -m pytest tests/               # test suite
```

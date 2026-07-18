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
| v3 | Moneylines removed, QB-change Elo feature, robust threshold sweep (both train halves + majority of seasons must profit) | −12.7% (58) | +2.7% (53) | No robust edge; conservative fallback thresholds |
| v4 (final) | Post-audit: tie-game Elo fix, window-scoped metrics, **t ≥ 2 significance gate on the threshold sweep** (which caught a fourth overfit: +5.4% on 144 train bets → −14.6% on 141 validation bets) | −11.2% (57) | **+2.7% (53)** | Same conclusion, now audited: 11-agent adversarial audit confirmed no leakage, correct grading of all bets, reproducible calibrations |

Final model quality (walk-forward, correctly window-scoped after audit):

| Metric | Train 2008–19 model | Train market | Validation 2020–25 model | Validation market |
|--------|--------------------:|-------------:|-------------------------:|------------------:|
| Margin MAE | 10.62 | 10.40 | 10.14 | 9.77 |
| Total MAE | 10.68 | 10.54 | 10.73 | 10.31 |
| Straight-up accuracy | 65.3% | — | 64.6% | — |
| Brier (home win) | 0.218 | — | 0.222 | — |

## The verdict, with statistics

**The model engine does not beat NFL closing lines. Verdict: NO EDGE.**

- Validation STRONG stream: 28–24–1, hit 53.9%, **95% CI [40.5%, 66.7%]** — the interval contains both coin-flip (50%) and −110 breakeven (52.4%). Flat ROI +2.7% with **bootstrap 95% CI [−22.5%, +28.0%]**; p = 0.83 against breakeven. Statistically indistinguishable from zero.
- The decisive test: the calibration slope P(cover) = σ(b × edge) fit on train is b = 0.0166; refit on the untouched 2020–2025 seasons it is **b = 0.0012 (SE 0.0155, z = 0.08)**. Out of sample, the model's disagreement with the closing line carries **no detectable predictive signal whatsoever**. The training-era relationship did not replicate.
- The model's margin error is worse than the market's in both windows (10.62 vs 10.40; 10.14 vs 9.77). Nobody's public box-score model beats the close; ours measurably doesn't either.

**Four overfitting traps were caught and removed by the holdout protocol** — v1 (underdog-moneyline regime), v2 (alt-line price artifacts), v3→v4 (a threshold config that passed consistency gates in-sample at +5.4% and lost 14.6% out of sample), each showing exactly how "profitable backtest" claims are usually manufactured. Treat that as this report's second product.

An 11-agent adversarial audit (independent reproduction of every claim) confirmed: zero look-ahead leakage (prefix-invariance test), 111/111 historical bets graded correctly from raw scores, calibrations reproducible to 1e-6, Kelly math exact, and every documented number regenerable from the checked-in code and config.

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

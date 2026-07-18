# NFL-bets

A model + orchestration pipeline that, for every NFL game, finds the best available bet — backtested on 1999–2025 and tuned before the 2026 season.

> ⚠️ Betting involves risk and no model guarantees profit — read the [backtest report](backtest-report.md) before trusting any number here. 1-800-GAMBLER.

## What's here

| Piece | File(s) |
|-------|---------|
| **Weekly best-bet card** (the product) | `python -m nflbets.weekly` → [cards/](cards/) |
| Model + strategy package | [`nflbets/`](nflbets/) |
| Walk-forward backtester | `python -m nflbets.backtest` |
| Tuner (train 2008–19, validate 2020–25) | `python -m nflbets.tune` → [`config/champion.json`](config/champion.json) |
| **Backtest report** (read this) | [backtest-report.md](backtest-report.md) |
| Season futures analysis (July 2026) | [futures-2026.md](futures-2026.md) |
| Week 1 hand-researched card (July 2026) | [week1-2026-best-bets.md](week1-2026-best-bets.md) |

## Quickstart

```bash
pip install -r requirements.txt
python -m nflbets.weekly          # best bet for every game, next week with lines
python -m nflbets.weekly --all    # every posted 2026 line
python -m pytest tests/           # 11 tests
```

The card auto-downloads fresh data (schedule, results, current lines) from nflverse, replays history to compute ratings, and emits a markdown table: matchup, market line, model margin/total, raw edge, best bet, tier, calibrated win probability, EV, and Kelly stake.

## How it works

1. **Elo ratings** (margin-of-victory, home-field, rest, playoff, QB-change penalty) predict each game's margin; an EWMA scoring model predicts the total.
2. **Calibration layer**: logistic models fit on 2008–2019 map "model vs market disagreement" into real win probabilities — the model's opinion is worth ~6% of its nominal disagreement with the market, and the system knows that.
3. **Strategy**: every game gets candidate bets (spread both sides, total both sides) priced at −110; the highest-EV candidate is the *best bet*, tiered **STRONG** (edge clears tuned threshold — rare), **LEAN** (thin positive EV), or **PASS** (line is fair).
4. **Walk-forward backtest** replays every season chronologically with zero look-ahead; the tuner never touches the 2020–2025 holdout until the final evaluation.

**Honest summary of results:** the system does not beat closing lines (nobody's public-data Elo does) — validation ROI on its rare STRONG bets is +2.7% on n=53, statistically zero. Its real value is calibrated game-by-game rankings, bet discipline (it PASSes most games), and flagging stale posted lines in-season, where a genuine edge can exist. Details, iteration log, and the two overfitting traps we caught along the way: [backtest-report.md](backtest-report.md).

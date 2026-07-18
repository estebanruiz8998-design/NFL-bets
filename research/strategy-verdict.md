# Strategy Verdict — Professional Backtest, July 2026

**The question:** does this betting strategy work? **The answer: no component of it has a demonstrated edge against closing lines.** Details, statistics, and what that means below. All studies are reproducible (`research/*.py`), were graded at standard −110, and every result was independently re-implemented from scratch by a second, blind analysis before being accepted.

## Verdict by component

| Component | Verdict | Evidence |
|-----------|---------|----------|
| **Model engine** (Elo + calibration, STRONG tier) | **NO EDGE** | Validation 28–24–1, ROI +2.7%, bootstrap 95% CI [−22.5%, +28.0%], p=0.83 vs breakeven. Decisively: the train-era calibration slope (0.0166) refit on 2020–2025 is **0.0012 (z=0.08)** — out of sample, model/market disagreement predicts nothing. |
| **Week 1 "big home favorite"** (the Jaguars −7 pattern) | **NO SUPPORT** | Home favorites −6.5 to −7.5 in Week 1, 2002–2025: **19–22, −11.5% ROI** (ns). Since 2014 the *dog* side went 14–7 — the pattern's recent lean is against the recommended side. |
| **Week 1 "disrespected champion" dog** (the Broncos +2.5 pattern) | **NO SUPPORT — historically negative** | Prior-season division winners as +1 to +6.5 dogs vs non-playoff teams in Week 1: **5–9–1, −29.7% ROI** (n too small for significance; the broader any-opponent version is 20–28–2, −19.6%). Weeks 1–8 version (n=344): coin flip. |
| **Week 1 playoff-team road dog** (the 49ers +3.5 pattern) | **NO SUPPORT — historically the fade side won** | Playoff-team road dogs +2.5 to +4 in Week 1: **9–19–3 (32.1%, p=0.037)**; all playoff-team road dogs: **26–45–4 (36.6%, p=0.009)**. The market historically *overrated* last year's playoff road teams — the opposite of the recommendation. Even that fade signal is dead post-2014 (~coin flip since), and after multiple-comparison correction (16 rules tested) it does not survive as a bettable edge. |
| **Defending SB champ home opener** (the Seahawks −3.5 pattern) | **INSUFFICIENT DATA** | 9–3–1 (+39.9% ROI) laying ≤6.5 at home — but n=13 in 24 seasons, p=0.15. Anecdote-sized. The fair-sample test (champs as favorites, all games, n=315) is a pure coin flip (51.5%, −1.7%). |
| **Week 1 market baselines** | **MARKET IS EFFICIENT** | W1 homes 49.1% (ns), W1 dogs 52.1% (ns), W1 unders 54.1% (+3.2%, p=0.12, ns). The only significant result anywhere: blindly betting dogs in weeks 2–18 **loses** the vig (50.8%, p=0.021 on the losing side). |
| **Futures slate** (Bengals +200, Patriots +120, Bills +1000, …) | **UNTESTABLE** | No historical futures-odds dataset is available, so these cannot be backtested. They rest on qualitative expert consensus and web-verified facts — treat them as researched opinions, not edges. |

## Methodology

- **Data**: nflverse game file, 2002–2025 (post-realignment), closing spreads/totals, all grading at −110.
- **Pre-registration**: every rule was defined exactly (spread bands, qualifiers, seasons) before any results were seen; contrarian and no-qualifier controls were included by design.
- **Blind verification**: each family's numbers were re-derived from scratch by an independent implementation that did not read the original script; 4 of 5 families reproduced *exactly* (to the bet), and the fifth (champion-dog) differed only in the division-winner derivation (record-based vs playoff-seed-based; n=15 vs 14, hit 35.7% vs 30.8%) — both versions agree it is negative and insignificant.
- **Statistics**: Wilson 95% CIs, exact two-sided binomial tests vs both 0.500 and the −110 breakeven (0.5238), first/second-era splits (2002–2013 vs 2014–2025) to expose regime drift, and Bonferroni awareness across the 16 rules tested.
- **Engine integrity**: the model backtest ran on an engine that passed an 11-agent adversarial audit (no look-ahead leakage by prefix-invariance test; 111/111 bets re-graded correctly; calibrations reproducible to 1e-6).

## What the era splits teach

Nearly every "pattern" flips sign between 2002–2013 and 2014–2025 (W1 home favorites 52%→46%; playoff road-dog fade −61%→+3%; champ-dog 32%→52%). This is what betting folklore looks like under a microscope: angles that were real (or lucky) in one era get arbitraged away or reverse. Any Week 1 rule someone sells you was probably fit to one of these half-windows.

## The bottom line, professionally stated

1. **Nothing in this strategy — model or slip heuristics — is proven +EV against closing lines.** Several recommended patterns' historical analogues actually favored the other side.
2. **Absence of evidence here is close to evidence of absence** for the game-bet heuristics: samples of 40–380 bets with CIs centered at or below breakeven, on rules that were defined exactly as recommended.
3. The futures cannot be judged by backtest; they are opinions with documented reasoning and counter-arguments. If you bet them, you are betting on the reasoning, not on data.
4. **What survives professionally**: bet small or not at all; if you bet, the discipline layer is the value — price conditions (never lay through key numbers), one-position sizing for correlated tickets, fractional-Kelly caps, and tracking your bets against closing lines during the season (CLV is the only fast feedback loop that can tell you within months whether any live edge exists).

*Reproduce everything:* `python3 research/w1_bigfav.py` (and siblings), `python3 -m nflbets.backtest`, `python3 -m nflbets.tune`.

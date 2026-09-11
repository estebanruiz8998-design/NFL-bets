# Paper-trade verdict — Week 1 2026

*Graded 2026-09-11 · PARTIAL — 2 of 16 Week 1 games final; final grading after Monday night, Sept 14*

Every game position is graded at its entry line and odds against the actual result, and its final closing-line value (CLV) is measured against the nflverse closing line. Futures and win totals cannot be graded until the season ends and are excluded here (their price movement stays on the dashboard).

## By arm

| Arm | Thesis | Entered | Graded | W-L-P | Units | Final CLV (stake-wtd pts) | No-bet |
|---|---|---|---|---|---|---|---|
| A | the July slip: expert-consensus opinions (original entries) | 6 | 2 | 1-1-0 | -0.02u | -0.25 | 0 |
| B | backtest-informed contrarian: the sides the 2002-2025 patterns leaned toward, incl. two paired opposites of Arm A | 3 | 1 | 0-1-0 | -0.25u | +0.50 | 0 |
| U | Week 1 unders basket: the only baseline with a stable positive lean (54.1% since 2002) | 15 | 2 | 2-0-0 | +0.09u | +0.50 | 0 |
| M | model-edge tracker: biggest Elo/market gaps; tests whether the market moves toward the model | 3 | 0 | 0-0-0 | +0.00u | — | 0 |
| S | the Sept 8 final slip: five price-rule tickets from the 55-agent review, entered only where the reference feed met the stated price condition | 2 | 1 | 1-0-0 | +0.22u | +0.00 | 1 |

**All arms: 4-2-0, +0.04u over 6 graded tickets.**

## Graded positions

| Arm | Position | Entry | Close | Final CLV | Score | Outcome | Units |
|---|---|---|---|---|---|---|---|
| A | Seahawks −3.5 vs Patriots (opener) | -3.5 | -3 | -0.5 | NE 10 @ SEA 13 | loss | -0.25u |
| A | 49ers +3.5 vs Rams, Melbourne (Wk 1) | +3.5 | +3.5 | 0.0 | SF 27 @ LA 7 | win | +0.23u |
| B | Rams −3 vs 49ers (Wk 1) — fade the playoff road dog; opposite of waiting SF +3.5 | -3 | -3.5 | 0.5 | SF 27 @ LA 7 | loss | -0.25u |
| U | NE@SEA Under 44.5 (Wk 1 unders basket) | U 44.5 | U 44.5 | 0.0 | NE 10 @ SEA 13 | win | +0.05u |
| U | SF@LA Under 48.5 (Wk 1 unders basket) | U 48.5 | U 47.5 | 1.0 | SF 27 @ LA 7 | win | +0.05u |
| S | NE@SEA Under 44.5 (final slip headline; entered at the feed's −112) | U 44.5 | U 44.5 | 0.0 | NE 10 @ SEA 13 | win | +0.22u |
| S | Patriots +3.5 (final slip; only at −115 or better, or +3 at +100 or better) | — | +3 | — | NE 10 @ SEA 13 | no bet | +0.00u |

*Pending (game not yet final): 27 positions — w1-den-kc, lean-ten-over, lean-mia-kc, w1-jax-cle, w1-phi-was, w1-min-gb, b-no-det, b-kc-den, u-chi_car, u-tb_cin, u-no_det, u-buf_hou, u-bal_ind, u-cle_jax, u-atl_pit, u-ari_lac, u-mia_lv, u-gb_min, u-was_phi, u-dal_nyg, u-den_kc, m-jax-phi, m-den-la, m-ari-lac, s-buf_hou-u445, s-cle-plus9, s-den-plus3.*

## How to read it

- A win-loss record over a handful of tickets is noise; the number that matters is final CLV, and even that is a small-sample signal. The pre-season verdict — no component has demonstrated edge against closing lines — stands unless a full season of CLV says otherwise.
- Arm S is the Sept 8 slip graded strictly: a ticket counts only if the reference feed met its price rule, so "no bet" rows are the discipline layer working, not missing data.
- Reproduce: `python3 papertrade/track.py && python3 papertrade/grade.py && python3 papertrade/build.py`.

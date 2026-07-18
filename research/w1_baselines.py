#!/usr/bin/env python3
"""
Week 1 market-efficiency baselines (2002-2025, post-realignment).

Rules:
  R1: REG week 1, bet HOME spread in every game.
  R2: REG week 1, bet the UNDERDOG spread in every game (skip pick'em spread_line == 0).
  R3: REG week 1, bet UNDER the total_line in every game.
  R4: REG weeks 2-18, bet the UNDERDOG spread (comparison baseline for R2).

Conventions (nflverse games.csv):
  result      = home_score - away_score
  spread_line = expected HOME margin (positive = home favored)
  home covers iff result > spread_line; push iff result == spread_line
  dog side: away team if spread_line > 0, home team if spread_line < 0
  under wins iff total < total_line; push iff equal

Grading: flat 1u at -110 (win +100/110, loss -1, push 0).
"""

import math

import pandas as pd

DATA = "/home/user/NFL-bets/data/games.csv"
PAYOUT = 100.0 / 110.0  # win profit per 1u at -110


def binom_pmf_log(k, n, p):
    return (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log(1 - p)
    )


def binom_test_two_sided(k, n, p):
    """Exact two-sided binomial test (scipy 'exact' convention: sum all
    outcomes with pmf <= pmf(k), with a small relative tolerance)."""
    if n == 0:
        return float("nan")
    log_pk = binom_pmf_log(k, n, p)
    thresh = log_pk + 1e-7
    total = 0.0
    for i in range(n + 1):
        if binom_pmf_log(i, n, p) <= thresh:
            total += math.exp(binom_pmf_log(i, n, p))
    return min(1.0, total)


def wilson_ci(w, n, z=1.959963984540054):
    """Wilson 95% CI for w successes in n trials."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = w / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, center + half)


def grade(df, win_mask, push_mask):
    """Return (n, wins, losses, pushes) from boolean masks over df rows."""
    n = len(df)
    pushes = int(push_mask.sum())
    wins = int(win_mask.sum())
    losses = n - wins - pushes
    return n, wins, losses, pushes


def summarize(rule_id, definition, sub, win_mask, push_mask):
    n, w, l, p = grade(sub, win_mask, push_mask)
    decided = w + l
    hit = w / decided if decided else float("nan")
    roi = (w * PAYOUT - l) / n if n else float("nan")
    lo, hi = wilson_ci(w, decided)
    p_be = binom_test_two_sided(w, decided, 0.5238)
    p_half = binom_test_two_sided(w, decided, 0.5)

    # era split 2002-2013 vs 2014-2025
    era_parts = []
    for lab, (a, b) in [("2002-2013", (2002, 2013)), ("2014-2025", (2014, 2025))]:
        m = (sub["season"] >= a) & (sub["season"] <= b)
        se = sub[m]
        ne, we, le, pe = grade(se, win_mask[m], push_mask[m])
        de = we + le
        hite = we / de if de else float("nan")
        roie = (we * PAYOUT - le) / ne if ne else float("nan")
        era_parts.append(
            f"{lab}: n={ne} {we}-{le}-{pe}, hit={hite:.4f}, roi={roie:+.4f}"
        )
    era_split = " | ".join(era_parts)

    return {
        "rule_id": rule_id,
        "definition": definition,
        "n": n,
        "wins": w,
        "losses": l,
        "pushes": p,
        "hit": round(hit, 4),
        "roi": round(roi, 4),
        "ci_lo": round(lo, 4),
        "ci_hi": round(hi, 4),
        "p_vs_breakeven": round(p_be, 4),
        "p_vs_half": round(p_half, 4),
        "era_split": era_split,
    }


def main():
    df = pd.read_csv(DATA)
    df = df[
        (df["game_type"] == "REG")
        & (df["season"] >= 2002)
        & (df["season"] <= 2025)
        & df["result"].notna()
    ].copy()
    df["week"] = pd.to_numeric(df["week"])

    results = []

    # --- R1: week 1, home spread ---
    r1 = df[(df["week"] == 1) & df["spread_line"].notna()].copy()
    win = r1["result"] > r1["spread_line"]
    push = r1["result"] == r1["spread_line"]
    results.append(
        summarize(
            "R1",
            "REG week 1, 2002-2025: bet HOME spread in every game at -110",
            r1,
            win,
            push,
        )
    )

    # --- R2: week 1, dog spread (skip pick'em) ---
    r2 = df[
        (df["week"] == 1) & df["spread_line"].notna() & (df["spread_line"] != 0)
    ].copy()
    home_dog = r2["spread_line"] < 0
    # home dog covers iff result > spread_line; away dog covers iff result < spread_line
    win = (home_dog & (r2["result"] > r2["spread_line"])) | (
        ~home_dog & (r2["result"] < r2["spread_line"])
    )
    push = r2["result"] == r2["spread_line"]
    results.append(
        summarize(
            "R2",
            "REG week 1, 2002-2025: bet UNDERDOG spread in every game "
            "(skip spread_line == 0) at -110",
            r2,
            win,
            push,
        )
    )

    # --- R3: week 1, unders ---
    r3 = df[(df["week"] == 1) & df["total_line"].notna() & df["total"].notna()].copy()
    win = r3["total"] < r3["total_line"]
    push = r3["total"] == r3["total_line"]
    results.append(
        summarize(
            "R3",
            "REG week 1, 2002-2025: bet UNDER the total_line in every game at -110",
            r3,
            win,
            push,
        )
    )

    # --- R4: weeks 2-18, dog spread ---
    r4 = df[
        (df["week"] >= 2)
        & (df["week"] <= 18)
        & df["spread_line"].notna()
        & (df["spread_line"] != 0)
    ].copy()
    home_dog = r4["spread_line"] < 0
    win = (home_dog & (r4["result"] > r4["spread_line"])) | (
        ~home_dog & (r4["result"] < r4["spread_line"])
    )
    push = r4["result"] == r4["spread_line"]
    results.append(
        summarize(
            "R4",
            "REG weeks 2-18, 2002-2025: bet UNDERDOG spread in every game "
            "(skip spread_line == 0) at -110",
            r4,
            win,
            push,
        )
    )

    for r in results:
        print(f"\n{r['rule_id']}: {r['definition']}")
        print(
            f"  n={r['n']}  W-L-P={r['wins']}-{r['losses']}-{r['pushes']}  "
            f"hit={r['hit']:.4f}  ROI={r['roi']:+.4f}"
        )
        print(
            f"  Wilson95=[{r['ci_lo']:.4f}, {r['ci_hi']:.4f}]  "
            f"p_vs_.5238={r['p_vs_breakeven']:.4f}  p_vs_.50={r['p_vs_half']:.4f}"
        )
        print(f"  era split: {r['era_split']}")

    return results


if __name__ == "__main__":
    main()

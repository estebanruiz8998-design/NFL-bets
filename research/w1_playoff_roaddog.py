#!/usr/bin/env python3
"""
Week 1 playoff-team road dogs study (the "49ers +3.5 in Melbourne" pattern).

Rules (bet AWAY spread, graded at -110: win +0.9091u, loss -1u, push 0):
  R1: REG week 1, away team getting 2.5 to 4 (spread_line in [2.5, 4])
      AND the away team made the playoffs the PRIOR season.
  R2: REG week 1, any away dog (spread_line > 0) that made the playoffs
      the prior season.
  R3: REG week 1, away dogs +2.5 to +4 regardless of playoff history
      (control for the playoff qualifier).

Conventions (nflverse games.csv):
  result = home_score - away_score; spread_line = expected HOME margin
  (positive = home favored). Home covers iff result > spread_line; push iff
  equal -> AWAY covers iff result < spread_line.
  Playoff appearance in season S = team appears in any game_type != 'REG'
  row of season S. Franchise moves OAK/LV, SD/LAC, STL/LA linked.
  Seasons 2002-2025 (post-realignment), completed games only.
"""

import math
import pandas as pd

DATA = "/home/user/NFL-bets/data/games.csv"
SEASONS = range(2002, 2026)
ERA1 = (2002, 2013)
ERA2 = (2014, 2025)
WIN_PAY = 100.0 / 110.0  # +0.9091u per -110 win

# Franchise continuity map -> canonical franchise codes
FRANCHISE = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def canon(team):
    return FRANCHISE.get(team, team)


def wilson_ci(w, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = w / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, center + half)


def binom_two_sided(w, n, p0):
    """Exact two-sided binomial p-value (sum of outcome probs <= P(observed))."""
    if n == 0:
        return float("nan")
    from math import comb

    pobs = comb(n, w) * (p0 ** w) * ((1 - p0) ** (n - w))
    tol = pobs * (1 + 1e-9)
    total = 0.0
    for k in range(n + 1):
        pk = comb(n, k) * (p0 ** k) * ((1 - p0) ** (n - k))
        if pk <= tol:
            total += pk
    return min(1.0, total)


def grade(df):
    """Grade AWAY spread bets. Away covers iff result < spread_line."""
    wins = int((df["result"] < df["spread_line"]).sum())
    pushes = int((df["result"] == df["spread_line"]).sum())
    losses = int((df["result"] > df["spread_line"]).sum())
    return wins, losses, pushes


def summarize(df, rule_id, definition):
    w, l, p = grade(df)
    n = len(df)
    dec = w + l
    hit = w / dec if dec else float("nan")
    roi = (w * WIN_PAY - l * 1.0) / n if n else float("nan")
    lo, hi = wilson_ci(w, dec)
    p_be = binom_two_sided(w, dec, 0.5238)
    p_half = binom_two_sided(w, dec, 0.50)

    # Era split
    era_parts = []
    for (a, b) in (ERA1, ERA2):
        sub = df[(df["season"] >= a) & (df["season"] <= b)]
        ew, el, ep = grade(sub)
        edec = ew + el
        ehit = ew / edec if edec else float("nan")
        eroi = (ew * WIN_PAY - el * 1.0) / len(sub) if len(sub) else float("nan")
        era_parts.append(
            f"{a}-{b}: n={len(sub)} {ew}-{el}-{ep} "
            f"hit={ehit:.3f} roi={eroi:+.3f}" if edec else f"{a}-{b}: n={len(sub)} no decided bets"
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

    # Playoff appearance sets by season (canonical franchise codes)
    po = df[df["game_type"] != "REG"]
    playoff_teams = {}
    for season, g in po.groupby("season"):
        teams = set(g["home_team"]) | set(g["away_team"])
        playoff_teams[season] = {canon(t) for t in teams}

    # Week 1 REG games, completed, with spread, 2002-2025
    wk1 = df[
        (df["game_type"] == "REG")
        & (pd.to_numeric(df["week"], errors="coerce") == 1)
        & (df["season"].isin(SEASONS))
        & df["result"].notna()
        & df["spread_line"].notna()
    ].copy()

    wk1["away_playoff_prior"] = wk1.apply(
        lambda r: canon(r["away_team"]) in playoff_teams.get(r["season"] - 1, set()),
        axis=1,
    )

    r1 = wk1[
        (wk1["spread_line"] >= 2.5)
        & (wk1["spread_line"] <= 4.0)
        & wk1["away_playoff_prior"]
    ]
    r2 = wk1[(wk1["spread_line"] > 0) & wk1["away_playoff_prior"]]
    r3 = wk1[(wk1["spread_line"] >= 2.5) & (wk1["spread_line"] <= 4.0)]

    results = [
        summarize(
            r1,
            "R1",
            "Wk1 REG away dog +2.5 to +4 (spread_line in [2.5,4]), away team made "
            "playoffs prior season -> bet AWAY spread",
        ),
        summarize(
            r2,
            "R2",
            "Wk1 REG any away dog (spread_line > 0), away team made playoffs prior "
            "season -> bet AWAY spread",
        ),
        summarize(
            r3,
            "R3",
            "Wk1 REG away dog +2.5 to +4, regardless of playoff history -> bet AWAY "
            "spread (control)",
        ),
    ]

    out = pd.DataFrame(results)
    pd.set_option("display.width", 250)
    print(out.to_string(index=False))
    return results


if __name__ == "__main__":
    main()

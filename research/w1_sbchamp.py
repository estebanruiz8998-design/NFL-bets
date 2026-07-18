#!/usr/bin/env python3
"""
Defending Super Bowl champion spread angles ("Seahawks -3.5 opener" family).

Data: /home/user/NFL-bets/data/games.csv (nflverse schema).
Conventions:
  result      = home_score - away_score
  spread_line = expected HOME margin (positive = home favored)
  home covers iff result > spread_line; push iff result == spread_line
Grading: flat 1u at -110 (win +0.9091u, loss -1u, push 0).
Seasons analyzed: 2002-2025 (post-realignment).

Defending champ for season S = winner of season S-1's final playoff game
(game_type == 'SB'; fall back to last postseason game by gameday if absent).
Franchise moves handled: OAK/LV, SD/LAC, STL/LA treated as the same team
when linking champion identity across seasons.

Rules:
  R1: REG week 1, defending SB champ at home laying 6.5 or fewer points
      (0 < spread_line <= 6.5) -> bet the champ's spread.
  R2: REG week 1, defending SB champ anywhere, any line -> bet champ spread.
  R3: All REG-season games in which the defending SB champ is the favorite
      -> bet the champ's spread.
"""

import math
import pandas as pd

DATA = "/home/user/NFL-bets/data/games.csv"
SEASONS = range(2002, 2026)          # 2002..2025 inclusive
BREAKEVEN = 0.5238                   # -110 breakeven
WIN_PAYOUT = 100.0 / 110.0           # +0.9091u per win at -110

# Franchise relocation canonicalization (same franchise across seasons)
CANON = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def canon(team: str) -> str:
    return CANON.get(team, team)


def load():
    df = pd.read_csv(DATA)
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    return df


def defending_champs(df) -> dict:
    """Map season S -> canonical abbreviation of the winner of season S-1's SB."""
    champs = {}
    for s in SEASONS:
        prior = df[(df.season == s - 1) & (df.game_type != "REG") & df.result.notna()]
        sb = prior[prior.game_type == "SB"]
        pool = sb if len(sb) else prior
        if not len(pool):
            continue
        g = pool.sort_values("gameday").iloc[-1]
        if g.result == 0:
            raise ValueError(f"Season {s-1} title game tied?")
        winner = g.home_team if g.result > 0 else g.away_team
        champs[s] = canon(winner)
    return champs


def grade(row, champ):
    """Return ('W'|'L'|'P') for a bet on the champ's spread."""
    if canon(row.home_team) == champ:
        margin = row.result - row.spread_line        # champ is home
    else:
        margin = row.spread_line - row.result        # champ is away
    if margin > 0:
        return "W"
    if margin < 0:
        return "L"
    return "P"


def binom_pmf(k, n, p):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_test_two_sided(k, n, p):
    """Exact two-sided binomial test (scipy 'binomtest' style: sum of all
    outcomes with pmf <= pmf(k), with small tolerance for float noise)."""
    if n == 0:
        return float("nan")
    pk = binom_pmf(k, n, p)
    tol = 1e-12
    pv = sum(binom_pmf(i, n, p) for i in range(n + 1)
             if binom_pmf(i, n, p) <= pk * (1 + tol))
    return min(1.0, pv)


def wilson_ci(w, n, z=1.959963984540054):
    if n == 0:
        return (float("nan"), float("nan"))
    p = w / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, center + half)


def summarize(bets):
    """bets: list of (season, result_char). Returns stats dict."""
    w = sum(1 for _, r in bets if r == "W")
    l = sum(1 for _, r in bets if r == "L")
    p = sum(1 for _, r in bets if r == "P")
    n = len(bets)
    dec = w + l
    hit = w / dec if dec else float("nan")
    roi = (w * WIN_PAYOUT - l * 1.0) / n if n else float("nan")
    lo, hi = wilson_ci(w, dec)
    p_be = binom_test_two_sided(w, dec, BREAKEVEN) if dec else float("nan")
    p_half = binom_test_two_sided(w, dec, 0.5) if dec else float("nan")

    def era(lo_s, hi_s):
        sub = [(s, r) for s, r in bets if lo_s <= s <= hi_s]
        ew = sum(1 for _, r in sub if r == "W")
        el = sum(1 for _, r in sub if r == "L")
        ep = sum(1 for _, r in sub if r == "P")
        ed = ew + el
        ehit = ew / ed if ed else float("nan")
        eroi = (ew * WIN_PAYOUT - el) / len(sub) if sub else float("nan")
        return f"{ew}-{el}-{ep} hit={ehit:.3f} roi={eroi:+.3f}" if sub else "n=0"

    return dict(n=n, wins=w, losses=l, pushes=p, hit=hit, roi=roi,
                ci_lo=lo, ci_hi=hi, p_vs_breakeven=p_be, p_vs_half=p_half,
                era1=era(2002, 2013), era2=era(2014, 2025))


def main():
    df = load()
    champs = defending_champs(df)

    reg = df[(df.game_type == "REG") & df.result.notna() &
             df.spread_line.notna() & df.season.isin(SEASONS)].copy()
    reg["home_c"] = reg.home_team.map(canon)
    reg["away_c"] = reg.away_team.map(canon)
    reg["champ"] = reg.season.map(champs)
    champ_games = reg[(reg.home_c == reg.champ) | (reg.away_c == reg.champ)].copy()
    champ_games["champ_home"] = champ_games.home_c == champ_games.champ
    champ_games["champ_fav"] = (
        (champ_games.champ_home & (champ_games.spread_line > 0)) |
        (~champ_games.champ_home & (champ_games.spread_line < 0))
    )

    wk1 = champ_games[champ_games.week == 1]

    r1_rows = wk1[wk1.champ_home & (wk1.spread_line > 0) & (wk1.spread_line <= 6.5)]
    r2_rows = wk1
    r3_rows = champ_games[champ_games.champ_fav]

    rules = {
        "R1: wk1 champ home, laying <=6.5": r1_rows,
        "R2: wk1 champ, any site/line": r2_rows,
        "R3: champ as favorite, all REG": r3_rows,
    }

    print(f"Defending champs 2002-2025: {champs}\n")
    for name, rows in rules.items():
        bets = [(r.season, grade(r, r.champ)) for r in rows.itertuples()]
        s = summarize(bets)
        print(name)
        print(f"  n={s['n']}  W-L-P {s['wins']}-{s['losses']}-{s['pushes']}"
              f"  hit={s['hit']:.4f}  ROI={s['roi']:+.4f}")
        print(f"  Wilson95 [{s['ci_lo']:.4f}, {s['ci_hi']:.4f}]"
              f"  p(vs .5238)={s['p_vs_breakeven']:.4f}"
              f"  p(vs .50)={s['p_vs_half']:.4f}")
        print(f"  2002-2013: {s['era1']}")
        print(f"  2014-2025: {s['era2']}\n")

    # Per-game detail for the tiny-n week-1 rules
    print("Week-1 champ game log (R2 universe):")
    for r in wk1.sort_values("season").itertuples():
        site = "H" if r.champ_home else "A"
        line = r.spread_line if r.champ_home else -r.spread_line
        print(f"  {r.season} {r.champ} ({site}) vs "
              f"{r.away_team if r.champ_home else r.home_team} "
              f"champ line {-line:+.1f}  result(home) {r.result:+.0f}  -> {grade(r, r.champ)}")


if __name__ == "__main__":
    main()

"""
Week 1 "disrespected champion" study (the "Broncos +2.5 at Chiefs" pattern).

Data: /home/user/NFL-bets/data/games.csv (nflverse).
Conventions:
  result      = home_score - away_score
  spread_line = expected HOME margin (positive = home favored)
  home covers iff result > spread_line; push iff equal.
  Champion's own spread = -spread_line if champion is home, +spread_line if away.

Rules (bet seasons 2002-2025, REG games, graded flat -110):
  R1: REG week 1, team was its division's winner the PRIOR season AND is an
      underdog of 1 to 6.5 (its spread in [+1, +6.5]) AND opponent did NOT make
      the playoffs the prior season -> bet the champion's spread.
  R2: REG week 1, prior-season division winner underdog of 1 to 6.5 vs ANY
      opponent -> bet the champion's spread.
  R3: REG weeks 1-8, prior-season division winner getting 1 to 6.5 -> bet the
      champion's spread.

Prior-season division winner = best REG win pct within the (hardcoded 2002+)
division that season; ties broken by point differential (coarse tiebreak --
NFL's real head-to-head/common-games tiebreakers are NOT applied).
Note: for the 2002 bet season the "prior season" is 2001, which is grouped by
the 2002+ division map anachronistically (as instructed).

Franchise normalization: OAK->LV, SD->LAC, STL->LA.
Playoff appearance = team appears in any game_type != 'REG' row that season.

Usage: python3 /home/user/NFL-bets/research/w1_champ_dog.py
"""
import math

import pandas as pd

DATA = "/home/user/NFL-bets/data/games.csv"
BET_SEASONS = range(2002, 2026)          # 2002..2025 inclusive
ERA1 = (2002, 2013)
ERA2 = (2014, 2025)
BREAKEVEN = 0.5238                        # -110 breakeven
WIN_UNITS = 100.0 / 110.0                 # +0.9091u per win at -110

ALIAS = {"OAK": "LV", "SD": "LAC", "STL": "LA"}

DIVISIONS = {
    "AFC East":  ["BUF", "MIA", "NE", "NYJ"],
    "AFC North": ["BAL", "CIN", "CLE", "PIT"],
    "AFC South": ["HOU", "IND", "JAX", "TEN"],
    "AFC West":  ["DEN", "KC", "LV", "LAC"],
    "NFC East":  ["DAL", "NYG", "PHI", "WAS"],
    "NFC North": ["CHI", "DET", "GB", "MIN"],
    "NFC South": ["ATL", "CAR", "NO", "TB"],
    "NFC West":  ["ARI", "LA", "SEA", "SF"],
}
TEAM_DIV = {t: d for d, ts in DIVISIONS.items() for t in ts}


def norm(team):
    return ALIAS.get(team, team)


def load():
    df = pd.read_csv(DATA)
    df["home_team"] = df["home_team"].map(norm)
    df["away_team"] = df["away_team"].map(norm)
    return df


def division_winners(df, season):
    """Return set of division-winning teams (normalized codes) for a season.

    Best REG W-L (win pct) within division; tiebreak = point differential.
    """
    reg = df[(df["season"] == season) & (df["game_type"] == "REG")
             & df["result"].notna()]
    rec = {}  # team -> [wins, losses, ties, pointdiff]
    for r in reg.itertuples():
        h, a, res = r.home_team, r.away_team, r.result
        for t in (h, a):
            rec.setdefault(t, [0, 0, 0, 0.0])
        if res > 0:
            rec[h][0] += 1
            rec[a][1] += 1
        elif res < 0:
            rec[a][0] += 1
            rec[h][1] += 1
        else:
            rec[h][2] += 1
            rec[a][2] += 1
        rec[h][3] += res
        rec[a][3] -= res
    winners = set()
    for div, teams in DIVISIONS.items():
        best, best_key = None, None
        for t in teams:
            if t not in rec:
                continue  # e.g. HOU before 2002
            w, l, ties, pd_ = rec[t]
            games = w + l + ties
            pct = (w + 0.5 * ties) / games if games else 0.0
            key = (pct, pd_)
            if best is None or key > best_key:
                best, best_key = t, key
        if best is not None:
            winners.add(best)
    return winners


def playoff_teams(df, season):
    po = df[(df["season"] == season) & (df["game_type"] != "REG")]
    return set(po["home_team"]) | set(po["away_team"])


def binom_pmf(k, n, p):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_test_two_sided(k, n, p):
    """Exact two-sided binomial test (scipy convention: sum all outcome
    probabilities <= pmf(k) within a small relative tolerance)."""
    if n == 0:
        return float("nan")
    pk = binom_pmf(k, n, p)
    tol = 1 + 1e-7
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(n + 1)
                        if binom_pmf(i, n, p) <= pk * tol))


def wilson_ci(w, n, z=1.959963984540054):
    if n == 0:
        return (float("nan"), float("nan"))
    p = w / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, center + half)


def summarize(bets):
    """bets: list of dicts with keys season, outcome in {W,L,P}."""
    w = sum(1 for b in bets if b["outcome"] == "W")
    l = sum(1 for b in bets if b["outcome"] == "L")
    p = sum(1 for b in bets if b["outcome"] == "P")
    n = len(bets)
    dec = w + l
    hit = w / dec if dec else float("nan")
    roi = (w * WIN_UNITS - l * 1.0) / n if n else float("nan")
    lo, hi = wilson_ci(w, dec)
    p_be = stats.binomtest(w, dec, BREAKEVEN).pvalue if dec else float("nan")
    p_half = stats.binomtest(w, dec, 0.5).pvalue if dec else float("nan")

    def era(a, b):
        sub = [x for x in bets if a <= x["season"] <= b]
        ew = sum(1 for x in sub if x["outcome"] == "W")
        el = sum(1 for x in sub if x["outcome"] == "L")
        ep = sum(1 for x in sub if x["outcome"] == "P")
        ed = ew + el
        ehit = ew / ed if ed else float("nan")
        eroi = (ew * WIN_UNITS - el) / len(sub) if sub else float("nan")
        return f"{a}-{b}: {ew}-{el}-{ep}, hit {ehit:.3f}, ROI {eroi:+.3f}"

    return {
        "n": n, "wins": w, "losses": l, "pushes": p,
        "hit": round(hit, 4), "roi": round(roi, 4),
        "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
        "p_vs_breakeven": round(p_be, 4), "p_vs_half": round(p_half, 4),
        "era_split": era(*ERA1) + " | " + era(*ERA2),
    }


def run():
    df = load()
    winners_by_season = {s: division_winners(df, s) for s in range(2001, 2025)}
    playoffs_by_season = {s: playoff_teams(df, s) for s in range(2001, 2025)}

    reg = df[(df["game_type"] == "REG") & df["season"].isin(BET_SEASONS)
             & df["result"].notna() & df["spread_line"].notna()].copy()
    reg["week"] = reg["week"].astype(int)

    r1, r2, r3 = [], [], []
    for g in reg.itertuples():
        prior = g.season - 1
        champs = winners_by_season[prior]
        po = playoffs_by_season[prior]
        for side in ("home", "away"):
            team = g.home_team if side == "home" else g.away_team
            opp = g.away_team if side == "home" else g.home_team
            if team not in champs:
                continue
            team_spread = -g.spread_line if side == "home" else g.spread_line
            if not (1.0 <= team_spread <= 6.5):
                continue
            margin = g.result if side == "home" else -g.result
            adj = margin + team_spread
            outcome = "W" if adj > 0 else ("L" if adj < 0 else "P")
            bet = {"season": g.season, "week": g.week, "team": team,
                   "opp": opp, "spread": team_spread, "outcome": outcome}
            if g.week == 1:
                r2.append(bet)
                if opp not in po:
                    r1.append(bet)
            if 1 <= g.week <= 8:
                r3.append(bet)

    results = {}
    for rid, definition, bets in [
        ("R1", "Wk1: prior-season div winner +1..+6.5 vs opp that missed "
               "prior playoffs -> bet champ spread", r1),
        ("R2", "Wk1: prior-season div winner +1..+6.5 vs any opp -> bet "
               "champ spread", r2),
        ("R3", "Wks 1-8: prior-season div winner +1..+6.5 -> bet champ "
               "spread", r3),
    ]:
        s = summarize(bets)
        s["definition"] = definition
        results[rid] = s
        print(f"\n{rid}: {definition}")
        for k, v in s.items():
            if k != "definition":
                print(f"  {k}: {v}")

    print("\nR1 bet log:")
    for b in r1:
        print(f"  {b['season']} wk{b['week']} {b['team']} +{b['spread']} "
              f"vs {b['opp']}: {b['outcome']}")
    return results, r1, r2, r3


if __name__ == "__main__":
    run()

"""Pre-registered study: Week 1 big home favorites ("Jaguars -7" pattern).

Rules (grading at standard -110: win +0.9091u, loss -1u, push 0; seasons 2002-2025):
  R1: REG week 1, spread_line in [6.5, 7.5] -> bet HOME spread.
  R2: same filter -> bet AWAY spread (contrarian control).
  R3: REG week 1, spread_line > 0 (any home favorite) -> bet HOME spread.

Conventions: result = home_score - away_score; home covers iff result > spread_line;
push iff result == spread_line.
"""
import math
import json
import pandas as pd

DATA = "/home/user/NFL-bets/data/games.csv"
WIN_PAYOUT = 100 / 110  # -110


def binom_pmf(k, n, p):
    return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                    + k * math.log(p) + (n - k) * math.log(1 - p))


def binom_test_two_sided(k, n, p):
    """Exact two-sided binomial test (sum of outcomes with pmf <= pmf(k))."""
    if n == 0:
        return float("nan")
    pk = binom_pmf(k, n, p)
    tol = pk * 1e-7
    total = sum(pmf for i in range(n + 1)
                if (pmf := binom_pmf(i, n, p)) <= pk + tol)
    return min(1.0, total)


def wilson_ci(w, n, z=1.959963984540054):
    if n == 0:
        return (float("nan"), float("nan"))
    p = w / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, center + half)


def grade(df, side):
    """side='home' bets home spread, side='away' bets away spread."""
    res = df["result"]
    line = df["spread_line"]
    if side == "home":
        wins = (res > line).sum()
        losses = (res < line).sum()
    else:
        wins = (res < line).sum()
        losses = (res > line).sum()
    pushes = (res == line).sum()
    return int(wins), int(losses), int(pushes)


def summarize(df, side):
    w, l, p = grade(df, side)
    n = len(df)
    dec = w + l
    hit = w / dec if dec else float("nan")
    roi = (w * WIN_PAYOUT - l) / n if n else float("nan")
    lo, hi = wilson_ci(w, dec)
    p_be = binom_test_two_sided(w, dec, 0.5238)
    p_half = binom_test_two_sided(w, dec, 0.5)
    return dict(n=n, wins=w, losses=l, pushes=p, hit=hit, roi=roi,
                ci_lo=lo, ci_hi=hi, p_vs_breakeven=p_be, p_vs_half=p_half)


def era_split(df, side):
    out = []
    for label, lo, hi in [("2002-2013", 2002, 2013), ("2014-2025", 2014, 2025)]:
        sub = df[(df["season"] >= lo) & (df["season"] <= hi)]
        w, L, p = grade(sub, side)
        dec = w + L
        hit = w / dec if dec else float("nan")
        roi = (w * WIN_PAYOUT - L) / len(sub) if len(sub) else float("nan")
        out.append(f"{label}: {w}-{L}-{p}, hit {hit:.3f}, ROI {roi:+.3f}")
    return " | ".join(out)


def main():
    df = pd.read_csv(DATA, low_memory=False)
    df = df[(df["game_type"] == "REG")
            & (df["season"] >= 2002) & (df["season"] <= 2025)].copy()
    df["week"] = pd.to_numeric(df["week"])
    df = df.dropna(subset=["result", "spread_line"])
    w1 = df[df["week"] == 1]

    big = w1[(w1["spread_line"] >= 6.5) & (w1["spread_line"] <= 7.5)]
    anyfav = w1[w1["spread_line"] > 0]

    rules = [
        ("R1", "REG wk1, home favored 6.5-7.5 -> bet HOME spread", big, "home"),
        ("R2", "REG wk1, home favored 6.5-7.5 -> bet AWAY spread", big, "away"),
        ("R3", "REG wk1, home favorite any size -> bet HOME spread", anyfav, "home"),
    ]
    results = []
    for rid, desc, sub, side in rules:
        s = summarize(sub, side)
        s["rule_id"] = rid
        s["definition"] = desc
        s["era_split"] = era_split(sub, side)
        results.append(s)
        print(f"\n{rid}: {desc}")
        for k, v in s.items():
            print(f"  {k}: {v}")
    print("\nJSON:")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

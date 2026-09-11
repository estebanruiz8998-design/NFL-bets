"""Grade paper-trade game positions whose games are final.

Run:  python3 papertrade/grade.py

For every spread/total position whose game has a result, records the closing
line (nflverse keeps the final line), the outcome of the entered ticket at its
entry line/odds, units won or lost, and final closing-line value. Writes
papertrade/grades.json (consumed by build.py) and papertrade/verdict.md.
Futures cannot be graded until the season ends; they keep showing CLV only.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from nflbets import data  # noqa: E402
from papertrade.track import _is_home, clv_points  # noqa: E402

LEDGER = HERE / "ledger.json"
GRADES = HERE / "grades.json"
VERDICT = HERE / "verdict.md"
ARM_LETTER = {"slip": "A", "contra": "B", "unders": "U", "model": "M", "futures2": "F", "final": "S"}


def payout(odds: float) -> float:
    return 100.0 / -odds if odds < 0 else odds / 100.0


def grade_position(pos: dict, game) -> dict:
    spread = pos["type"] == "spread"
    home = _is_home(pos)
    closing = (-game.spread_line if home else game.spread_line) if spread else game.total_line
    rec = {
        "score": f"{game.away_team} {int(game.away_score)} @ {game.home_team} {int(game.home_score)}",
        "closing_line": float(closing),
    }
    if pos["status"] != "entered":
        rec["outcome"] = "no bet"
        rec["units"] = 0.0
        return rec
    if spread:
        margin = game.result if home else -game.result
        diff = margin + pos["entry_line"]
    else:
        diff = pos["entry_line"] - game.total if pos["side"] == "under" else game.total - pos["entry_line"]
    outcome = "win" if diff > 0 else "loss" if diff < 0 else "push"
    odds = pos.get("entry_odds", -110)
    units = pos["stake"] * (payout(odds) if outcome == "win" else -1.0 if outcome == "loss" else 0.0)
    rec.update(outcome=outcome, units=round(units, 4), final_clv=round(clv_points(pos, float(closing)), 1))
    return rec


def main() -> None:
    ledger = json.loads(LEDGER.read_text())
    games = data.load()
    g26 = games[games.season == 2026].set_index("game_id")
    grades, pending = {}, []
    for pos in ledger["positions"]:
        if pos["type"] not in ("spread", "total"):
            continue
        game = g26.loc[pos["game_id"]]
        if math.isnan(float(game.result)):
            pending.append(pos["id"])
            continue
        grades[pos["id"]] = grade_position(pos, game)
    week1 = g26[g26.week == 1]
    played = int(week1.result.notna().sum())
    meta = {"graded_on": str(date.today()), "week1_games_final": played, "week1_games": int(len(week1)),
            "pending_positions": pending, "final": played == len(week1)}
    GRADES.write_text(json.dumps({"meta": meta, "grades": grades}, indent=2) + "\n")
    VERDICT.write_text(render_verdict(ledger, grades, meta))
    print(f"[grade {meta['graded_on']}] {played}/{len(week1)} Week 1 games final; "
          f"{len(grades)} positions graded, {len(pending)} pending")
    for pid, g in grades.items():
        print(f"  {pid:>16}: {g['score']:<22} close={g['closing_line']:g} {g['outcome']:>6} "
              f"{g.get('units', 0):+.2f}u clv={g.get('final_clv', '—')}")


def render_verdict(ledger: dict, grades: dict, meta: dict) -> str:
    by_id = {p["id"]: p for p in ledger["positions"]}
    arms = defaultdict(lambda: {"entered": 0, "graded": 0, "w": 0, "l": 0, "p": 0, "units": 0.0, "clv": 0.0, "clv_stake": 0.0, "nobet": 0})
    for p in ledger["positions"]:
        if p["type"] not in ("spread", "total"):
            continue
        a = arms[p["arm"]]
        if p["status"] == "entered":
            a["entered"] += 1
        g = grades.get(p["id"])
        if not g:
            continue
        if g["outcome"] == "no bet":
            a["nobet"] += 1
            continue
        a["graded"] += 1
        a[{"win": "w", "loss": "l", "push": "p"}[g["outcome"]]] += 1
        a["units"] += g["units"]
        a["clv"] += p["stake"] * g["final_clv"]
        a["clv_stake"] += p["stake"]
    status = ("FINAL" if meta["final"] else
              f"PARTIAL — {meta['week1_games_final']} of {meta['week1_games']} Week 1 games final; "
              "final grading after Monday night, Sept 14")
    lines = [f"# Paper-trade verdict — Week 1 2026\n",
             f"*Graded {meta['graded_on']} · {status}*\n",
             "Every game position is graded at its entry line and odds against the actual result, and its final "
             "closing-line value (CLV) is measured against the nflverse closing line. Futures and win totals cannot be "
             "graded until the season ends and are excluded here (their price movement stays on the dashboard).\n",
             "## By arm\n",
             "| Arm | Thesis | Entered | Graded | W-L-P | Units | Final CLV (stake-wtd pts) | No-bet |",
             "|---|---|---|---|---|---|---|---|"]
    for arm, a in arms.items():
        clv = f"{a['clv'] / a['clv_stake']:+.2f}" if a["clv_stake"] else "—"
        thesis = ledger["arms"].get(arm, arm).split(" — ", 1)[-1]
        lines.append(f"| {ARM_LETTER.get(arm, arm)} | {thesis} | {a['entered']} | {a['graded']} | "
                     f"{a['w']}-{a['l']}-{a['p']} | {a['units']:+.2f}u | {clv} | {a['nobet']} |")
    tot = {k: sum(a[k] for a in arms.values()) for k in ("graded", "w", "l", "p", "units")}
    lines += ["", f"**All arms: {tot['w']}-{tot['l']}-{tot['p']}, {tot['units']:+.2f}u over {tot['graded']} graded tickets.**\n",
              "## Graded positions\n",
              "| Arm | Position | Entry | Close | Final CLV | Score | Outcome | Units |", "|---|---|---|---|---|---|---|---|"]
    for pid, g in grades.items():
        p = by_id[pid]
        entry = p.get("entry_line", "—")
        if p["type"] == "total" and entry != "—":
            entry = f"{'U' if p['side'] == 'under' else 'O'} {entry}"
        elif entry != "—":
            entry = f"{entry:+g}"
        close = g["closing_line"]
        close = f"{'U' if p['side'] == 'under' else 'O'} {close:g}" if p["type"] == "total" else f"{close:+g}"
        lines.append(f"| {ARM_LETTER.get(p['arm'], p['arm'])} | {p['bet']} | {entry} | {close} | "
                     f"{g.get('final_clv', '—')} | {g['score']} | {g['outcome']} | {g.get('units', 0):+.2f}u |")
    if meta["pending_positions"]:
        lines += ["", f"*Pending (game not yet final): {len(meta['pending_positions'])} positions — "
                      f"{', '.join(meta['pending_positions'])}.*"]
    lines += ["", "## How to read it\n",
              "- A win-loss record over a handful of tickets is noise; the number that matters is final CLV, and even that "
              "is a small-sample signal. The pre-season verdict — no component has demonstrated edge against closing lines — "
              "stands unless a full season of CLV says otherwise.",
              "- Arm S is the Sept 8 slip graded strictly: a ticket counts only if the reference feed met its price rule, "
              "so \"no bet\" rows are the discipline layer working, not missing data.",
              "- Reproduce: `python3 papertrade/track.py && python3 papertrade/grade.py && python3 papertrade/build.py`.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()

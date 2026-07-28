"""Paper-trade tracker: snapshot current market lines against the ledger's
entry prices and accumulate closing-line-value (CLV) history.

Run:  python3 papertrade/track.py [--date YYYY-MM-DD]

Each run appends one row per position to papertrade/snapshots.csv, auto-enters
conditional positions whose line condition is met at the reference book
(nflverse), and rewrites papertrade/state.json for the dashboard.

CLV conventions (positive = our entry beats the current market):
- spread/total: points of line value. For a points-getting or points-laying
  side, value = entry_line - current_line from the bettor's perspective
  (DEN +2.5 -> +1.5 line = +1.0 pt; SEA -3.5 -> -4.5 line = +1.0 pt).
  Overs gain when the line rises; unders when it falls.
- futures: change in raw implied win probability, percentage points
  (entry +200 = 33.3%; current +170 = 37.0% -> +3.7pp: the market moved
  toward our position after entry).
Futures quotes come from papertrade/futures_quotes.json (web-sourced at each
check-in); game lines come from the auto-refreshed nflverse dataset.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from nflbets import data  # noqa: E402

LEDGER = HERE / "ledger.json"
SNAPSHOTS = HERE / "snapshots.csv"
QUOTES = HERE / "futures_quotes.json"
STATE = HERE / "state.json"

SNAP_FIELDS = ["snap_date", "position_id", "status", "current_line", "current_odds",
               "clv_points", "clv_prob_pp"]


def implied(odds: float) -> float:
    return (-odds / (-odds + 100.0) if odds < 0 else 100.0 / (odds + 100.0)) * 100.0


def _is_home(pos: dict) -> bool:
    return pos["game_id"].split("_")[3] == pos["side"]


def clv_points(pos: dict, current: float) -> float:
    if pos["type"] == "spread":
        return pos["entry_line"] - current
    if pos["side"] == "over":
        return current - pos["entry_line"]
    return pos["entry_line"] - current


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=str(date.today()))
    args = ap.parse_args()
    snap_date = args.date

    ledger = json.loads(LEDGER.read_text())
    quotes = json.loads(QUOTES.read_text()) if QUOTES.exists() else {}
    games = data.load(refresh_hours=2)
    g26 = games[games.season == 2026].set_index("game_id")

    # latest futures quotes on or before snap_date
    quote_dates = sorted(d for d in quotes if d <= snap_date)
    latest_quotes = quotes[quote_dates[-1]] if quote_dates else {}

    rows, changed = [], False
    for pos in ledger["positions"]:
        row = {"snap_date": snap_date, "position_id": pos["id"], "status": pos["status"],
               "current_line": "", "current_odds": "", "clv_points": "", "clv_prob_pp": ""}
        if pos["type"] in ("futures", "wintotal"):
            cur = latest_quotes.get(pos["id"])
            if cur is not None:
                odds = cur["odds"] if isinstance(cur, dict) else cur
                row["current_odds"] = odds
                row["clv_prob_pp"] = round(implied(odds) - implied(pos["entry_odds"]), 2)
                if isinstance(cur, dict) and "line" in cur:
                    row["current_line"] = cur["line"]
                    row["clv_points"] = round(clv_points(pos, cur["line"]), 1)
        else:
            import math
            game = g26.loc[pos["game_id"]]
            spread, total = float(game.spread_line), float(game.total_line)
            # Books sometimes pull a line (e.g. pending injury news): record the
            # position with no current line rather than a NaN.
            ref = spread if pos["type"] == "spread" else total
            if math.isnan(ref):
                rows.append(row)
                continue
            # auto-enter conditionals when the reference line meets the rule
            if pos["status"] == "waiting":
                ok = eval(pos["condition"], {"__builtins__": {}}, {"spread_line": spread, "total_line": total})
                if ok:
                    pos["status"] = "entered"
                    pos["entry_date"] = snap_date
                    pos["entry_line"] = -spread if (pos["type"] == "spread" and _is_home(pos)) else (
                        spread if pos["type"] == "spread" else total)
                    changed = True
            if pos["type"] == "spread":
                cur = -spread if _is_home(pos) else spread
            else:
                cur = total
            row["status"] = pos["status"]
            row["current_line"] = cur
            if pos["status"] == "entered":
                row["clv_points"] = round(clv_points(pos, cur), 1)
        rows.append(row)

    write_header = not SNAPSHOTS.exists()
    with SNAPSHOTS.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SNAP_FIELDS)
        if write_header:
            w.writeheader()
        w.writerows(rows)
    if changed:
        LEDGER.write_text(json.dumps(ledger, indent=2) + "\n")

    # state.json for the dashboard: full history + latest per position
    hist: dict[str, list] = {}
    with SNAPSHOTS.open() as f:
        for r in csv.DictReader(f):
            hist.setdefault(r["position_id"], []).append(r)
    state = {"generated": snap_date, "ledger": ledger, "history": hist,
             "quote_dates": quote_dates}
    STATE.write_text(json.dumps(state, indent=2) + "\n")

    entered = [p for p in ledger["positions"] if p["status"] == "entered"]
    print(f"[snapshot {snap_date}] {len(rows)} positions tracked, "
          f"{len(entered)} entered, futures quotes from: "
          f"{quote_dates[-1] if quote_dates else 'none yet'}")
    for r in rows:
        if r["clv_points"] != "" or r["clv_prob_pp"] != "":
            clv = r["clv_points"] if r["clv_points"] != "" else r["clv_prob_pp"]
            cur = r["current_line"] if r["current_line"] != "" else r["current_odds"]
            print(f"  {r['position_id']:>14}: line={cur} CLV={clv:+.1f}")


if __name__ == "__main__":
    main()

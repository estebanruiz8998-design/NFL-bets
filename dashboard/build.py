"""Rebuild dashboard/index.html from the live model.

Run:  python dashboard/build.py
Injects fresh game data (current posted lines, model views, best bets) and
current Elo ratings into template.html. Re-run any time lines move; the
static texts (futures, week 1 card, backtest numbers) live in the template.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nflbets import data, strategy
from nflbets.config import Config
from nflbets.weekly import build_models

HERE = Path(__file__).resolve().parent


def game_rows(cfg: Config, games) -> list[dict]:
    elo, tot = build_models(cfg, games)
    rows = []
    for row in data.upcoming(games, int(games.season.max())).itertuples(index=False):
        _, pm, _ = elo.pregame(row.season, row.home_team, row.away_team, row.neutral,
                               row.home_rest, row.away_rest, row.playoff,
                               row.home_qb_change, row.away_qb_change)
        pt = tot.pregame(row.season, row.home_team, row.away_team)
        best, tier = strategy.best_bet(cfg, strategy.candidates(cfg, row, pm, pt))
        am, at = strategy.anchored(cfg, row, pm, pt)

        def ml(v):
            return None if (isinstance(v, float) and math.isnan(v)) else float(v)

        rows.append({
            "week": int(row.week), "date": str(row.gameday.date()),
            "away": row.away_team, "home": row.home_team,
            "spread": float(row.spread_line), "total": float(row.total_line),
            "hml": ml(row.home_moneyline), "aml": ml(row.away_moneyline),
            "modelMargin": round(am, 1), "modelTotal": round(at, 1),
            "rawEdge": round(pm - row.spread_line, 1),
            "rawTotalEdge": round(pt - row.total_line, 1),
            "bet": best.label() if best else "-", "tier": tier,
            "p": round(best.p_win, 3) if best else None,
            "ev": round(best.ev, 3) if best else None,
            "stake": round(100 * best.stake, 2) if best else 0,
            "neutral": bool(row.neutral),
        })
    return rows


def main() -> None:
    cfg = Config.load()
    games = data.load(refresh_hours=6)
    elo, _ = build_models(cfg, games)
    ratings = [{"team": t, "elo": round(r, 1)}
               for t, r in sorted(elo.ratings.items(), key=lambda kv: -kv[1])][:16]
    payload = {"generated": str(date.today()),
               "games": game_rows(cfg, games), "ratings": ratings}

    tpl = (HERE / "template.html").read_text()
    assert tpl.count("/*__DATA__*/") == 1, "template must contain one /*__DATA__*/ slot"
    out = tpl.replace("/*__DATA__*/", json.dumps(payload, separators=(",", ":")))
    (HERE / "index.html").write_text(out)
    n = len(payload["games"])
    strong = sum(1 for g in payload["games"] if g["tier"] == "STRONG")
    lean = sum(1 for g in payload["games"] if g["tier"] == "LEAN")
    print(f"built dashboard/index.html: {n} games, {strong} STRONG, {lean} LEAN")


if __name__ == "__main__":
    main()

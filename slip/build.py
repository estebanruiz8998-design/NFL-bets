"""Inject slip/week1.json into slip/template.html -> slip/index.html.

The JSON is the synthesized, adversarially-verified Week 1 slip. Kickoff
times come from the nflverse schedule (America/New_York) so the page can
count down and flag plays whose game has already started.

Run:  python3 slip/build.py
"""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Week 1 2026 kickoffs (ET, UTC-4), from nflverse gameday/gametime.
KICKOFFS = {
    "NE @ SEA": "2026-09-09T20:20:00-04:00",
    "SF @ LA": "2026-09-10T20:35:00-04:00",
    "ARI @ LAC": "2026-09-13T16:25:00-04:00",
    "ATL @ PIT": "2026-09-13T13:00:00-04:00",
    "BAL @ IND": "2026-09-13T13:00:00-04:00",
    "BUF @ HOU": "2026-09-13T13:00:00-04:00",
    "CHI @ CAR": "2026-09-13T13:00:00-04:00",
    "CLE @ JAX": "2026-09-13T13:00:00-04:00",
    "DAL @ NYG": "2026-09-13T20:20:00-04:00",
    "GB @ MIN": "2026-09-13T16:25:00-04:00",
    "MIA @ LV": "2026-09-13T16:25:00-04:00",
    "NO @ DET": "2026-09-13T13:00:00-04:00",
    "NYJ @ TEN": "2026-09-13T13:00:00-04:00",
    "TB @ CIN": "2026-09-13T13:00:00-04:00",
    "WAS @ PHI": "2026-09-13T16:25:00-04:00",
    "DEN @ KC": "2026-09-14T20:15:00-04:00",
}


def game_key(game: str) -> str | None:
    """Map free-text game labels ('Patriots @ Seahawks', 'SF vs LA (Melbourne)') to the schedule key."""
    g = game.upper()
    for key in KICKOFFS:
        away, home = key.split(" @ ")
        if away in g and home in g:
            return key
    return None


def git_serial() -> str:
    try:
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        h = "local"
    return f"{date.today().isoformat()} · {h}"


def main() -> None:
    slip = json.loads((HERE / "week1.json").read_text())
    for section in ("tomorrow", "week1"):
        for p in slip[section]:
            k = game_key(p["game"])
            p["kickoff_iso"] = KICKOFFS.get(k) if k else None
    slip["serial"] = git_serial()
    html = (HERE / "template.html").read_text().replace("/*__SLIP__*/null", json.dumps(slip))
    (HERE / "index.html").write_text(html)
    print(f"built {HERE / 'index.html'} ({len(slip['tomorrow'])} opener + {len(slip['week1'])} week-1 plays)")


if __name__ == "__main__":
    main()

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
    (HERE.parent / "week1-2026-final-slip.md").write_text(markdown(slip))
    print(f"built {HERE / 'index.html'} ({len(slip['tomorrow'])} opener + {len(slip['week1'])} week-1 plays)")


def _play(p: dict) -> str:
    return (
        f"### #{p['rank']} {p['game']} — {p['date']} {p.get('kickoff', '')}\n\n"
        f"**{p['bet']}** ({p['market']}) · {p['stake_units']}u · {p['tier']} · evidence {p['evidence_grade']}\n\n"
        f"- **Now:** {p['price_now']}\n"
        f"- **Only if:** {p['price_condition']}\n"
        f"- **Why:** {p['why']}\n"
        f"- **Risk:** {p['risk']}\n"
        f"- **Verification:** {p['verification']}\n"
    )


def markdown(slip: dict) -> str:
    total = sum(p["stake_units"] for p in slip["tomorrow"] + slip["week1"])
    parts = [
        "# Week 1 2026 — Final Bet Slip\n",
        f"*{slip['eyebrow']}*\n",
        f"> {slip['banner']}\n",
        f"**{slip['headline']}**\n",
        f"{slip['honesty_note']}\n",
        f"## Tomorrow — {slip['tomorrow_label']}\n",
        *[_play(p) for p in slip["tomorrow"]],
        f"## Rest of Week 1 — {slip['week1_label']}\n",
        *[_play(p) for p in slip["week1"]],
        "## Do not bet\n",
        "| Ticket | Why |\n|---|---|\n" + "\n".join(f"| ~~{a['bet']}~~ | {a['why']} |" for a in slip["do_not_bet"]) + "\n",
        "## Timing rules\n",
        "\n".join(f"{i}. {r}" for i, r in enumerate(slip["timing_rules"], 1)) + "\n",
        f"**Total exposure {total:g}u** (1u = 1% of bankroll). {slip['foot']}\n",
        f"*Serial: {slip['serial']}. Source: `slip/week1.json`; page: `slip/index.html`.* If it stops being fun: 1-800-GAMBLER.\n",
    ]
    return "\n".join(parts)


if __name__ == "__main__":
    main()

"""Load and normalize the nflverse games dataset.

Source: https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv
One row per game, 1999-present, including scores and betting market columns
(spread_line, total_line, moneylines, spread/total prices). For completed
seasons these are closing lines; for the upcoming season they are current
lines, refreshed upstream several times per day.

Conventions used throughout this package:
- ``result``      = home_score - away_score (home margin)
- ``spread_line`` = expected home margin (positive => home favored)
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pandas as pd

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "games.csv"

# Franchise relocations: carry ratings across the move.
FRANCHISE = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def refresh(path: Path = DATA_PATH, max_age_hours: float | None = None) -> Path:
    """Download games.csv (if missing, or older than max_age_hours)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and max_age_hours is not None:
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if age_h <= max_age_hours:
            return path
    if path.exists() and max_age_hours is None:
        return path
    tmp = path.with_suffix(".tmp")
    subprocess.run(
        ["curl", "-sS", "--max-time", "120", "-o", str(tmp), GAMES_URL],
        check=True,
    )
    # Sanity check before replacing the previous copy.
    head = tmp.open().readline()
    if "game_id" not in head or "spread_line" not in head:
        raise RuntimeError(f"downloaded games.csv looks wrong: {head[:120]!r}")
    tmp.replace(path)
    return path


def load(path: Path = DATA_PATH, refresh_hours: float | None = None) -> pd.DataFrame:
    """Load games, normalized and sorted chronologically."""
    refresh(path, max_age_hours=refresh_hours)
    df = pd.read_csv(path, low_memory=False)
    for col in ("away_team", "home_team"):
        df[col] = df[col].replace(FRANCHISE)
    df["gameday"] = pd.to_datetime(df["gameday"])
    df["neutral"] = df["location"].astype(str).str.lower().eq("neutral")
    df["playoff"] = df["game_type"].ne("REG")
    df = df.sort_values(["gameday", "game_id"]).reset_index(drop=True)
    df = _add_qb_change(df)
    return df


def _add_qb_change(df: pd.DataFrame) -> pd.DataFrame:
    """Flag games where a team starts a different QB than in its previous game.

    Starters are known before kickoff, so this is a legitimate pregame feature.
    First game on record for a team counts as no change.
    """
    long = pd.concat([
        df.reset_index()[["index", "game_id", "home_team", "home_qb_name"]]
        .rename(columns={"home_team": "team", "home_qb_name": "qb"}),
        df.reset_index()[["index", "game_id", "away_team", "away_qb_name"]]
        .rename(columns={"away_team": "team", "away_qb_name": "qb"}),
    ]).sort_values("index", kind="stable")
    long["prev_qb"] = long.groupby("team")["qb"].shift(1)
    long["qb_change"] = long.prev_qb.notna() & long.qb.notna() & (long.qb != long.prev_qb)

    key = long.set_index(["game_id", "team"]).qb_change
    df["home_qb_change"] = [
        bool(key.get((g, t), False)) for g, t in zip(df.game_id, df.home_team)
    ]
    df["away_qb_change"] = [
        bool(key.get((g, t), False)) for g, t in zip(df.game_id, df.away_team)
    ]
    return df


def completed(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["result"].notna()]


def upcoming(df: pd.DataFrame, season: int) -> pd.DataFrame:
    """Games in `season` not yet played, with at least a spread posted."""
    m = (df["season"] == season) & df["result"].isna() & df["spread_line"].notna()
    return df[m]

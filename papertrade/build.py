"""Rebuild papertrade/index.html from state.json (run track.py first)."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    state = json.loads((HERE / "state.json").read_text())
    grades_path = HERE / "grades.json"
    if grades_path.exists():
        g = json.loads(grades_path.read_text())
        state["grades"], state["grades_meta"] = g["grades"], g["meta"]
    tpl = (HERE / "template.html").read_text()
    assert tpl.count("/*__STATE__*/") == 1
    (HERE / "index.html").write_text(
        tpl.replace("/*__STATE__*/", json.dumps(state, separators=(",", ":")))
    )
    print(f"built papertrade/index.html (snapshot {state['generated']})")


if __name__ == "__main__":
    main()

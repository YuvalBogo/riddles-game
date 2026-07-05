"""Loading riddle content and the random reaction messages."""

from __future__ import annotations

import json
from pathlib import Path

from .riddle import Riddle, from_dict

_CONTENT_DIR = Path(__file__).parent / "content"

LEVELS = ["easy", "medium", "hard"]

# Hints available to the player per level.
HINTS_PER_LEVEL = {"easy": 3, "medium": 2, "hard": 2}

# One-line thematic name shown when the player enters each level.
LEVEL_NAMES = {
    "easy": "The Outer Halls",
    "medium": "The Inner Vault",
    "hard": "The Sphinx's Chamber",
}


def load_riddles(path: Path | None = None) -> dict[str, list[Riddle]]:
    """Load riddles grouped by difficulty from the JSON content file."""
    path = path or _CONTENT_DIR / "riddles.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        level: [from_dict(item, level) for item in raw.get(level, [])]
        for level in LEVELS
    }


# --- Leaderboard (Top 5) ---------------------------------------------------

LEADERBOARD_SIZE = 5
_LEADERBOARD_FILE = _CONTENT_DIR / "leaderboard.json"


def load_leaderboard() -> list[tuple[str, int]]:
    """Return the current Top 5 as ``(name, score)`` sorted high → low."""
    try:
        raw = json.loads(_LEADERBOARD_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    entries = [(str(e["name"]), int(e["score"])) for e in raw]
    entries.sort(key=lambda e: e[1], reverse=True)
    return entries[:LEADERBOARD_SIZE]


def _save_leaderboard(entries: list[tuple[str, int]]) -> None:
    entries = sorted(entries, key=lambda e: e[1], reverse=True)[:LEADERBOARD_SIZE]
    payload = [{"name": name, "score": score} for name, score in entries]
    _LEADERBOARD_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def qualifies(score: int) -> bool:
    """Whether ``score`` earns a place in the Top 5."""
    if score <= 0:
        return False
    board = load_leaderboard()
    if len(board) < LEADERBOARD_SIZE:
        return True
    return score > min(s for _, s in board)


def add_score(name: str, score: int) -> list[tuple[str, int]]:
    """Insert a score, trim to Top 5, persist, and return the new board."""
    board = load_leaderboard()
    board.append((name, score))
    _save_leaderboard(board)
    return load_leaderboard()


PRAISE = [
    "Well done!",
    "You nailed it!",
    "Congratulations, that's correct!",
    "I knew you could do it!",
    "Excellent work!",
    "Brilliant — you make it look easy!",
    "Bravo! Truly impressive.",
    "Sharp as ever!",
    "That's the spirit — spot on!",
]

TAUNT = [
    "Nope.",
    "Wrong answer.",
    "Not quite — think it through.",
    "Don't be impulsive, take a breath.",
    "Try to picture the solution.",
    "Close, but no.",
]

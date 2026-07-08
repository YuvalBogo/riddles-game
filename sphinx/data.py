"""Loading riddle content and the random reaction messages."""

from __future__ import annotations

import json
import os
import sys
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


def _user_data_dir() -> Path:
    """The per-user directory for save data, by platform convention.

    Scores cannot live beside the code. A frozen one-file build unpacks itself
    into a temporary directory that the OS deletes on exit, and an installed
    copy may sit somewhere read-only such as ``C:\\Program Files``. Either way
    the package directory is the wrong place to write.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or "~/AppData/Roaming"
    elif sys.platform == "darwin":
        base = "~/Library/Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or "~/.local/share"
    return Path(base).expanduser() / "Sphinx"


_LEADERBOARD_FILE = _user_data_dir() / "leaderboard.json"

# Where scores lived before they moved out of the package. Read-only: an older
# board is still honored, and the next save rewrites it to the new location.
_LEGACY_LEADERBOARD_FILE = _CONTENT_DIR / "leaderboard.json"


def _read_board(path: Path) -> list[tuple[str, int]] | None:
    """Parse a leaderboard file, or ``None`` if it is missing or unreadable."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [(str(e["name"]), int(e["score"])) for e in raw]
    except (OSError, json.JSONDecodeError, TypeError, KeyError, ValueError):
        return None


def load_leaderboard() -> list[tuple[str, int]]:
    """Return the current Top 5 as ``(name, score)`` sorted high → low."""
    entries = _read_board(_LEADERBOARD_FILE)
    if entries is None:
        entries = _read_board(_LEGACY_LEADERBOARD_FILE) or []
    entries.sort(key=lambda e: e[1], reverse=True)
    return entries[:LEADERBOARD_SIZE]


def _save_leaderboard(entries: list[tuple[str, int]]) -> None:
    entries = sorted(entries, key=lambda e: e[1], reverse=True)[:LEADERBOARD_SIZE]
    payload = [{"name": name, "score": score} for name, score in entries]
    try:
        _LEADERBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LEADERBOARD_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        # A read-only or missing home directory must not end the player's run
        # on the very screen that celebrates it — just don't persist the score.
        pass


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
    "Look at THAT!",
    "You're on fire!",
    "GOD DAYUMN, you are good at this!",
    "mmm, yes, very good.",
    "MACHINEEE!"
]

TAUNT = [
    "Nope.",
    "Not quite — think it through.",
    "Don't be impulsive, take a breath.",
    "Try to picture the solution. BE the solution.",
    "Close, but no.",
    "How do you sleep at night, knowing that was wrong?",
    "BBZZZT! Wrong answer.",
    "HAHA! loser."
]

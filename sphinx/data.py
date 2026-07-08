"""Loading riddle content and the random reaction messages."""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

from .riddle import Riddle, from_dict

_CONTENT_DIR = Path(__file__).parent / "content"

LEVELS = ["easy", "medium", "hard"]

# Riddles drawn per level for a real run. The pool is much larger than this, so
# the tomb is never the same twice — which is the point, and also the story.
RIDDLES_PER_LEVEL = 5

# Hints available to the player per level.
HINTS_PER_LEVEL = {"easy": 3, "medium": 2, "hard": 2}

# One-line thematic name shown when the player enters each level.
LEVEL_NAMES = {
    "easy": "The Outer Halls",
    "medium": "The Inner Vault",
    "hard": "The Sphinx's Chamber",
}


def load_riddles(path: Path | None = None) -> dict[str, list[Riddle]]:
    """Load the whole riddle pool, grouped by difficulty.

    This is every riddle in the content file. Practice Mode drills the full
    pool; a real run draws a subset from it — see :func:`draw_run`.
    """
    path = path or _CONTENT_DIR / "riddles.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        level: [from_dict(item, level) for item in raw.get(level, [])]
        for level in LEVELS
    }


# --- Drawing a run ---------------------------------------------------------

def _draw_level(pool: list[Riddle], count: int, seen: set[str]) -> list[Riddle]:
    """Draw ``count`` riddles from ``pool``, preferring ones not in ``seen``.

    Unseen riddles are exhausted first, so consecutive runs do not repeat until
    the pool runs dry. The draw also guarantees at least one non-classic riddle
    (a cipher, sequence, logic or ASCII-art one) whenever the pool holds one:
    without that, a pool that is mostly plain questions will now and then serve
    a run of nothing but plain questions, which is the dullest thing it can do.
    """
    if count >= len(pool):
        return random.sample(pool, len(pool))

    unseen = [r for r in pool if r.rid not in seen]
    # Fall back to the seen ones only once the unseen are used up.
    ordered = random.sample(unseen, len(unseen))
    if len(ordered) < count:
        rest = [r for r in pool if r.rid in seen]
        ordered += random.sample(rest, len(rest))
    drawn = ordered[:count]

    special = [r for r in pool if type(r) is not Riddle]
    if special and all(type(r) is Riddle for r in drawn):
        # Swap the last plain riddle for a special one, preferring an unseen.
        pick = [r for r in special if r.rid not in seen] or special
        drawn[-1] = random.choice(pick)
    random.shuffle(drawn)
    return drawn


def draw_run(pool: dict[str, list[Riddle]] | None = None,
             count: int = RIDDLES_PER_LEVEL) -> dict[str, list[Riddle]]:
    """Draw one run's riddles: ``count`` per level, avoiding recent repeats.

    The drawn ids are remembered, so the next run reaches for riddles this one
    did not use. When a level has no unseen riddles left it starts over — the
    memory is reset for that level alone, not the whole tomb.
    """
    pool = pool if pool is not None else load_riddles()
    seen = _load_seen()
    drawn: dict[str, list[Riddle]] = {}

    for level in LEVELS:
        level_pool = pool.get(level, [])
        if not level_pool:
            drawn[level] = []
            continue
        record = seen.get(level, {"seen": set(), "last": set()})
        remembered = record["seen"]
        if len(level_pool) - len(remembered) < count:
            # Exhausted. Start over, but keep the previous run's riddles out of
            # this one — a reset must not hand back what was just played.
            remembered = set(record["last"])
        drawn[level] = _draw_level(level_pool, count, remembered)
        ids = {r.rid for r in drawn[level] if r.rid}
        seen[level] = {"seen": remembered | ids, "last": ids}

    _save_seen(seen)
    return drawn


def run_max_exp(drawn: dict[str, list[Riddle]]) -> int:
    """The most XP a flawless run through ``drawn`` could earn: every riddle
    solved, every streak bonus collected, nothing spent.

    Solving pays a flat ``BASE_XP`` — ``Player.solve`` never sees the riddle, so
    the ``exp`` field in the content file is not read by anything. The ceiling
    therefore depends only on how many riddles a run holds, and the run length
    is what a percentage makes comparable: a 15-riddle run tops out at 332 XP
    where the old whole-pool run topped out at 2342.
    """
    from .player import BASE_XP, streak_bonus   # local: player imports none of this

    n = sum(len(drawn.get(level, [])) for level in LEVELS)
    return n * BASE_XP + sum(streak_bonus(i) for i in range(1, n + 1))


def score_pct(exp: int, drawn: dict[str, list[Riddle]]) -> float:
    """A run's score as a percentage of what that run could have earned."""
    ceiling = run_max_exp(drawn)
    if ceiling <= 0:
        return 0.0
    return round(100.0 * max(0, exp) / ceiling, 1)


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

# Which riddles this player has already been shown, so a run can avoid them.
# Per level: "seen" is everything drawn since the pool was last exhausted, and
# "last" is only the previous run's draw. When the pool runs dry the memory is
# wiped back to "last" rather than to nothing — otherwise the run immediately
# after a reset could re-draw the riddles of the run just finished, which is
# precisely the repetition this is all here to prevent.
_SEEN_FILE = _user_data_dir() / "seen.json"


def _load_seen() -> dict[str, dict[str, set[str]]]:
    """Riddle ids drawn before, per level. Empty when unreadable — forgetting is
    harmless, and a corrupt file must never stop someone playing."""
    try:
        raw = json.loads(_SEEN_FILE.read_text(encoding="utf-8"))
        return {
            lvl: {"seen": set(map(str, rec.get("seen", []))),
                  "last": set(map(str, rec.get("last", [])))}
            for lvl, rec in raw.items()
            if lvl in LEVELS and isinstance(rec, dict)
        }
    except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return {}


def _save_seen(seen: dict[str, dict[str, set[str]]]) -> None:
    payload = {lvl: {"seen": sorted(rec["seen"]), "last": sorted(rec["last"])}
               for lvl, rec in seen.items()}
    try:
        _SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SEEN_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass    # a read-only home means repeats, not a crash


# Scores were raw XP until 2.8.0, when a run stopped covering the whole pool.
# A 45-riddle run and a 15-riddle one are not on the same scale — the streak
# bonus grows with every consecutive answer, so it dominates a long run — and an
# old score of 982 would have been unbeatable against the new ceiling of 332.
# This was the old ceiling: 45 riddles at BASE_XP, plus a perfect streak.
_LEGACY_MAX_EXP = 45 * 10 + sum(2 * (i - 2) for i in range(3, 46))   # 2342


def _read_board(path: Path) -> list[tuple[str, float]] | None:
    """Parse a leaderboard file into ``(name, percent)``.

    Entries carrying ``pct`` are current. Entries carrying ``score`` are raw XP
    from an older release and are converted against the run they were set on.
    ``None`` when the file is missing or unreadable.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        board = []
        for e in raw:
            name = str(e["name"])
            if "pct" in e:
                board.append((name, round(float(e["pct"]), 1)))
            else:
                pct = 100.0 * int(e["score"]) / _LEGACY_MAX_EXP
                board.append((name, round(pct, 1)))
        return board
    except (OSError, json.JSONDecodeError, TypeError, KeyError, ValueError):
        return None


def load_leaderboard() -> list[tuple[str, float]]:
    """Return the current Top 5 as ``(name, percent)`` sorted high → low."""
    entries = _read_board(_LEADERBOARD_FILE)
    if entries is None:
        entries = _read_board(_LEGACY_LEADERBOARD_FILE) or []
    entries.sort(key=lambda e: e[1], reverse=True)
    return entries[:LEADERBOARD_SIZE]


def _save_leaderboard(entries: list[tuple[str, float]]) -> None:
    entries = sorted(entries, key=lambda e: e[1], reverse=True)[:LEADERBOARD_SIZE]
    payload = [{"name": name, "pct": pct} for name, pct in entries]
    try:
        _LEADERBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LEADERBOARD_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        # A read-only or missing home directory must not end the player's run
        # on the very screen that celebrates it — just don't persist the score.
        pass


def qualifies(pct: float) -> bool:
    """Whether a score of ``pct`` percent earns a place in the Top 5."""
    if pct <= 0:
        return False
    board = load_leaderboard()
    if len(board) < LEADERBOARD_SIZE:
        return True
    return pct > min(s for _, s in board)


def add_score(name: str, pct: float) -> list[tuple[str, float]]:
    """Insert a score, trim to Top 5, persist, and return the new board."""
    board = load_leaderboard()
    board.append((name, round(float(pct), 1)))
    _save_leaderboard(board)
    return load_leaderboard()


# The sphinx speaking. It is old, it is not in a hurry, and it has heard every
# answer before — including yours. 
PRAISE = [
    "Yes. That one was easy. They are all easy, at first.",
    "Correct. The stone remembers you now.",
    "You see it. Good. Keep seeing.",
    "Hm. Most do not get that far.",
    "Right — though you took your time about it.",
    "So. You can think. We will find out how well.",
    "That is the answer. It was always the answer.",
    "Good. The next one is not like that one.",
    "You are quicker than the last. He is still here, somewhere.",
    "Correct. Do not let it go to your head; there is not much room.",
    "Yes. I am almost disappointed.",
    "Well answered. I will make the next one worse.",
    # Something the sphinx would never say - Easter Egg
    "MACHINEEE!",
]

TAUNT = [
    "No.",
    "Wrong. Sit with it — you have time. I have more.",
    "The stone does not move for that answer.",
    "No. Say it slower, in your head, before your mouth.",
    "Close. Close is nothing, down here.",
    "That is not it. Try being cleverer.",
    "Wrong. Four thousand years, and still nobody listens to the question.",
    "No. Breathe. The dark is patient, and so am I.",
    "You guessed. I can hear it when you guess.",
    "Wrong — and you knew it before you finished saying it.",
]

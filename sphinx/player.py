"""The Player: lives, experience and running statistics.

This is the completed version of the ``User`` class from the original
project — the one that trailed off at ``def`` with a bare colon.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

# EXP thresholds → cosmetic titles (ascending). Computed from final EXP;
# no save file is kept.
_TITLES = [
    (0, "Novice Seeker"),
    (40, "Apprentice"),
    (90, "Adept"),
    (150, "Riddle Master"),
    (220, "Sphinx Whisperer"),
]

# Base experience for any correct answer (real runs only).
BASE_XP = 10

# Skipping in a real run costs this much, drawn from the same XP pool.
SKIP_COST = 65

# Revealing a hint in a real run costs this much, from the same XP pool.
HINT_COST = 65

# Streak bonus kicks in from the 3rd consecutive correct answer and grows
# by +2 for each further one: 3rd → +2, 4th → +4, 5th → +6, ...
def _streak_bonus(streak: int) -> int:
    return (streak - 2) * 2 if streak >= 3 else 0


@dataclass
class Player:
    name: str = "Player"
    lives: int = 3
    max_lives: int = 3
    exp: int = 0
    solved: int = 0
    mistakes: int = 0
    hints_used: int = 0
    skipped: int = 0
    streak: int = 0
    longest_streak: int = 0
    _start: float = field(default_factory=time.monotonic, init=False)

    # -- lives --------------------------------------------------------------

    @property
    def alive(self) -> bool:
        return self.lives > 0

    def lose_life(self) -> None:
        self.lives = max(0, self.lives - 1)
        self.mistakes += 1
        self.streak = 0

    def gain_life(self) -> bool:
        """Grant an extra life if below the cap. Returns True if granted."""
        if self.lives < self.max_lives:
            self.lives += 1
            return True
        return False

    # -- scoring ------------------------------------------------------------

    def solve(self, award_xp: bool = True) -> tuple[int, int]:
        """Record a solved riddle.

        Returns ``(base, bonus)`` XP awarded. With ``award_xp=False``
        (Practice Mode) the solve is counted but no XP is granted.
        """
        self.solved += 1
        self.streak += 1
        self.longest_streak = max(self.longest_streak, self.streak)
        if not award_xp:
            return (0, 0)
        base = BASE_XP
        bonus = _streak_bonus(self.streak)
        self.exp += base + bonus
        return (base, bonus)

    def use_hint(self, cost: int = 0) -> None:
        self.hints_used += 1
        if cost:
            self.exp = max(0, self.exp - cost)

    def can_hint(self) -> bool:
        """Whether the player can afford a real-run hint (costs HINT_COST)."""
        return self.exp >= HINT_COST

    def can_skip(self) -> bool:
        """Whether the player can afford a real-run skip (costs SKIP_COST)."""
        return self.exp >= SKIP_COST

    def skip(self, cost: int = 0) -> None:
        self.skipped += 1
        self.streak = 0
        if cost:
            self.exp = max(0, self.exp - cost)

    # -- titles -------------------------------------------------------------

    @property
    def title(self) -> str:
        earned = _TITLES[0][1]
        for threshold, name in _TITLES:
            if self.exp >= threshold:
                earned = name
        return earned

    # -- reporting ----------------------------------------------------------

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start

    def elapsed_str(self) -> str:
        secs = int(self.elapsed)
        return f"{secs // 60}m {secs % 60}s"

    def stats(self) -> dict[str, str | int]:
        return {
            "Name": self.name,
            "Title": self.title,
            "EXP earned": self.exp,
            "Riddles solved": self.solved,
            "Longest streak": self.longest_streak,
            "Mistakes": self.mistakes,
            "Hints used": self.hints_used,
            "Skipped": self.skipped,
            "Time played": self.elapsed_str(),
        }

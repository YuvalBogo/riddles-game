"""Pure game-flow state for the tkinter GUI front-end (no tkinter here).

This drives the *unmodified* engine (``Player``, ``Riddle``, ``data``) and
turns a run into an ordered list of frozen ``Card`` snapshots the GUI can
render and browse. Keeping it tkinter-free means the whole flow — scoring,
lives, streaks, level progression, win/lose — is testable headlessly.

The GUI (``gui.py``) owns rendering, animation and input; this module owns
"what happens next".
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import data
from .player import HINT_COST, Player, SKIP_COST
from .riddle import AsciiArtRiddle, CipherRiddle, SequenceRiddle

# Inner text width (characters) for a card — the GUI renders cards as
# monospace box-drawing blocks of this content width. Wide enough that the
# HUD progress bar (one tile per riddle, up to ~15 a level) fits on one row,
# and so riddles wrap to fewer lines (which keeps the deck short).
CONTENT_W = 70


# --- Text helpers ----------------------------------------------------------

def wrap(text: str, width: int = CONTENT_W) -> list[str]:
    """Greedy word-wrap a single paragraph to ``width`` columns."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def riddle_body(riddle, width: int = CONTENT_W) -> list[str]:
    """Build a riddle's display lines as data, reading type-specific
    attributes directly (never calling the terminal print helpers).

    Mirrors the terminal presentation: ASCII art above the prompt, and
    cipher/sequence extras below it. Logic-riddle constraints are *not*
    shown — they live in the hint, exactly as in the terminal version.
    """
    lines: list[str] = []
    if isinstance(riddle, AsciiArtRiddle):
        lines.extend(riddle.art.splitlines())
        lines.append("")
    for paragraph in riddle.prompt.splitlines():
        lines.extend(wrap(paragraph, width) or [""])
    if isinstance(riddle, CipherRiddle):
        lines.append("")
        lines.extend(wrap("Encoded: " + riddle.encoded, width))
        family = "Atbash" if riddle.cipher_type == "atbash" else "Caesar"
        lines.append(f"Cipher: {family} — decode it!")
    if isinstance(riddle, SequenceRiddle):
        lines.append("")
        shown = ", ".join(str(x) for x in riddle.sequence) + ", ___"
        lines.extend(wrap(shown, width))
    return lines


# --- Card snapshot ---------------------------------------------------------

@dataclass
class Card:
    """A frozen snapshot of one riddle encountered this run."""

    title: str
    level: str
    body: list[str]
    hints: list[str] = field(default_factory=list)
    answer: str | None = None
    result: str = "pending"  # pending | correct | wrong | skipped


# --- Run state machine -----------------------------------------------------

class RunState:
    """Drives a run as a sequence of cards.

    ``mode="real"``     — continuous Easy → Medium → Hard, XP + streak,
                          skips cost SKIP_COST, flawless-level life bonus.
    ``mode="practice"`` — a single chosen level, no XP, free skips, and a
                          finish once that level is cleared.
    """

    def __init__(
        self,
        riddles: dict,
        player: Player | None = None,
        mode: str = "real",
        practice_level: str | None = None,
    ):
        self.riddles = riddles
        self.player = player or Player(name="Player")
        self.mode = mode
        self.level_index = (
            data.LEVELS.index(practice_level)
            if mode == "practice" and practice_level
            else 0
        )
        self.order: list = []
        self.pos = 0
        self.hints_left = 0
        self._mistakes_at_level = 0
        self.cards: list[Card] = []
        self.finished = False
        self.outcome: str | None = None  # "win" | "dead"
        self._load_level()
        self._present()

    # -- level / riddle bookkeeping ----------------------------------------

    @property
    def level(self) -> str:
        return data.LEVELS[self.level_index]

    def _load_level(self) -> None:
        self.order = list(self.riddles[self.level])
        random.shuffle(self.order)
        self.hints_left = data.HINTS_PER_LEVEL[self.level]
        self._mistakes_at_level = self.player.mistakes
        self.pos = 0

    def current_riddle(self):
        return self.order[self.pos]

    def _present(self) -> None:
        riddle = self.current_riddle()
        title = f"{self.level.upper()} · Riddle {self.pos + 1}/{len(self.order)}"
        self.cards.append(
            Card(title=title, level=self.level, body=riddle_body(riddle))
        )

    def live_index(self) -> int:
        return len(self.cards) - 1

    def live_card(self) -> Card:
        return self.cards[self.live_index()]

    def progress(self) -> tuple[int, int]:
        """(riddles completed in the current level, total in the level)."""
        return (self.pos, len(self.order))

    # -- actions ------------------------------------------------------------

    def submit(self, answer: str) -> dict:
        """Resolve the current riddle against ``answer`` (does not advance)."""
        if self.finished:
            return {"result": "none"}
        card = self.live_card()
        if card.result != "pending":
            return {"result": "none"}
        guess = answer.strip()
        if not guess:
            return {"result": "invalid"}

        riddle = self.current_riddle()
        if riddle.check(guess):
            base, bonus = self.player.solve(award_xp=(self.mode == "real"))
            card.answer = guess
            card.result = "correct"
            return {"result": "correct", "base": base, "bonus": bonus,
                    "square": self.pos}

        # Wrong: costs a life and breaks the streak.
        self.player.lose_life()
        card.answer = guess
        if not self.player.alive:
            card.result = "wrong"
            self.finished = True
            self.outcome = "dead"
            return {"result": "wrong", "dead": True, "lost_index": self.player.lives}
        return {"result": "wrong", "dead": False, "lost_index": self.player.lives}

    def skip(self) -> dict:
        """Skip the current riddle. Real: costs SKIP_COST XP. Practice: free."""
        if self.finished:
            return {"ok": False, "reason": "finished"}
        card = self.live_card()
        if card.result != "pending":
            return {"ok": False, "reason": "not_current"}
        if self.mode == "real":
            if not self.player.can_skip():
                return {"ok": False, "reason": "poor",
                        "need": SKIP_COST, "have": self.player.exp}
            self.player.skip(cost=SKIP_COST)
        else:
            self.player.skip()  # free in Practice Mode
        card.result = "skipped"
        return {"ok": True, "square": self.pos}

    def use_hint(self) -> dict:
        if self.finished:
            return {"ok": False, "reason": "finished"}
        card = self.live_card()
        if card.result != "pending":
            return {"ok": False, "reason": "not_current"}
        if self.hints_left <= 0:
            return {"ok": False, "reason": "none"}
        # A hint in a real run is bought with XP (like a skip); Practice Mode
        # hints stay free. Refuse if the player can't cover the cost.
        if self.mode == "real" and not self.player.can_hint():
            return {"ok": False, "reason": "poor",
                    "need": HINT_COST, "have": self.player.exp}
        cost = HINT_COST if self.mode == "real" else 0
        self.hints_left -= 1
        self.player.use_hint(cost=cost)
        text = self.current_riddle().get_hint()
        card.hints.extend(text.splitlines())
        return {"ok": True, "hints_left": self.hints_left, "cost": cost}

    def advance(self) -> dict:
        """Move to the next riddle / level / end. Appends the next card."""
        if self.finished:
            return {"kind": "end"}
        self.pos += 1
        if self.pos < len(self.order):
            self._present()
            return {"kind": "card"}

        # Practice Mode drills a single level — clearing it ends the drill.
        if self.mode == "practice":
            self.finished = True
            self.outcome = "win"
            return {"kind": "win", "life_gained": False, "gain_index": None}

        # Level cleared — flawless bonus, then next level or win.
        life_gained = False
        if self.player.mistakes == self._mistakes_at_level:
            life_gained = self.player.gain_life()
        gain_index = self.player.lives - 1 if life_gained else None

        if self.level_index + 1 < len(data.LEVELS):
            self.level_index += 1
            self._load_level()
            self._present()
            return {"kind": "level_up", "level": self.level,
                    "life_gained": life_gained, "gain_index": gain_index}

        self.finished = True
        self.outcome = "win"
        return {"kind": "win", "life_gained": life_gained, "gain_index": gain_index}

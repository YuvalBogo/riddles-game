"""Riddle domain model.

``Riddle`` is the base class; ``LogicRiddle`` extends it with constraints,
mirroring the original inheritance design — now fully implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ui
from .ui import C


# A universal answer accepted for *any* riddle — a testing/demo backdoor so
# a run can be walked through without knowing every solution. Already in
# normalized form (lower-case, no surrounding punctuation).
MASTER_ANSWER = "banana"


def _normalize(text: str) -> str:
    """Lower-case, collapse whitespace and drop trailing punctuation."""
    cleaned = " ".join(str(text).lower().split())
    return cleaned.strip(" .!?,")


@dataclass
class Riddle:
    """A single riddle.

    Attributes:
        prompt: The question text shown to the player.
        answers: Every accepted answer (any one of them counts as correct).
        difficulty: "easy" | "medium" | "hard".
        hint: A single hint the player may request.
        exp: Experience points awarded for solving it.
        solved: Whether it has been solved this run.
    """

    prompt: str
    answers: list[str]
    difficulty: str = "easy"
    hint: str = "No hint available."
    exp: int = 10
    solved: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._accepted = {_normalize(a) for a in self.answers}

    # -- behaviour ----------------------------------------------------------

    def display(self, number: int | None = None) -> None:
        """Render the riddle to the terminal.

        Subclasses hook into this single display path via ``_pre_prompt``
        (rendered above the question, e.g. ASCII art) and ``_post_prompt``
        (rendered below it, e.g. clues or an encoded message) rather than
        building a parallel display flow.
        """
        label = f"{self.difficulty.upper()} RIDDLE"
        if number is not None:
            label += f" #{number}"
        print()
        print(ui.color(label, C.BOLD, C.MAGENTA))
        print(ui.rule())
        self._pre_prompt()
        ui.typewriter(self.prompt, 0.014, C.CYAN)
        self._post_prompt()

    def _pre_prompt(self) -> None:
        """Hook: render content above the prompt. Default: nothing."""

    def _post_prompt(self) -> None:
        """Hook: render content below the prompt. Default: nothing."""

    def check(self, guess: str) -> bool:
        """Return True if ``guess`` matches an accepted answer.

        The ``MASTER_ANSWER`` backdoor is accepted for every riddle to ease
        testing and demos.
        """
        normalized = _normalize(guess)
        correct = normalized == MASTER_ANSWER or normalized in self._accepted
        if correct:
            self.solved = True
        return correct

    def get_hint(self) -> str:
        return self.hint


@dataclass
class LogicRiddle(Riddle):
    """A logic riddle whose constraints/clues are held back until asked for.

    The clues are *not* shown alongside the prompt — that would spoil the
    riddle. They are folded into the hint, so they only appear when the
    player explicitly requests a hint.
    """

    constraints: list[str] = field(default_factory=list)

    def get_hint(self) -> str:
        text = self.hint
        if self.constraints:
            clues = "\n".join(f"      • {c}" for c in self.constraints)
            text = f"{text}\n    Clues to consider:\n{clues}"
        return text


# --- Cipher helpers --------------------------------------------------------

def _caesar(text: str, shift: int) -> str:
    out = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            out.append(ch)
    return "".join(out)


def _atbash(text: str) -> str:
    out = []
    for ch in text:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr((25 - (ord(ch) - base)) + base))
        else:
            out.append(ch)
    return "".join(out)


@dataclass
class CipherRiddle(Riddle):
    """The prompt is a Caesar- or Atbash-encoded message to decode."""

    cipher_type: str = "caesar"
    shift: int = 3
    plain: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.cipher_type == "atbash":
            self.encoded = _atbash(self.plain)
        else:
            self.encoded = _caesar(self.plain, self.shift)

    def _post_prompt(self) -> None:
        print()
        print(ui.color("  Encoded message:", C.YELLOW))
        print("    " + ui.color(self.encoded, C.BOLD, C.YELLOW))
        # Show the cipher family (needed to frame the puzzle) but hold back
        # the exact shift — that's a hint, revealed only on request.
        family = "Atbash" if self.cipher_type == "atbash" else "Caesar"
        print(ui.color(f"  Cipher type: {family} — decode it!", C.GREY))


@dataclass
class SequenceRiddle(Riddle):
    """A 'what comes next?' number or letter pattern."""

    sequence: list = field(default_factory=list)

    def _post_prompt(self) -> None:
        shown = ", ".join(str(x) for x in self.sequence)
        print()
        print("    " + ui.color(f"{shown}, ___", C.BOLD, C.CYAN))


@dataclass
class AsciiArtRiddle(Riddle):
    """A small ASCII-art image rendered above the prompt: 'what is this?'."""

    art: str = ""

    def _pre_prompt(self) -> None:
        for line in self.art.splitlines():
            print("    " + ui.color(line, C.GREEN))
        print()


def from_dict(data: dict, difficulty: str) -> Riddle:
    """Build the right Riddle subclass from a raw content dict."""
    kind = data.get("type", "classic")
    common = dict(
        prompt=data["prompt"],
        difficulty=difficulty,
        hint=data.get("hint", "No hint available."),
        exp=data.get("exp", 10),
    )
    if kind == "cipher":
        plain = data["plain"]
        answers = data.get("answers") or [plain]
        return CipherRiddle(
            answers=answers,
            cipher_type=data.get("cipher_type", "caesar"),
            shift=data.get("shift", 3),
            plain=plain,
            **common,
        )

    common["answers"] = data["answers"]
    if kind == "logic":
        return LogicRiddle(constraints=data.get("constraints", []), **common)
    if kind == "sequence":
        return SequenceRiddle(sequence=data.get("sequence", []), **common)
    if kind == "ascii_art":
        return AsciiArtRiddle(art=data.get("art", ""), **common)
    return Riddle(**common)

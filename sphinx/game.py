"""Game orchestration: the interactive loop that ties everything together.

Two modes share the same machinery:

* ``real``     — one continuous run, Easy → Medium → Hard, with lives, XP,
                 streaks and the leaderboard. Ends completely on zero lives.
* ``practice`` — drill a single chosen level. No XP, free skips, and the
                 results never touch the real-run stats or leaderboard.
"""

from __future__ import annotations

import random

from . import data, ui
from .player import Player, SKIP_COST
from .riddle import Riddle
from .ui import C


class QuitGame(Exception):
    """Raised to unwind out of the loop when the player quits or dies."""


class Game:
    def __init__(
        self,
        player: Player,
        riddles: dict[str, list[Riddle]],
        mode: str = "real",
        practice_level: str | None = None,
    ):
        self.player = player
        self.riddles = riddles
        self.mode = mode
        self.practice_level = practice_level

    # -- top-level flow -----------------------------------------------------

    def run(self) -> None:
        if self.mode == "practice":
            self._run_practice()
        else:
            self._run_real()

    def _run_real(self) -> None:
        """A full run: always starts at Easy, unlocking each level in turn."""
        try:
            for index, level in enumerate(data.LEVELS):
                if index > 0:
                    ui.level_descent(level)
                self._play_level(level)
            self._win_screen()
        except QuitGame:
            self._quit_screen()
        finally:
            self._show_stats()

    def _run_practice(self) -> None:
        """Drill a single level; nothing here counts toward a real run."""
        try:
            self._play_level(self.practice_level)
            print()
            ui.banner("Practice complete")
        except QuitGame:
            self._quit_screen()
        finally:
            self._show_stats()

    # -- one level ----------------------------------------------------------

    def _help_text(self) -> str:
        skip_note = "free" if self.mode == "practice" else f"−{SKIP_COST} XP"
        return (
            "Commands: type your answer, or "
            + ui.color("hint", C.YELLOW)
            + " / "
            + ui.color(f"skip ({skip_note})", C.YELLOW)
            + " / "
            + ui.color("quit", C.YELLOW)
        )

    def _play_level(self, level: str) -> None:
        # Present the level's riddles in a fresh random order each time.
        riddles = list(self.riddles[level])
        if not riddles:
            return
        random.shuffle(riddles)

        ui.level_banner(data.LEVEL_NAMES[level], f"{level.upper()} level", level)
        max_hints = data.HINTS_PER_LEVEL[level]
        print(
            f"  You have {ui.hearts(self.player.lives, self.player.max_lives)}"
            f"  ·  {max_hints} hints for this level."
        )
        print("  " + self._help_text())

        hints_left = max_hints
        mistakes_before = self.player.mistakes
        total = len(riddles)

        for index, riddle in enumerate(riddles, 1):
            hints_left = self._play_riddle(riddle, index, hints_left, level, total)
            if not self.player.alive:
                raise QuitGame

        # Flawless level → earn a life back (real runs only).
        if self.mode == "real" and self.player.mistakes == mistakes_before:
            if self.player.gain_life():
                print()
                print(
                    ui.color(
                        f"  Flawless level! You earned an extra life. "
                        f"{ui.hearts(self.player.lives, self.player.max_lives)}",
                        C.GREEN,
                    )
                )

    # -- one riddle ---------------------------------------------------------

    def _status_bar(self, level: str, done: int, total: int) -> str:
        # XP is only meaningful in a real run; Practice Mode drops that segment.
        xp = self.player.exp if self.mode == "real" else None
        return ui.status_bar(
            level.capitalize(),
            done,
            total,
            self.player.lives,
            self.player.max_lives,
            xp,
        )

    def _play_riddle(
        self, riddle: Riddle, index: int, hints_left: int, level: str, total: int
    ) -> int:
        # Persistent HUD: first thing on screen for this riddle's refresh,
        # above the prompt, hints, and feedback that follow.
        print()
        print(self._status_bar(level, index - 1, total))
        # Sphinx motif above the riddle's header, tinted by the level.
        ui.sphinx(level)
        riddle.display(index)

        while True:
            answer = ui.ask("\n  Your answer: ")
            command = answer.lower()

            if command == "quit":
                raise QuitGame

            if command in ("hint", "help"):
                hints_left = self._give_hint(riddle, hints_left)
                continue

            if command == "skip":
                if self._do_skip():
                    return hints_left
                continue

            if not answer:
                continue

            if riddle.check(answer):
                self._reward_correct(riddle)
                return hints_left

            # Wrong answer: costs a life and breaks the streak.
            self.player.lose_life()
            print(ui.color(f"  BZZT! {random.choice(data.TAUNT)}", C.RED))
            if not self.player.alive:
                return hints_left
            ui.animate_life_loss(self.player.lives, self.player.max_lives)

    def _reward_correct(self, riddle: Riddle) -> None:
        base, bonus = self.player.solve(difficulty=riddle.difficulty, award_xp=(self.mode == "real"))
        print()
        line = ui.color(f"  {random.choice(data.PRAISE)}", C.GREEN, C.BOLD)
        if self.mode == "real":
            line += ui.color(f"  (+{base} XP)", C.GREEN)
        print(line)
        if bonus:
            print(
                ui.color(
                    f"  🔥 {self.player.streak} in a row! "
                    f"Streak bonus +{bonus} XP",
                    C.YELLOW,
                    C.BOLD,
                )
            )

    def _do_skip(self) -> bool:
        """Handle a 'skip'. Returns True if the riddle was actually skipped."""
        if self.mode == "real":
            if not self.player.can_skip():
                print(
                    ui.color(
                        f"  You need {SKIP_COST} XP to skip "
                        f"(you have {self.player.exp}). Keep solving!",
                        C.YELLOW,
                    )
                )
                return False
            self.player.skip(cost=SKIP_COST)
            print(
                ui.color("  Skipped. The answer stays a mystery.", C.GREY)
                + ui.color(f"  (−{SKIP_COST} XP)", C.RED)
            )
        else:
            self.player.skip()  # free in Practice Mode
            print(ui.color("  Skipped. The answer stays a mystery.", C.GREY))
        return True

    def _give_hint(self, riddle: Riddle, hints_left: int) -> int:
        if hints_left <= 0:
            print(ui.color("  You're out of hints for this level!", C.YELLOW))
            return hints_left
        self.player.use_hint()
        hints_left -= 1
        print(ui.color(f"  HINT: {riddle.get_hint()}", C.YELLOW))
        print(ui.color(f"  ({hints_left} hint(s) left this level)", C.GREY))
        return hints_left

    # -- end screens --------------------------------------------------------

    def _win_screen(self) -> None:
        ui.win_banner()

    def _quit_screen(self) -> None:
        if self.player.alive:
            ui.banner("Game over")
            print(ui.color("  Thanks for playing — come back soon!", C.CYAN))
        else:
            ui.lose_banner()

    def _show_stats(self) -> None:
        rows = list(self.player.stats().items())
        title = f"REPORT CARD — {self.player.name}"
        if self.mode == "practice":
            title = f"PRACTICE SUMMARY — {self.player.name}"
        ui.report_card(title, rows)

"""Single entry point for Sphinx.

Dispatches to a front-end based on a command-line flag:

    -g / --gui                 the tkinter GUI version (default)
    -t / --terminal            the text (terminal) version
    -i / --interactive / -c / --choose
                               ask interactively which one to launch

The GUI is the default: with no flag (or with ``-g``) the GUI launches; ``-t``
opts into the terminal version; ``-i`` / ``-c`` bring up an interactive
chooser. Reachable as ``python -m sphinx`` or ``python play.py`` (both call
:func:`main`).
"""

from __future__ import annotations

import argparse
import sys

from . import data, ui
from .game import Game
from .player import Player
from .ui import C


def show_menu() -> str:
    ui.banner("Main Menu")
    print(f"  {ui.color('1', C.BOLD)}  Start Run      Easy → Medium → Hard, one life pool")
    print(f"  {ui.color('2', C.BOLD)}  Practice Mode  drill any level, no stakes")
    print(f"  {ui.color('3', C.BOLD)}  View Top 5     the leaderboard")
    print(f"  {ui.color('4', C.BOLD)}  Quit")
    print()

    # Easter egg: three invalid picks in a row and the game walks off in a huff.
    strikes = 0
    while True:
        choice = ui.ask("  Choose (1-4): ").lower()
        if choice in {"1", "2", "3", "4"}:
            return choice
        if choice == "quit":
            return "quit"
        strikes += 1
        if strikes >= 3:
            print(ui.color("\n  That's not nice!", C.RED, C.BOLD))
            raise SystemExit
        print(ui.color("  Please pick 1, 2, 3, or 4.", C.YELLOW))


def real_run() -> None:
    name = ui.ask("  Enter your name, riddler: ") or "Player"
    if name.lower() == "quit":
        return
    player = Player(name=name)
    drawn = data.draw_run()
    Game(player, drawn, mode="real").run()
    _handle_leaderboard(player, drawn)


def _handle_leaderboard(player: Player, drawn: dict) -> None:
    # A run no longer covers the whole pool, so raw XP is not comparable across
    # releases. Report the score against what this run could have earned.
    pct = data.score_pct(player.exp, drawn)
    if not data.qualifies(pct):
        print(ui.color(
            f"\n  Final score: {player.exp} XP — {pct}% of this run. "
            "Not a Top 5 this time.", C.CYAN))
        return
    print(ui.color(
        f"\n  🎉 {pct}% — {player.exp} XP earns you a spot in the Top 5!",
        C.GREEN, C.BOLD))
    board = data.add_score(player.name, pct)
    ui.show_leaderboard(board)


def practice_run() -> None:
    ui.banner("Practice Mode — drill a single level")
    level = ui.ask_choice("  Which level? (easy / medium / hard): ", data.LEVELS)
    if level == "quit":
        return
    player = Player(name="Player")
    Game(player, data.load_riddles(), mode="practice", practice_level=level).run()


def run_terminal() -> None:
    ui.clear_screen()
    ui.intro_banner()
    print()
    print("  Solve riddles across three levels. A wrong answer costs a life;")
    print("  clear a level flawlessly to earn one back.Good luck!")
    print("  Each correct answer earns experience points (XP). Use them to get hints when you're stuck.")
    print("  Good luck!")
    print("  The Top 5 leaderboard is based on total XP earned.")

    while True:
        choice = show_menu()
        if choice in ("4", "quit"):
            print(ui.color("\n  Goodbye! 👋\n", C.CYAN))
            break
        if choice == "1":
            real_run()
        elif choice == "2":
            practice_run()
        elif choice == "3":
            ui.show_leaderboard(data.load_leaderboard())


def run_gui() -> None:
    """Launch the tkinter GUI, with a friendly message if tkinter is absent."""
    try:
        import tkinter  # noqa: F401
    except ModuleNotFoundError:
        sys.exit(
            "tkinter is not installed — needed for the GUI version.\n"
            "  Fedora/RHEL  : sudo dnf install python3-tkinter\n"
            "  Debian/Ubuntu: sudo apt install python3-tk\n"
            "Or run the terminal version instead: python play.py --terminal"
        )
    from .gui import main as gui_main
    gui_main()


def choose_frontend() -> str:
    """Interactively ask which front-end to launch. Returns 't', 'g' or 'q'."""
    ui.intro_banner()
    print()
    print("  How would you like to play?")
    print(f"    {ui.color('t', C.BOLD)}  Terminal   the classic text version")
    print(f"    {ui.color('g', C.BOLD)}  GUI        the windowed (tkinter) version")
    print(f"    {ui.color('q', C.BOLD)}  Quit")
    print()
    while True:
        choice = ui.ask("  Choose (t/g): ").strip().lower()
        if choice in ("t", "terminal"):
            return "t"
        if choice in ("g", "gui"):
            return "g"
        if choice in ("q", "quit"):
            return "q"
        print(ui.color("  Please enter 't' for terminal or 'g' for GUI.", C.YELLOW))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="sphinx",
        description="Sphinx — a riddle game. Match wits with the sphinx.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-g", "--gui", action="store_true",
        help="launch the GUI (tkinter) version (default)",
    )
    group.add_argument(
        "-t", "--terminal", action="store_true",
        help="launch the terminal (text) version",
    )
    group.add_argument(
        "-i", "--interactive", "-c", "--choose",
        dest="interactive", action="store_true",
        help="ask interactively whether to play in the terminal or GUI",
    )
    args = parser.parse_args(argv)

    # The GUI is the default: launched by -g or by passing no flag at all.
    # -t opts into the terminal; -i / -c bring up the interactive chooser.
    if args.terminal:
        run_terminal()
    elif args.interactive:
        choice = choose_frontend()
        if choice == "t":
            run_terminal()
        elif choice == "g":
            run_gui()
    else:
        run_gui()


if __name__ == "__main__":
    main()

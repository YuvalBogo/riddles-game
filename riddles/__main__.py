"""Entry point: ``python -m riddles`` — the start menu and mode dispatch."""

from __future__ import annotations

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
    Game(player, data.load_riddles(), mode="real").run()
    _handle_leaderboard(player)


def _handle_leaderboard(player: Player) -> None:
    score = player.exp
    if not data.qualifies(score):
        print(ui.color(f"\n  Final score: {score} XP — not a Top 5 this time.", C.CYAN))
        return
    print(ui.color(f"\n  🎉 {score} XP earns you a spot in the Top 5!", C.GREEN, C.BOLD))
    board = data.add_score(player.name, score)
    ui.show_leaderboard(board)


def practice_run() -> None:
    ui.banner("Practice Mode — drill a single level")
    level = ui.ask_choice("  Which level? (easy / medium / hard): ", data.LEVELS)
    if level == "quit":
        return
    player = Player(name="Player")
    Game(player, data.load_riddles(), mode="practice", practice_level=level).run()


def main() -> None:
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


if __name__ == "__main__":
    main()

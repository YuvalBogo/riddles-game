"""Terminal presentation helpers: colors, screen control and prompts.

Everything here is dependency-free and degrades gracefully when the
output is not an interactive terminal (colors are simply switched off).
"""

from __future__ import annotations

import os
import sys
import time

# --- ANSI colors -----------------------------------------------------------

_COLORS_ENABLED = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


class C:
    """Named ANSI escape codes (blanked out when colors are disabled)."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GREY = "\033[90m"


if not _COLORS_ENABLED:
    for _name in list(vars(C)):
        if not _name.startswith("_") and _name.isupper():
            setattr(C, _name, "")


def color(text: str, *codes: str) -> str:
    """Wrap ``text`` in the given ANSI codes (no-op without color)."""
    if not codes:
        return text
    return f"{''.join(codes)}{text}{C.RESET}"


# --- Screen & output -------------------------------------------------------

def clear_screen() -> None:
    """Clear the terminal, on both POSIX and Windows."""
    if not sys.stdout.isatty():
        return
    os.system("cls" if os.name == "nt" else "clear")


def rule(char: str = "─", width: int = 60) -> str:
    return color(char * width, C.GREY)


def banner(title: str) -> None:
    line = rule("═")
    print()
    print(color(line, C.CYAN))
    print(color(f"  {title}", C.BOLD, C.CYAN))
    print(color(line, C.CYAN))


def _interactive() -> bool:
    """True only when both stdin and stdout are real terminals."""
    return sys.stdout.isatty() and sys.stdin.isatty()


def typewriter(text: str, delay: float = 0.02, *codes: str) -> None:
    """Reveal ``text`` character by character, optionally colored.

    The color ``codes`` wrap the whole string (written once), so escape
    sequences are never revealed one glyph at a time. The animation is
    skippable: pressing any key finishes the line instantly and the stray
    keystroke is drained so it can't pollute the next prompt.

    Falls back to a plain colored ``print`` when not on an interactive
    terminal, so piped/`NO_COLOR` runs behave exactly as before.
    """
    if delay <= 0 or not _interactive():
        print(color(text, *codes))
        return

    prefix = "".join(codes)
    sys.stdout.write(prefix)

    try:
        import termios
        import tty
        import select

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            skip = False
            for ch in text:
                sys.stdout.write(ch)
                sys.stdout.flush()
                if skip or ch == "\n":
                    continue
                ready, _, _ = select.select([sys.stdin], [], [], delay)
                if ready:
                    os.read(fd, 1024)  # drain the skip keystroke
                    skip = True
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except (ImportError, OSError):
        # No POSIX termios (e.g. Windows) — reveal without skip support.
        for ch in text:
            sys.stdout.write(ch)
            sys.stdout.flush()
            time.sleep(delay)

    sys.stdout.write(f"{C.RESET if prefix else ''}\n")
    sys.stdout.flush()


# --- Lives -----------------------------------------------------------------

def hearts(current: int, maximum: int) -> str:
    full = color("♥" * current, C.RED)
    empty = color("♡" * max(0, maximum - current), C.GREY)
    return full + empty


def animate_life_loss(current: int, maximum: int, delay: float = 0.14) -> None:
    """Show the just-lost heart flickering out, then settle on the final row.

    ``current`` is the number of lives remaining *after* the loss, so the
    heart at index ``current`` is the one being extinguished. Degrades to a
    single static line when not on an interactive terminal.
    """
    label = "  Lives left: "
    kept = color("♥" * current, C.RED)
    rest = max(0, maximum - current - 1)
    tail = color("♡" * rest, C.GREY)

    if not _interactive():
        print(label + hearts(current, maximum))
        return

    flicker = [
        color("✗", C.RED),
        color("♡", C.YELLOW),
        color("✗", C.RED),
        color("♡", C.GREY),
    ]
    for frame in flicker:
        sys.stdout.write("\r" + label + kept + frame + tail)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


# --- Input -----------------------------------------------------------------

def ask(prompt: str) -> str:
    """Prompt for input, returning a stripped string.

    Treats Ctrl-D / Ctrl-C as the sentinel command ``quit`` so the game
    loop can shut down cleanly instead of crashing with a traceback.
    """
    try:
        return input(color(prompt, C.BOLD)).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "quit"


def ask_choice(prompt: str, choices: list[str]) -> str:
    """Prompt until the user enters one of ``choices`` (case-insensitive)."""
    lowered = [c.lower() for c in choices]
    misses = 0
    while True:
        answer = ask(prompt).lower()
        if answer in lowered:
            return answer
        if answer == "quit":
            return "quit"
        misses += 1
        options = ", ".join(choices)
        print(color(f"  Please choose one of: {options}", C.YELLOW))
        if misses >= 3:
            print(color("  (tip: type 'quit' any time to leave)", C.GREY))


# --- Framed banners --------------------------------------------------------

def _visible_len(text: str) -> int:
    """Length of ``text`` ignoring ANSI escape sequences."""
    out, i = 0, 0
    while i < len(text):
        if text[i] == "\033":
            while i < len(text) and text[i] != "m":
                i += 1
            i += 1
            continue
        out += 1
        i += 1
    return out


def framed(lines: list[str], *codes: str, pad: int = 2) -> str:
    """Draw ``lines`` inside a box-drawing frame, padded and colored.

    Lines may already contain ANSI codes; their visible width is measured
    correctly so the right border stays aligned.
    """
    inner = max((_visible_len(ln) for ln in lines), default=0) + pad * 2
    top = "╔" + "═" * inner + "╗"
    bottom = "╚" + "═" * inner + "╝"
    body = []
    for ln in lines:
        gap = inner - _visible_len(ln) - pad
        body.append("║" + " " * pad + ln + " " * gap + "║")
    frame = "\n".join([top, *body, bottom])
    return color(frame, *codes) if codes else frame


# Small, 80-col-safe art with a sphinx / vault theme.
_INTRO_ART = [
    r"      /\_/\        ",
    r"     ( o.o )   R I D D L E S   2 . 0",
    r"      > ^ <    Match wits with the Sphinx...",
]

_WIN_ART = [
    r"    \o/    THE VAULT OPENS",
    r"     |     Every riddle bows before you.",
    r"    / \    ",
]

_LOSE_ART = [
    r"    x_x    THE VAULT SEALS SHUT",
    r"     |     Your wits ran dry.",
    r"    / \    ",
]


def intro_banner() -> None:
    print()
    print(framed(_INTRO_ART, C.CYAN, C.BOLD))


def win_banner() -> None:
    print()
    print(framed(_WIN_ART, C.GREEN, C.BOLD))


def lose_banner() -> None:
    print()
    print(framed(_LOSE_ART, C.RED, C.BOLD))


# Accent color per level — intensifies as levels get harder (cool → hot),
# reinforcing rising tension.
LEVEL_ACCENT = {"easy": C.CYAN, "medium": C.YELLOW, "hard": C.RED}


def level_banner(title: str, subtitle: str, level: str | None = None) -> None:
    """Themed banner shown when entering a level."""
    accent = LEVEL_ACCENT.get(level or "", C.MAGENTA)
    print()
    print(framed([title, color(subtitle, C.DIM)], accent, C.BOLD))


def level_descent(to_level: str) -> None:
    """A brief 'descent' beat between levels, darkening into the next level.

    Purely decorative — skipped entirely when colors are disabled or the
    output isn't an interactive terminal, per the existing fallback rules.
    """
    if not (_COLORS_ENABLED and _interactive()):
        return
    accent = LEVEL_ACCENT.get(to_level, C.MAGENTA)
    # Bright → normal → dim → dark: the palette sinks as we descend.
    shades = [C.BOLD + accent, accent, C.DIM + accent, C.DIM + C.GREY]
    bar = "▼ " * 12
    print()
    for shade in shades:
        sys.stdout.write("\r  " + color(bar, shade))
        sys.stdout.flush()
        time.sleep(0.22)
    sys.stdout.write("\n")
    print(color(f"  Descending into {to_level.upper()}...", C.DIM))
    time.sleep(0.35)


def show_leaderboard(entries: list[tuple[str, int]]) -> None:
    """Render the Top 5 leaderboard inside a frame."""
    lines = [color("🏆  TOP 5 RIDDLERS", C.BOLD)]
    if not entries:
        lines.append(color("No scores yet — be the first!", C.DIM))
    else:
        lines.append("")
        for rank, (name, score) in enumerate(entries, 1):
            row = f"{rank}.  {name[:16].ljust(16)}  {str(score).rjust(5)} XP"
            lines.append(row)
    print()
    print(framed(lines, C.YELLOW, pad=2))


def report_card(title: str, rows: list[tuple[str, str]]) -> None:
    """Render an end-of-run 'report card' inside a box-drawing frame."""
    width = max((len(k) for k, _ in rows), default=0)
    lines = [color(title, C.BOLD), ""]
    for key, value in rows:
        lines.append(f"{key.ljust(width)}  :  {color(str(value), C.CYAN)}")
    print()
    print(framed(lines, C.YELLOW, pad=3))

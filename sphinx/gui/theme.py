"""Shared visual theme for the tkinter front-end.

One place for the look every ``gui_*`` module reuses: the black-content
config, the vivid palette echoing the terminal's ANSI colors, the per-level
accent ("chrome") tints, and monospace font resolution. Kept dependency-free
(only tkinter) so any GUI module can import it without cycles.
"""

from __future__ import annotations

from tkinter import font as tkfont

# --- Configuration (swappable without touching rendering logic) ------------

CONFIG = {
    "background": "#000000",       # content background — black, per spec
    "font_family": "Noto Sans Mono",  # preferred; see resolve_font for fallback
    "font_size": 15,
    "border_px": 10,               # chrome margin that reveals the level tint
}

# Preference order for a monospace with good box-drawing / ♥ / ■ coverage.
# The first family actually installed wins, so the look stays consistent
# instead of silently falling back to some Tk default.
_FONT_FALLBACKS = [
    "Noto Sans Mono", "DejaVu Sans Mono", "Liberation Mono",
    "Source Code Pro", "Courier New", "Courier",
]


def resolve_font(root) -> str:
    """The best available monospace family for ``root`` (preferred first)."""
    available = set(tkfont.families(root))
    for family in [CONFIG["font_family"], *_FONT_FALLBACKS]:
        if family in available:
            return family
    return "TkFixedFont"


# Vivid, saturated palette echoing the terminal ANSI colors.
PALETTE = {
    "fg": "#e8e8e8",
    "red": "#ff4141",
    "green": "#3dff6e",
    "yellow": "#ffe23d",
    "blue": "#4aa3ff",
    "magenta": "#ff5cff",
    "cyan": "#38e8e8",
    "grey": "#8b8b8b",
}

# Ambient chrome per level — cool → hot, intensifying with difficulty.
LEVEL_CHROME = {"easy": "#00c2c2", "medium": "#ff9a00", "hard": "#ff2b2b"}

# The sphinx's own voice, in tomb colours rather than the HUD's neon: gilded for
# praise, oxidised copper for a wrong answer. Both are picked to hold their own
# against the black content background — the sienna reads at about 5.6:1, the
# same legibility the old alarm-red had, without shouting like it.
CAPTION = {
    "praise": "#e3b23c",   # gold leaf
    "taunt": "#c96a4a",    # burnt sienna
}

"""Small reusable tkinter widgets for the GUI.

Currently the hover ``Tooltip`` used by the '?' help badges next to menu
buttons — a themed, borderless floating explanation.
"""

from __future__ import annotations

import tkinter as tk

from .theme import PALETTE


class Tooltip:
    """A themed hover tooltip: a small borderless ``Toplevel`` that floats
    beside ``widget`` while the pointer is over it and vanishes on leave.

    Styled to match the game — a black card with a coloured 1-px frame and the
    light palette text — and torn down if the widget it's attached to is
    destroyed (so a screen change never leaves an orphan tip on screen).
    """

    def __init__(self, widget, text: str, font, accent: str | None = None):
        self.widget = widget
        self.text = text
        self.font = font
        self.accent = accent or PALETTE["cyan"]
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _show(self, _event=None) -> None:
        if self.tip is not None or not self.text:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)          # no title bar / border
        self.tip.configure(bg=self.accent)          # accent shows as a 1-px frame
        tk.Label(
            self.tip, text=self.text, font=self.font, justify="left",
            bg="#111111", fg=PALETTE["fg"], wraplength=300, padx=12, pady=9,
        ).pack(padx=1, pady=1)
        # Float just to the right of the badge and vertically centred on it, so
        # the tip lines up with the button's height instead of hanging from its
        # top. The menu is centred, so there's open space out to the right.
        self.tip.update_idletasks()
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 10
        cy = self.widget.winfo_rooty() + self.widget.winfo_height() // 2
        y = cy - self.tip.winfo_reqheight() // 2
        self.tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event=None) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None

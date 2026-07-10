"""tkinter front-end for Sphinx — an alternate skin over the same engine.

This module is the entry point and the ``App`` controller: the main menu and
the screens it leads to (Practice / Leaderboard / About), window sizing, and
launching a run. Within the ``gui`` package: the look lives in ``theme``,
images in ``assets``, the hover tooltip in ``widgets``, the README renderer in
``markdown``, and the live game screen in ``game`` (``RiddlesGUI``). The
flow/scoring logic lives in ``state.RunState``; nothing here imports the
terminal front-end (``ui.py`` / ``__main__.py``).

Requires ``tkinter`` (Fedora: ``sudo dnf install python3-tkinter``).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from .. import __version__, data
from ..player import Player
from .assets import (load_image, natural_banner_height, set_banner_height,
                     set_window_icon)
from .game import RiddlesGUI
from .markdown import read_about
from .markdown import render as render_markdown
from .state import RunState
from .theme import CONFIG, LEVEL_CHROME, PALETTE, resolve_font
from .widgets import Tooltip

# Room (px) reserved for the window manager's chrome (title bar + panels) so a
# screen never opens taller than the visible desktop. The Easy banner takes
# the room left after the rest of the game fits, but never more than
# MAX_BANNER_H (so freeing deck height shortens the window instead of just
# growing the banner), and hides below MIN_BANNER_H rather than show a sliver.
SCREEN_MARGIN = 100
MIN_BANNER_H = 70
MAX_BANNER_H = 120


class App:
    """Top-level controller: the main menu and the screens it leads to.

    Mirrors the terminal menu — Start Run / Practice Mode / View Top 5 /
    Quit — swapping the window's contents between a menu, a running game,
    and the leaderboard on one root window.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.game: RiddlesGUI | None = None
        self._key_bindings: list[str] = []  # root key shortcuts for the live screen
        family = resolve_font(root)
        self.font = tkfont.Font(family=family, size=CONFIG["font_size"])
        self.title_font = tkfont.Font(
            family=family, size=CONFIG["font_size"] + 6, weight="bold"
        )
        # A quieter face for fine print (the About rights note).
        self.small_font = tkfont.Font(family=family, size=CONFIG["font_size"] - 4)
        # Faces for the rendered-Markdown README (headings + bold).
        self.md_fonts = {
            "h1": tkfont.Font(family=family, size=CONFIG["font_size"] + 7, weight="bold"),
            "h2": tkfont.Font(family=family, size=CONFIG["font_size"] + 4, weight="bold"),
            "h3": tkfont.Font(family=family, size=CONFIG["font_size"] + 1, weight="bold"),
            "bold": tkfont.Font(family=family, size=CONFIG["font_size"], weight="bold"),
        }
        # The window's default size, fitted to the screen once. Every screen
        # reuses it, so the window never jumps between screens.
        self._compute_layout()
        self._center_window(*self._game_size)
        self.show_menu()

    def _center_window(self, w: int, h: int) -> None:
        """Open the window at the default size, centered on screen. Set once —
        _clear never touches geometry again, so any manual move or resize the
        user makes afterwards persists across every screen switch. ``minsize``
        keeps it from shrinking below what the riddle interface needs."""
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(w, h)

    def _compute_layout(self) -> None:
        """Pick the Easy-banner height and the window size so nothing opens
        taller than the visible desktop.

        The rest of the game (HUD, story, deck, controls) has a fixed natural
        height; the banner takes only the vertical room left over on this
        screen — its full height on a tall display, a shrunk one on a laptop,
        or nothing at all when there's no room. Publishes the chosen banner
        height to ``assets`` and sets ``self._game_size``.
        """
        usable_h = self.root.winfo_screenheight() - SCREEN_MARGIN
        usable_w = self.root.winfo_screenwidth() - SCREEN_MARGIN

        set_banner_height(0)                           # measure the game bannerless
        base_w, base_h = self._measure_game_size()
        nat_h = min(natural_banner_height(), MAX_BANNER_H)

        gap = 8                                         # matches render_banner's pady
        budget = usable_h - base_h - gap
        banner_h = min(nat_h, budget)
        banner_h = banner_h if banner_h >= MIN_BANNER_H else 0
        set_banner_height(banner_h)

        win_h = base_h + (banner_h + gap if banner_h else 0)
        self._game_size = (min(base_w, usable_w), min(win_h, usable_h))

    def _measure_game_size(self) -> tuple[int, int]:
        """Lay a game out on a hidden window to read the pixel size the riddle
        interface needs. Built and torn down invisibly; nothing is shown."""
        probe = tk.Toplevel(self.root)
        probe.withdraw()
        try:
            state = RunState(data.load_riddles(), Player(name="?"), mode="real")
            RiddlesGUI(probe, state)
            probe.update_idletasks()
            return probe.winfo_reqwidth(), probe.winfo_reqheight()
        finally:
            probe.destroy()

    # -- screen scaffolding -------------------------------------------------

    def _clear(self) -> None:
        if self.game is not None:
            self.game.teardown()
            self.game = None
        self.root.unbind("<Left>")
        self.root.unbind("<Right>")
        self.root.unbind("<Escape>")   # the running game's "back to menu" key
        # Release this screen's number-key shortcuts so they never fire while
        # a later screen (e.g. a running game) is shown.
        for seq in self._key_bindings:
            self.root.unbind(seq)
        self._key_bindings.clear()
        for widget in self.root.winfo_children():
            widget.destroy()
        # Deliberately does NOT touch geometry: the window keeps its default
        # size (set once in _center_window) and, once the user moves or resizes
        # it, that choice — so screens never jump around underneath them.

    def _screen(self, accent: str) -> tk.Frame:
        """A bordered black screen (accent chrome), returns the content frame."""
        chrome = tk.Frame(self.root, bg=accent)
        chrome.pack(fill="both", expand=True)
        content = tk.Frame(chrome, bg=CONFIG["background"])
        content.pack(fill="both", expand=True,
                     padx=CONFIG["border_px"], pady=CONFIG["border_px"])
        return content

    def _title(self, parent, text, color) -> None:
        tk.Label(parent, text=text, font=self.title_font,
                 bg=CONFIG["background"], fg=color).pack(pady=(28, 6))

    def _menu_button(self, parent, label, desc, color, cmd, key=None,
                     help_text=None) -> None:
        # Each item is a centred vertical stack: the button on top, its small
        # grey description directly beneath. The shortcut digit rides just left
        # of the button, balanced by an equal-width slot on the right so the
        # button itself stays dead-centre (the number key still works too).
        # When ``help_text`` is given, that right slot holds a '?' badge whose
        # hover reveals a floating explanation.
        item = tk.Frame(parent, bg=CONFIG["background"])
        item.pack(pady=6)

        # Three-column grid with equal (uniform) side columns, so the button in
        # the middle stays dead-centre whether or not there's a '?' badge: the
        # shortcut digit hugs its left, the badge (if any) hugs its right.
        top = tk.Frame(item, bg=CONFIG["background"])
        top.pack()
        top.grid_columnconfigure(0, uniform="side", minsize=36)
        top.grid_columnconfigure(2, uniform="side", minsize=36)

        tk.Label(top, text=(str(key) if key is not None else ""),
                 font=self.small_font, bg=CONFIG["background"],
                 fg=PALETTE["grey"]).grid(row=0, column=0, sticky="e", padx=(0, 4))
        tk.Button(
            top, text=label, command=cmd, font=self.font, width=16,
            bg="#111111", fg=color, activebackground="#222222",
            activeforeground=color, relief="flat", bd=0, cursor="hand2", pady=8,
        ).grid(row=0, column=1)
        if help_text:
            badge = tk.Button(
                top, text="?", width=2, font=self.small_font, bg="#111111",
                fg=color, activebackground="#222222", activeforeground=color,
                relief="flat", bd=0, cursor="hand2",
            )
            badge.grid(row=0, column=2, sticky="w", padx=(4, 0))
            Tooltip(badge, help_text, self.font, accent=color)
        if key is not None:
            self._bind_key(key, cmd)

        if desc:
            tk.Label(item, text=desc.strip(), font=self.small_font,
                     bg=CONFIG["background"], fg=PALETTE["grey"]).pack(pady=(3, 0))

    def _bind_key(self, digit: int, cmd) -> None:
        """Bind a number key (top-row and keypad) to a menu action, tracking it
        so ``_clear`` can release it when the screen changes."""
        for seq in (f"<Key-{digit}>", f"<KP_{digit}>"):
            self.root.bind(seq, lambda event, c=cmd: c())
            self._key_bindings.append(seq)

    def _bind_back(self, cmd) -> None:
        """Bind Esc and Backspace as 'back' shortcuts for the current
        sub-screen, tracked so ``_clear`` releases them on exit. Esc is the
        one key that leaves every screen, matching its ◀ Back button (and, in
        a running game, the ≡ Menu button). Safe on screens whose only text
        widgets are read-only, so neither key is ever needed for editing."""
        for seq in ("<Escape>", "<BackSpace>"):
            self.root.bind(seq, lambda event: cmd())
            self._key_bindings.append(seq)

    def _confirm_quit(self) -> None:
        """A themed 'leave the game?' pop-up, echoing the in-run back-to-menu
        panel: the safe choice starts focused, ← → move between the two, Enter
        or Space confirms, Esc cancels. Modal, so a second Esc can't stack it."""
        bg = CONFIG["background"]
        dialog = tk.Toplevel(self.root, bg=PALETTE["magenta"])
        dialog.title("Sphinx")
        dialog.resizable(False, False)
        dialog.transient(self.root)

        content = tk.Frame(dialog, bg=bg)
        content.pack(fill="both", expand=True,
                     padx=CONFIG["border_px"], pady=CONFIG["border_px"])
        tk.Label(content, text="Leave Sphinx?", font=self.font,
                 bg=bg, fg=PALETTE["fg"]).pack(padx=40, pady=(24, 4))
        tk.Label(content, text="The sphinx will still be here when you return.",
                 font=self.small_font, bg=bg, fg=PALETTE["grey"]).pack(pady=(0, 18))

        row = tk.Frame(content, bg=bg)
        row.pack()

        def choice(text, cmd, color):
            btn = tk.Button(
                row, text=text, command=cmd, font=self.font,
                bg="#111111", fg=color, activebackground="#222222",
                activeforeground=color, relief="flat", bd=0,
                highlightthickness=2, highlightbackground=bg,
                highlightcolor=color, padx=14, pady=6, cursor="hand2",
            )
            btn.pack(side="left", padx=8)
            btn.bind("<Return>", lambda e: cmd())   # Tk gives Space for free
            return btn

        yes = choice("Yes — Exit", self.root.destroy, PALETTE["red"])
        keep = choice("No — Stay", dialog.destroy, PALETTE["cyan"])

        def focus_on(btn):
            def handler(_event=None):
                btn.focus_set()
                return "break"
            return handler
        for btn in (yes, keep):
            btn.bind("<Left>", focus_on(yes))
            btn.bind("<Right>", focus_on(keep))
        keep.focus_set()   # the safe choice starts under Return and Space

        tk.Label(content, text="← → choose  ·  Enter to confirm  ·  Esc to cancel",
                 font=self.small_font, bg=bg,
                 fg=PALETTE["grey"]).pack(pady=(16, 22))
        dialog.bind("<Escape>", lambda e: dialog.destroy())

        # Centre the dialog over the main window, then make it modal.
        dialog.update_idletasks()
        px, py = self.root.winfo_rootx(), self.root.winfo_rooty()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        w, h = dialog.winfo_width(), dialog.winfo_height()
        dialog.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
        dialog.grab_set()

    # -- screens ------------------------------------------------------------

    def show_menu(self) -> None:
        self._clear()
        c = self._screen(PALETTE["magenta"])
        self._title(c, "🧩  S P H I N X  🧩", PALETTE["cyan"])
        tk.Label(c, text="Do you have what it take to enter the sphinx?", font=self.font,
                 bg=CONFIG["background"], fg=PALETTE["grey"]).pack(pady=(0, 8))

        # The sphinx bust — pixel-art centrepiece of the welcome screen. Falls
        # back to a plain caption if the image can't be loaded.
        img = load_image("menu")
        sphinx = tk.Label(c, image=img, bg=CONFIG["background"])
        sphinx.image = img   # keep a reference so Tk doesn't drop the pixels
        sphinx.pack(pady=(0, 14))

        # Version, pinned quietly to the bottom edge (small, dim).
        tk.Label(c, text=f"- version {__version__} -", font=self.small_font,
                 bg=CONFIG["background"], fg="#555555").pack(side="bottom",
                                                             pady=(0, 12))

        self._menu_button(
            c, "Survival Run", "one life pool",
            PALETTE["green"], self.start_run, key=1,
            help_text=("A full run:\n Easy → Medium → Hard. \n"
                       "Earn XP to pay for hints and skips. "
                       "Strong score lands on the Top 5 leaderboard."))
        self._menu_button(
            c, "Practice Mode", "free hints, free skips",
            PALETTE["cyan"], self.show_practice, key=2,
            help_text=("Drill any single level on its own. "
                       "No XP is scored so no leaderboard placement is possible."))
        self._menu_button(c, "Leaderboard", "view top 5",
                          PALETTE["yellow"], self.show_leaderboard, key=3)
        self._menu_button(c, "About", "",
                          PALETTE["blue"], self.show_about, key=4)
        self._menu_button(c, "Quit", "  (or press Esc)", PALETTE["red"],
                          self._confirm_quit, key=5)
        # On the main menu Esc is the same as choosing Quit: it asks first,
        # rather than dropping out of the game without warning.
        self.root.bind("<Escape>", lambda event: self._confirm_quit())
        self._key_bindings.append("<Escape>")

    def show_practice(self) -> None:
        self._clear()
        c = self._screen(LEVEL_CHROME["easy"])
        self._title(c, "Pick a single level to practice on", PALETTE["cyan"])
        riddles = data.load_riddles()
        for i, level in enumerate(data.LEVELS, start=1):
            self._menu_button(
                c, level.capitalize(), f"{len(riddles[level])} riddles",
                LEVEL_CHROME[level], lambda lv=level: self.start_practice(lv), key=i,
            )
        self._menu_button(c, "◀ Back", "  (or press Esc)",
                          PALETTE["grey"], self.show_menu)
        self._bind_back(self.show_menu)

    def show_leaderboard(self) -> None:
        self._clear()
        c = self._screen(PALETTE["yellow"])
        self._title(c, "🏆  TOP 5 RIDDLERS", PALETTE["yellow"])
        entries = data.load_leaderboard()
        if not entries:
            tk.Label(c, text="No scores yet — be the first!", font=self.font,
                     bg=CONFIG["background"], fg=PALETTE["grey"]).pack(pady=12)
        else:
            for rank, (name, xp, max_exp) in enumerate(entries, 1):
                is_perfect = xp == max_exp
                perfect_badge = " (100%)" if is_perfect else ""
                tk.Label(
                    c, text=f"{rank}.  {name[:16].ljust(16)}  {str(xp).rjust(4)} XP{perfect_badge}",
                    font=self.font, bg=CONFIG["background"], fg=PALETTE["cyan"],
                ).pack(pady=2)
        tk.Label(c, text="", bg=CONFIG["background"]).pack(pady=6)
        self._menu_button(c, "◀ Back", "  (or press Esc)",
                          PALETTE["grey"], self.show_menu)
        self._bind_back(self.show_menu)

    def show_about(self) -> None:
        self._clear()
        c = self._screen(PALETTE["blue"])

        # The only fixed element up top: the sphinx and its companions (the four
        # canopic jars). Everything else — including the contact/GitHub link —
        # lives in the scrollable README below. Skipped if it can't be loaded.
        jars = load_image("about")
        if jars is not None:
            banner = tk.Label(c, image=jars, bg=CONFIG["background"])
            banner.image = jars
            banner.pack(pady=(8, 12))

        # The README, rendered in the app's palette inside a scrollable pane so
        # the whole file is readable without leaving the game's look.
        pane = tk.Frame(c, bg=CONFIG["background"])
        pane.pack(fill="both", expand=True, padx=40)
        scroll = tk.Scrollbar(pane, bg="#111111", troughcolor=CONFIG["background"],
                              activebackground=PALETTE["grey"], bd=0,
                              highlightthickness=0)
        scroll.pack(side="right", fill="y")
        readme = tk.Text(
            pane, font=self.font, bg=CONFIG["background"], fg=PALETTE["fg"],
            relief="flat", bd=0, highlightthickness=0, wrap="word",
            width=64, height=20, padx=12, pady=8,
            yscrollcommand=scroll.set, insertbackground=PALETTE["fg"],
            selectbackground="#333333",
        )
        readme.pack(side="left", fill="both", expand=True)
        scroll.configure(command=readme.yview)
        render_markdown(readme, read_about(), self.md_fonts)
        readme.configure(state="disabled")   # read-only

        # ↑ / ↓ scroll the README (it is read-only, so the arrows are free to
        # drive the view). Tracked so _clear releases them on exit.
        for seq, step in (("<Up>", -2), ("<Down>", 2)):
            self.root.bind(seq, lambda e, s=step: readme.yview_scroll(s, "units"))
            self._key_bindings.append(seq)

        # Explicit scroll instruction at the bottom.
        tk.Label(c, text="use ↑ / ↓ keys to scroll", font=self.small_font,
                 bg=CONFIG["background"], fg=PALETTE["grey"]).pack(pady=(6, 0))

        # Fine print — deliberately quiet (small, grey), easy to miss.
        tk.Label(c, text="© Yuval Bogomoletz — all rights reserved",
                 font=self.small_font, bg=CONFIG["background"],
                 fg=PALETTE["grey"]).pack(pady=(2, 4))
        self._menu_button(c, "◀ Back", "(or press Esc)",
                          PALETTE["grey"], self.show_menu)
        self._bind_back(self.show_menu)

    # -- launching a game ---------------------------------------------------

    def start_run(self) -> None:
        name = self._ask_name() or "Player"
        self._clear()
        # A real run draws a subset of the pool; Practice Mode drills all of it.
        state = RunState(data.draw_run(), Player(name=name), mode="real")
        self.game = RiddlesGUI(self.root, state, on_menu=self.show_menu)

    def _ask_name(self) -> str:
        """A theme-matched replacement for ``simpledialog.askstring`` — black
        content, magenta chrome and the vivid palette, so the name prompt
        looks like the rest of the app instead of a raw system dialog."""
        bg = CONFIG["background"]
        dialog = tk.Toplevel(self.root, bg=PALETTE["magenta"])
        dialog.title("Sphinx")
        dialog.resizable(False, False)
        dialog.transient(self.root)

        content = tk.Frame(dialog, bg=bg)
        content.pack(fill="both", expand=True,
                     padx=CONFIG["border_px"], pady=CONFIG["border_px"])
        tk.Label(content, text="Enter your name, riddler:", font=self.font,
                 bg=bg, fg=PALETTE["cyan"]).pack(padx=28, pady=(22, 12))
        entry = tk.Entry(
            content, font=self.font, bg="#111111", fg=PALETTE["fg"],
            insertbackground=PALETTE["fg"], relief="flat", width=24,
            justify="center",
        )
        entry.pack(padx=28, ipady=4)
        entry.focus_set()

        result = {"name": None}

        def confirm(event=None):
            result["name"] = entry.get().strip()
            dialog.destroy()

        tk.Button(
            content, text="Begin", command=confirm, font=self.font,
            bg="#111111", fg=PALETTE["green"], activebackground="#222222",
            activeforeground=PALETTE["green"], relief="flat", bd=0,
            highlightthickness=0, cursor="hand2", padx=12, pady=6,
        ).pack(pady=(18, 22))
        entry.bind("<Return>", confirm)
        dialog.bind("<Escape>", lambda e: dialog.destroy())

        # Centre the dialog over the main window.
        dialog.update_idletasks()
        px, py = self.root.winfo_rootx(), self.root.winfo_rooty()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        w, h = dialog.winfo_width(), dialog.winfo_height()
        dialog.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

        dialog.grab_set()
        self.root.wait_window(dialog)
        return result["name"]

    def start_practice(self, level: str) -> None:
        self._clear()
        state = RunState(data.load_riddles(), Player(name="Player"),
                         mode="practice", practice_level=level)
        self.game = RiddlesGUI(self.root, state, on_menu=self.show_menu)


def main() -> None:
    # className becomes the window's WM_CLASS — Tk capitalises it, so the class
    # is "Sphinx", which is what sphinx.desktop declares as StartupWMClass. A
    # Wayland compositor draws the dock icon from the .desktop entry it matches
    # on that class, ignoring the icon a window sets on itself; X11 does the
    # opposite. Both are set, because either session may be the one running.
    root = tk.Tk(className="sphinx")
    root.title("Sphinx")
    root.configure(bg=CONFIG["background"])
    set_window_icon(root)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""tkinter front-end for Sphinx — an alternate skin over the same engine.

This is an experimental GUI that renders the *unmodified* engine
(``Player`` / ``Riddle`` / ``data``) with the same clothes as the terminal
version: black background, one monospace font, vivid palette, box-drawing
borders drawn as text. The flow logic lives in ``gui_state.RunState``; this
module only renders, animates and reads input.

Requires ``tkinter`` (Fedora: ``sudo dnf install python3-tkinter``). It does
not import or modify the terminal front-end (``ui.py`` / ``__main__.py``).
"""

from __future__ import annotations

import random
import tkinter as tk
from tkinter import font as tkfont

from . import __version__, data
from .gui_state import CONTENT_W, RunState
from .player import Player, SKIP_COST

# --- Configuration (swappable without touching rendering logic) ------------

CONFIG = {
    "background": "#000000",       # content background — black, per spec
    "font_family": "Noto Sans Mono",  # preferred; see _resolve_font for fallback
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


def _resolve_font(root) -> str:
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

RESULT_COLOR = {
    "pending": PALETTE["cyan"],
    "correct": PALETTE["green"],
    "wrong": PALETTE["red"],
    "skipped": PALETTE["grey"],
}
RESULT_MARK = {"correct": "✓", "wrong": "✗", "skipped": "—"}

# Deliberately chunky, un-eased motion.
SLIDE_FRAMES = 6
SLIDE_MS = 26
BLINK_MS = 110
CARD_ROWS = 26   # deck canvas height in text rows (fits the tallest card)


class RiddlesGUI:
    def __init__(self, root: tk.Tk, state: RunState, on_menu=None):
        self.root = root
        self.state = state
        self.on_menu = on_menu     # callback to return to the main menu
        self.view_index = state.live_index()
        self._card_items: list[int] = []
        self._animating = False
        self._alive = True         # guards pending .after callbacks on teardown
        self._heart_flash = None   # (index, glyph, color)
        self._square_flash = None  # (index, glyph, color)
        self._popup_after = None   # pending .after id for the centre banner

        family = _resolve_font(root)
        self.font = tkfont.Font(family=family, size=CONFIG["font_size"])
        # Larger, bold face for the praise/taunt banner that pops in the
        # centre of the deck on every answer.
        self.popup_font = tkfont.Font(
            family=family, size=CONFIG["font_size"] + 8, weight="bold"
        )
        self.charw = self.font.measure("0")
        self.lineh = self.font.metrics("linespace")
        self.card_w_px = (CONTENT_W + 4) * self.charw
        self.deck_w = int(self.card_w_px + 6 * self.charw)
        self.deck_h = CARD_ROWS * self.lineh

        self._build_widgets()
        self._apply_chrome(self.state.level)
        self._card_items = self._draw_card(
            self._card_render(self.state.live_card()), self._card_x(), self.lineh
        )
        self.render_header()
        self._sync_input_state()
        self.entry.focus_set()

    # -- layout -------------------------------------------------------------

    def _build_widgets(self) -> None:
        bg = CONFIG["background"]
        b = CONFIG["border_px"]

        # Outer chrome frame (tinted per level) framing black content.
        self.chrome = tk.Frame(self.root, bg=LEVEL_CHROME["easy"])
        self.chrome.pack(fill="both", expand=True)
        content = tk.Frame(self.chrome, bg=bg)
        content.pack(fill="both", expand=True, padx=b, pady=b)

        self.header = tk.Canvas(
            content, bg=bg, height=2 * self.lineh,
            width=self.deck_w, highlightthickness=0,
        )
        self.header.pack(fill="x", pady=(0, 4))

        self.deck = tk.Canvas(
            content, bg=bg, width=self.deck_w, height=self.deck_h,
            highlightthickness=0,
        )
        self.deck.pack()

        self.msg = tk.Label(
            content, bg=bg, fg=PALETTE["fg"], font=self.font,
            text="", anchor="w",
        )
        self.msg.pack(fill="x", pady=(4, 4))

        controls = tk.Frame(content, bg=bg)
        # Extra bottom padding lifts the entry/buttons off the window edge
        # for visual comfort.
        controls.pack(fill="x", pady=(0, 22))

        def mkbtn(text, cmd, color=PALETTE["fg"]):
            return tk.Button(
                controls, text=text, command=cmd, font=self.font,
                bg="#111111", fg=color, activebackground="#222222",
                activeforeground=color, relief="flat", bd=0,
                highlightthickness=0, padx=8, cursor="hand2",
            )

        self.menu_btn = mkbtn("≡ Menu", self._to_menu, PALETTE["magenta"])
        self.menu_btn.pack(side="left", padx=(0, 10))
        self.back_btn = mkbtn("◀", self.on_back, PALETTE["cyan"])
        self.back_btn.pack(side="left")

        self.entry = tk.Entry(
            controls, font=self.font, bg="#111111", fg=PALETTE["fg"],
            insertbackground=PALETTE["fg"], relief="flat", width=28,
        )
        self.entry.pack(side="left", padx=6, ipady=4)

        self.submit_btn = mkbtn("Answer", self.on_submit, PALETTE["green"])
        self.submit_btn.pack(side="left", padx=2)
        self.hint_btn = mkbtn("Hint", self.on_hint, PALETTE["yellow"])
        self.hint_btn.pack(side="left", padx=2)
        self.skip_btn = mkbtn("Skip", self.on_skip, PALETTE["grey"])
        self.skip_btn.pack(side="left", padx=2)
        self.fwd_btn = mkbtn("▶", self.on_forward, PALETTE["cyan"])
        self.fwd_btn.pack(side="right")

        # Key bindings: Enter submits; arrows navigate the deck (but still
        # edit the entry text when it isn't empty, so typing feels normal).
        self.entry.bind("<Return>", self.on_submit)
        self.entry.bind("<Left>", self._entry_left)
        self.entry.bind("<Right>", self._entry_right)
        self.root.bind("<Left>", self.on_back)
        self.root.bind("<Right>", self.on_forward)

    # -- geometry / drawing -------------------------------------------------

    def _card_x(self) -> float:
        return (self.deck_w - self.card_w_px) / 2

    def _card_render(self, card) -> list[tuple[str, str]]:
        """Build a boxed card as a list of (line_text, color)."""
        w = CONTENT_W
        border = RESULT_COLOR[card.result]
        top = "╔" + "═" * (w + 2) + "╗"
        bot = "╚" + "═" * (w + 2) + "╝"

        def row(text: str) -> str:
            return "║ " + text[:w].ljust(w) + " ║"

        lines: list[tuple[str, str]] = [(top, border)]
        lines.append((row(card.title), PALETTE["magenta"]))
        lines.append((row(""), border))
        for body_line in card.body:
            lines.append((row(body_line), PALETTE["cyan"]))
        if card.hints:
            lines.append((row(""), border))
            for hint_line in card.hints:
                lines.append((row(hint_line), PALETTE["yellow"]))
        if card.result != "pending":
            lines.append((row(""), border))
            mark = RESULT_MARK.get(card.result, "")
            if card.answer:
                lines.append((row(f"Your answer: {card.answer}  {mark}"), border))
            else:
                lines.append((row(f"Skipped  {mark}"), border))
        lines.append((bot, border))
        return lines

    def _draw_card(self, lines, x_left, y_top) -> list[int]:
        ids = []
        for i, (text, color) in enumerate(lines):
            ids.append(self.deck.create_text(
                x_left, y_top + i * self.lineh,
                text=text, fill=color, font=self.font, anchor="nw",
            ))
        return ids

    def _redraw_current(self) -> None:
        for item in self._card_items:
            self.deck.delete(item)
        self._card_items = self._draw_card(
            self._card_render(self.state.cards[self.view_index]),
            self._card_x(), self.lineh,
        )

    # -- header HUD ---------------------------------------------------------

    def render_header(self) -> None:
        self.header.delete("all")
        p = self.state.player
        done, total = self.state.progress()
        accent = LEVEL_CHROME.get(self.state.level, PALETTE["cyan"])

        segs: list[tuple[str, str]] = [("┌─ ", accent)]
        segs.append(("Level: ", PALETTE["grey"]))
        segs.append((self.state.level.capitalize(), PALETTE["cyan"]))
        segs.append(("  ─  [", PALETTE["grey"]))
        for i in range(total):
            if self._square_flash and self._square_flash[0] == i:
                segs.append(self._square_flash[1:])
            elif i < done:
                segs.append(("■", PALETTE["green"]))
            else:
                segs.append(("□", PALETTE["grey"]))
        segs.append(("]  ─  ", PALETTE["grey"]))
        for i in range(p.max_lives):
            if self._heart_flash and self._heart_flash[0] == i:
                segs.append(self._heart_flash[1:])
            elif i < p.lives:
                segs.append(("♥", PALETTE["red"]))
            else:
                segs.append(("♡", PALETTE["grey"]))
        # XP only matters in a real run — Practice Mode awards none.
        if self.state.mode == "real":
            segs.append(("  ─  XP: ", PALETTE["grey"]))
            segs.append((str(p.exp), PALETTE["fg"]))
        segs.append((" ─┐", accent))

        x = self.charw
        y = self.lineh
        for text, color in segs:
            self.header.create_text(
                x, y, text=text, fill=color, font=self.font, anchor="w"
            )
            x += self.charw * len(text)

    # -- input handlers -----------------------------------------------------

    def _viewing_history(self) -> bool:
        return self.view_index != self.state.live_index()

    def _sync_input_state(self) -> None:
        live_pending = (
            not self.state.finished
            and not self._viewing_history()
            and self.state.live_card().result == "pending"
        )
        state = "normal" if live_pending else "disabled"
        for widget in (self.entry, self.submit_btn, self.skip_btn):
            widget.configure(state=state)
        self.hint_btn.configure(
            state=("normal" if live_pending and self.state.hints_left > 0 else "disabled"),
            text=f"Hint ({self.state.hints_left})",
        )
        self.back_btn.configure(state=("normal" if self.view_index > 0 else "disabled"))
        self.fwd_btn.configure(
            state=("normal" if self.view_index < self.state.live_index() else "disabled")
        )

    def _message(self, text: str, color: str = None) -> None:
        self.msg.configure(text="  " + text, fg=color or PALETTE["fg"])

    def _flash_center(self, text: str, color: str) -> None:
        """Pop a praise/taunt banner in the centre of the deck, briefly."""
        self._clear_popup()
        cx, cy = self.deck_w / 2, self.deck_h / 2
        tid = self.deck.create_text(
            cx, cy, text=text, fill=color, font=self.popup_font,
            anchor="center", justify="center", tags="popup",
        )
        bbox = self.deck.bbox(tid)
        if bbox:
            pad = self.charw
            rid = self.deck.create_rectangle(
                bbox[0] - pad, bbox[1] - pad // 2,
                bbox[2] + pad, bbox[3] + pad // 2,
                fill=CONFIG["background"], outline=color, width=2,
                tags="popup",
            )
            self.deck.tag_lower(rid, tid)
        self._popup_after = self.root.after(1500, self._clear_popup)

    def _clear_popup(self) -> None:
        if self._popup_after is not None:
            self.root.after_cancel(self._popup_after)
            self._popup_after = None
        self.deck.delete("popup")

    def _entry_left(self, event=None):
        if not self.entry.get():
            self.on_back()
            return "break"

    def _entry_right(self, event=None):
        if not self.entry.get():
            self.on_forward()
            return "break"

    def on_submit(self, event=None):
        if self._animating or self._viewing_history():
            return
        if self.state.live_card().result != "pending":
            return
        answer = self.entry.get()
        self.entry.delete(0, "end")
        res = self.state.submit(answer)
        if res["result"] in ("invalid", "none"):
            return
        self._animating = True
        if res["result"] == "correct":
            self.view_index = self.state.live_index()
            self._redraw_current()
            bonus = f", +{res['bonus']} streak" if res["bonus"] else ""
            self._flash_center(random.choice(data.PRAISE), PALETTE["green"])
            self._message(f"+{res['base']} XP{bonus}", PALETTE["green"])
            sq = res["square"]
            self._blink(self._set_square,
                        [(sq, "■", PALETTE["yellow"]), (sq, "■", PALETTE["green"])],
                        done=self._after_correct)
        else:
            self._redraw_current()
            self._flash_center(random.choice(data.TAUNT), PALETTE["red"])
            i = res["lost_index"]
            frames = [(i, "♥", PALETTE["yellow"]), (i, "♥", PALETTE["grey"]),
                      (i, "♡", PALETTE["grey"])]
            self._blink(self._set_heart, frames,
                        done=(self._game_over if res["dead"] else self._unlock))

    def on_hint(self, event=None):
        if self._animating or self._viewing_history():
            return
        res = self.state.use_hint()
        if not res["ok"]:
            self._message("No hints left for this level." if res.get("reason") == "none"
                          else "Not available.", PALETTE["yellow"])
            return
        self._redraw_current()
        self.render_header()
        self._sync_input_state()
        self._message("Hint revealed.", PALETTE["yellow"])

    def on_skip(self, event=None):
        if self._animating or self._viewing_history():
            return
        res = self.state.skip()
        if not res["ok"]:
            if res.get("reason") == "poor":
                self._message(f"Need {res['need']} XP to skip (you have {res['have']}).",
                              PALETTE["yellow"])
            return
        self._animating = True
        self.view_index = self.state.live_index()
        self._redraw_current()
        cost_note = f"  (−{SKIP_COST} XP)" if self.state.mode == "real" else ""
        self._message(f"Skipped.{cost_note}", PALETTE["grey"])
        sq = res["square"]
        self._blink(self._set_square,
                    [(sq, "■", PALETTE["yellow"]), (sq, "■", PALETTE["green"])],
                    done=self._after_correct)

    def on_back(self, event=None):
        if self._animating or self.view_index <= 0:
            return
        self._animating = True
        self.view_index -= 1
        self._slide(self.state.cards[self.view_index], -1, done=self._unlock)

    def on_forward(self, event=None):
        if self._animating or self.view_index >= self.state.live_index():
            return
        self._animating = True
        self.view_index += 1
        self._slide(self.state.cards[self.view_index], +1, done=self._unlock)

    # -- transitions after a resolved riddle --------------------------------

    def _after_correct(self):
        adv = self.state.advance()
        if adv["kind"] == "card":
            self._slide_to_live(+1, done=self._unlock)
        elif adv["kind"] == "level_up":
            self._apply_chrome(adv["level"])
            if adv["life_gained"]:
                gi = adv["gain_index"]
                self._blink(self._set_heart,
                            [(gi, "♡", PALETTE["yellow"]), (gi, "♥", PALETTE["yellow"]),
                             (gi, "♥", PALETTE["red"])],
                            done=lambda: self._slide_to_live(+1, done=self._unlock))
            else:
                self._slide_to_live(+1, done=self._unlock)
        else:  # win
            self._show_end()
            self._unlock()

    def _game_over(self):
        self._show_end()
        self._unlock()

    def _unlock(self):
        self._animating = False
        self.render_header()
        self._sync_input_state()
        if not self.state.finished and not self._viewing_history():
            self.entry.focus_set()

    # -- animation primitives (discrete .after frames, no easing) -----------

    def _set_heart(self, value):
        self._heart_flash = value

    def _set_square(self, value):
        self._square_flash = value

    def _blink(self, setter, frames, done=None, i=0):
        if not self._alive:
            return
        if i >= len(frames):
            setter(None)
            self.render_header()
            if done:
                done()
            return
        setter(frames[i])
        self.render_header()
        self.root.after(BLINK_MS, lambda: self._blink(setter, frames, done, i + 1))

    def _slide(self, new_card, direction, done=None):
        lines = self._card_render(new_card)
        new_items = self._draw_card(
            lines, self._card_x() + direction * self.deck_w, self.lineh
        )
        old_items = self._card_items
        step = -direction * self.deck_w / SLIDE_FRAMES

        def run(i):
            if not self._alive:
                return
            if i >= SLIDE_FRAMES:
                for item in old_items:
                    self.deck.delete(item)
                self._card_items = new_items
                if done:
                    done()
                return
            for item in old_items + new_items:
                self.deck.move(item, step, 0)
            self.root.after(SLIDE_MS, lambda: run(i + 1))

        run(0)

    def _slide_to_live(self, direction, done=None):
        self.view_index = self.state.live_index()
        self._slide(self.state.live_card(), direction, done=done)

    # -- chrome / end -------------------------------------------------------

    def _to_menu(self) -> None:
        if self.on_menu:
            self.on_menu()

    def teardown(self) -> None:
        """Stop pending animations so leftover .after callbacks are no-ops."""
        self._alive = False
        if self._popup_after is not None:
            self.root.after_cancel(self._popup_after)
            self._popup_after = None

    def _apply_chrome(self, level: str) -> None:
        self.chrome.configure(bg=LEVEL_CHROME.get(level, PALETTE["cyan"]))

    def _show_end(self) -> None:
        for item in self._card_items:
            self.deck.delete(item)
        won = self.state.outcome == "win"
        title = "★  THE VAULT OPENS  ★" if won else "✗  THE VAULT SEALS SHUT  ✗"
        color = PALETTE["green"] if won else PALETTE["red"]
        w = CONTENT_W
        rows = [("╔" + "═" * (w + 2) + "╗", color)]

        def row(text, c):
            return ("║ " + text[:w].ljust(w) + " ║", c)

        rows.append(row(title, color))
        rows.append(row("", color))
        for key, value in self.state.player.stats().items():
            rows.append(row(f"{key:16}: {value}", PALETTE["cyan"]))
        rows.append(("╚" + "═" * (w + 2) + "╝", color))
        self._card_items = self._draw_card(rows, self._card_x(), self.lineh)

        # Record a qualifying real run on the shared leaderboard.
        if self.state.mode == "real" and data.qualifies(self.state.player.exp):
            data.add_score(self.state.player.name, self.state.player.exp)
            self._message("New Top 5! Saved. Press ≡ Menu to return.",
                          PALETTE["green"])
        else:
            self._message("Press ≡ Menu to return.", PALETTE["fg"])


class App:
    """Top-level controller: the main menu and the screens it leads to.

    Mirrors the terminal menu — Start Run / Practice Mode / View Top 5 /
    Quit — swapping the window's contents between a menu, a running game,
    and the leaderboard on one root window.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.game: RiddlesGUI | None = None
        family = _resolve_font(root)
        self.font = tkfont.Font(family=family, size=CONFIG["font_size"])
        self.title_font = tkfont.Font(
            family=family, size=CONFIG["font_size"] + 6, weight="bold"
        )
        self.show_menu()

    # -- screen scaffolding -------------------------------------------------

    def _clear(self) -> None:
        if self.game is not None:
            self.game.teardown()
            self.game = None
        self.root.unbind("<Left>")
        self.root.unbind("<Right>")
        for widget in self.root.winfo_children():
            widget.destroy()

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

    def _menu_button(self, parent, label, desc, color, cmd) -> None:
        row = tk.Frame(parent, bg=CONFIG["background"])
        row.pack(fill="x", padx=60, pady=6)
        tk.Button(
            row, text=label, command=cmd, font=self.font, width=16,
            bg="#111111", fg=color, activebackground="#222222",
            activeforeground=color, relief="flat", bd=0, cursor="hand2", pady=8,
        ).pack(side="left")
        if desc:
            tk.Label(row, text=desc, font=self.font,
                     bg=CONFIG["background"], fg=PALETTE["grey"]).pack(
                side="left", padx=14)

    # -- screens ------------------------------------------------------------

    def show_menu(self) -> None:
        self._clear()
        c = self._screen(PALETTE["magenta"])
        self._title(c, "🧩  S P H I N X  🧩", PALETTE["cyan"])
        tk.Label(c, text="match wits with the sphinx", font=self.font,
                 bg=CONFIG["background"], fg=PALETTE["grey"]).pack(pady=(0, 2))
        tk.Label(c, text=f"v{__version__}", font=self.font,
                 bg=CONFIG["background"], fg=PALETTE["grey"]).pack(pady=(0, 20))
        self._menu_button(c, "Start Run", "Easy → Medium → Hard, one life pool",
                          PALETTE["green"], self.start_run)
        self._menu_button(c, "Practice Mode", "drill any level, no stakes",
                          PALETTE["cyan"], self.show_practice)
        self._menu_button(c, "View Top 5", "the leaderboard",
                          PALETTE["yellow"], self.show_leaderboard)
        self._menu_button(c, "Quit", "", PALETTE["red"], self.root.destroy)

    def show_practice(self) -> None:
        self._clear()
        c = self._screen(LEVEL_CHROME["easy"])
        self._title(c, "Practice — pick a level", PALETTE["cyan"])
        riddles = data.load_riddles()
        for level in data.LEVELS:
            self._menu_button(
                c, level.capitalize(), f"{len(riddles[level])} riddles",
                LEVEL_CHROME[level], lambda lv=level: self.start_practice(lv),
            )
        self._menu_button(c, "◀ Back", "", PALETTE["grey"], self.show_menu)

    def show_leaderboard(self) -> None:
        self._clear()
        c = self._screen(PALETTE["yellow"])
        self._title(c, "🏆  TOP 5 RIDDLERS", PALETTE["yellow"])
        entries = data.load_leaderboard()
        if not entries:
            tk.Label(c, text="No scores yet — be the first!", font=self.font,
                     bg=CONFIG["background"], fg=PALETTE["grey"]).pack(pady=12)
        else:
            for rank, (name, score) in enumerate(entries, 1):
                tk.Label(
                    c, text=f"{rank}.  {name[:16].ljust(16)}  {str(score).rjust(5)} XP",
                    font=self.font, bg=CONFIG["background"], fg=PALETTE["cyan"],
                ).pack(pady=2)
        tk.Label(c, text="", bg=CONFIG["background"]).pack(pady=6)
        self._menu_button(c, "◀ Back", "", PALETTE["grey"], self.show_menu)

    # -- launching a game ---------------------------------------------------

    def start_run(self) -> None:
        name = self._ask_name() or "Player"
        self._clear()
        state = RunState(data.load_riddles(), Player(name=name), mode="real")
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
    root = tk.Tk()
    root.title("Sphinx")
    root.configure(bg=CONFIG["background"])
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

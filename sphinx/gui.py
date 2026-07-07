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
import re
import tkinter as tk
import webbrowser
from pathlib import Path
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

# The run is a descent into the sphinx to uncover the secret sealed inside it.
# Each level gets a story header (title + one-line beat) above the riddle.
LEVEL_STORY = {
    "easy":   ("⟐ The Outer Halls ⟐",
               "Answer the riddles to step inside the sphinx."),
    "medium": ("⟐ The Inner Vault ⟐",
               "Deeper now — the secret stirs within."),
    "hard":   ("⟐ The Sphinx's Chamber ⟐",
               "One last riddle guards the secret. Take it."),
}

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

# Retro "framed photo" sphinx for the welcome screen. gui.py keeps its own
# copy of the silhouette on purpose — it never imports the terminal front-end
# — and swaps the eye glyph to make it blink on entry.
_SPHINX_ART = [
    '+-----------------------------------+',
    '|           _.--"""""""--._         |',
    '|          /   o      o   \\         |',
    '|          \\_     ^^     _/         |',
    '|            ___________            |',
    '|           /  _______  \\           |',
    '|          /  /       \\  \\          |',
    '|         /  /         \\  \\         |',
    '|   _____/  /           \\  \\_____   |',
    '|  |       /             \\       |  |',
    '|  |______/               \\______|  |',
    '|  ||====||               ||====||  |',
    '|  ||____||_______________||____||  |',
    '+-----------------------------------+',
]
_SPHINX_EYE_ROW = 2  # the only line that changes when the sphinx blinks


def _sphinx_face(eye: str) -> str:
    """The sphinx art with its eyes drawn as ``eye`` ('o' open, '-' shut)."""
    lines = list(_SPHINX_ART)
    lines[_SPHINX_EYE_ROW] = lines[_SPHINX_EYE_ROW].replace("o", eye)
    return "\n".join(lines)


_SPHINX_OPEN = _sphinx_face("o")
_SPHINX_SHUT = _sphinx_face("-")
SPHINX_COLOR = "#c9a24a"   # muted sandstone gold, a touch "aged photo"

# Inline Markdown spans handled by the About README renderer: **bold**,
# `code`, and [label](url) links.
_MD_INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


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
        self._xp_center = None     # (x, y) of the XP readout — for the -XP drop
        self._heart_centers: list = []  # (x, y) per heart — for the heart drop

        family = _resolve_font(root)
        self.font = tkfont.Font(family=family, size=CONFIG["font_size"])
        # Bold face for the praise/taunt banner that pops low over the deck on
        # every answer — sized modestly so it reads without dominating.
        self.popup_font = tkfont.Font(
            family=family, size=CONFIG["font_size"] + 5, weight="bold"
        )
        # Bold title for the per-level story header above the riddle.
        self.story_font = tkfont.Font(
            family=family, size=CONFIG["font_size"] + 3, weight="bold"
        )
        # Chunky, bold face for the progress markers so they read as satisfying
        # filled tiles, not thin glyphs.
        self.hud_font = tkfont.Font(
            family=family, size=CONFIG["font_size"] + 3, weight="bold"
        )
        # Face for the numbers/hearts that fly off the HUD (-65 XP, ♥).
        self.float_font = tkfont.Font(
            family=family, size=CONFIG["font_size"] + 2, weight="bold"
        )
        self.charw = self.font.measure("0")
        self.lineh = self.font.metrics("linespace")
        self.card_w_px = (CONTENT_W + 4) * self.charw
        self.deck_w = int(self.card_w_px + 6 * self.charw)
        self.deck_h = CARD_ROWS * self.lineh

        self._build_widgets()
        self._apply_chrome(self.state.level)
        self.render_story()
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
        self.content = content   # parent for transient fly-off overlays

        # Full-width HUD bar. It fills the window width; its contents are drawn
        # centered (see render_header), and it re-centers on resize.
        self.header = tk.Canvas(
            content, bg=bg, height=2 * self.lineh,
            width=self.deck_w, highlightthickness=0,
        )
        self.header.pack(fill="x", pady=(0, 4))
        self.header.bind("<Configure>", lambda e: self.render_header())

        # Per-level story header, tying each level to the descent narrative.
        story = tk.Frame(content, bg=bg)
        story.pack(fill="x", pady=(0, 6))
        self.story_title = tk.Label(story, font=self.story_font, bg=bg)
        self.story_title.pack()
        self.story_sub = tk.Label(story, font=self.font, bg=bg, fg=PALETTE["grey"])
        self.story_sub.pack()

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

    def render_story(self) -> None:
        """Refresh the per-level story header (title + one-line beat)."""
        title, sub = LEVEL_STORY.get(
            self.state.level, (self.state.level.capitalize(), ""))
        self.story_title.configure(
            text=title, fg=LEVEL_CHROME.get(self.state.level, PALETTE["cyan"]))
        self.story_sub.configure(text=sub)

    def render_header(self) -> None:
        """Draw the HUD as a full-width bar with its contents centered.

        Each segment carries its own font (progress tiles are chunkier), so the
        centering measures real pixel widths. The XP readout and each heart
        record their centre point, which the fly-off animations start from.
        """
        self.header.delete("all")
        p = self.state.player
        done, total = self.state.progress()
        accent = LEVEL_CHROME.get(self.state.level, PALETTE["cyan"])
        f, hud, grey = self.font, self.hud_font, PALETTE["grey"]

        # (text, color, font, tag) — tag marks the XP number and each heart.
        segs: list = [("Level ", grey, f, None),
                      (self.state.level.capitalize(), accent, f, None),
                      ("      ", grey, f, None)]
        for i in range(total):
            if self._square_flash and self._square_flash[0] == i:
                _, glyph, col = self._square_flash
                segs.append((glyph, col, hud, None))
            elif i < done:
                segs.append(("■", PALETTE["green"], hud, None))
            else:
                segs.append(("□", "#3a3a3a", hud, None))
            segs.append((" ", grey, hud, None))        # gap between tiles
        segs.append(("     ", grey, f, None))
        for i in range(p.max_lives):
            if self._heart_flash and self._heart_flash[0] == i:
                _, glyph, col = self._heart_flash
                segs.append((glyph, col, f, ("heart", i)))
            elif i < p.lives:
                segs.append(("♥", PALETTE["red"], f, ("heart", i)))
            else:
                segs.append(("♡", grey, f, ("heart", i)))
            segs.append((" ", grey, f, None))
        # XP only matters in a real run — Practice Mode awards none.
        if self.state.mode == "real":
            segs.append(("    XP ", grey, f, None))
            segs.append((str(p.exp), PALETTE["fg"], f, "xp"))

        width = self.header.winfo_width()
        if width <= 1:
            width = self.deck_w
        h = int(2 * self.lineh)
        self.header.create_rectangle(0, 0, width, h, fill="#0e0e0e", outline="")
        self.header.create_line(0, h - 2, width, h - 2, fill=accent, width=2)

        total_w = sum(fnt.measure(t) for t, _, fnt, _ in segs)
        x = max(self.charw, (width - total_w) / 2)
        y = self.lineh
        self._heart_centers = [None] * p.max_lives
        for text, color, fnt, tag in segs:
            self.header.create_text(
                x, y, text=text, fill=color, font=fnt, anchor="w")
            seg_w = fnt.measure(text)
            if tag == "xp":
                self._xp_center = (x + seg_w / 2, y)
            elif isinstance(tag, tuple):
                self._heart_centers[tag[1]] = (x + seg_w / 2, y)
            x += seg_w

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
        """Pop a praise/taunt banner low over the deck, briefly."""
        self._clear_popup()
        cx, cy = self.deck_w / 2, self.deck_h * 0.66
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

    # -- fly-off overlays (XP loss, lost heart) -----------------------------

    @staticmethod
    def _fade_hex(hex_color: str, factor: float) -> str:
        """Dim a hex colour toward the black background (1 → full, 0 → gone)."""
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"

    def _heart_pos(self, i: int) -> tuple:
        """Screen centre of heart ``i`` in the HUD, or (None, None)."""
        if 0 <= i < len(self._heart_centers) and self._heart_centers[i]:
            return self._heart_centers[i]
        return (None, None)

    def _square_pop(self, sq: int) -> list:
        """A brighter, more satisfying fill for a completed progress tile:
        white flash → yellow → settle green."""
        return [(sq, "■", "#ffffff"), (sq, "■", PALETTE["yellow"]),
                (sq, "■", PALETTE["green"])]

    def _float_off(self, text, color, cx, cy, done=None,
                   steps=16, dy=7, delay=38) -> None:
        """Drop ``text`` down from (cx, cy) over the content, fading it out,
        then remove it — the shared motion for the -XP and lost-heart effects.
        Calls ``done`` once when finished (immediately if there's no anchor)."""
        if not self._alive or cx is None:
            if done:
                done()
            return
        lbl = tk.Label(self.content, text=text, font=self.float_font,
                       bg=CONFIG["background"], fg=color)
        lbl.place(x=int(cx), y=int(cy), anchor="center")

        def frame(i):
            if not self._alive:
                return
            if i >= steps:
                lbl.destroy()
                if done:
                    done()
                return
            try:
                lbl.place_configure(y=int(cy) + i * dy)
                lbl.configure(fg=self._fade_hex(color, 1 - i / steps))
            except tk.TclError:
                return
            self.root.after(delay, lambda: frame(i + 1))

        frame(0)

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
        # Typing "hint" or "skip" is a shortcut for the matching button, so the
        # keyboard-only player never has to reach for the mouse. Routed here so
        # it works from both the Answer button and the Enter key.
        command = answer.strip().lower()
        if command == "hint":
            self.on_hint()
            return
        if command == "skip":
            self.on_skip()
            return
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
            self._blink(self._set_square, self._square_pop(res["square"]),
                        done=self._after_correct)
        else:
            self._redraw_current()
            self._flash_center(random.choice(data.TAUNT), PALETTE["red"])
            # The lost heart empties in the HUD, then a red heart drops away and
            # fades — more visceral than the old in-place blink.
            i = res["lost_index"]
            self.render_header()
            cx, cy = self._heart_pos(i)
            self._float_off("−♥", PALETTE["red"], cx, cy,
                            done=(self._game_over if res["dead"] else self._unlock))

    def on_hint(self, event=None):
        if self._animating or self._viewing_history():
            return
        res = self.state.use_hint()
        if not res["ok"]:
            if res.get("reason") == "poor":
                self._message(f"Need {res['need']} XP for a hint (you have {res['have']}).",
                              PALETTE["yellow"])
            else:
                self._message("No hints left for this level." if res.get("reason") == "none"
                              else "Not available.", PALETTE["yellow"])
            return
        self._redraw_current()
        self.render_header()
        self._sync_input_state()
        cost = res.get("cost") or 0
        if cost:
            # Drop a "-65 XP" off the (now updated) XP readout.
            cx, cy = self._xp_center or (None, None)
            self._float_off(f"−{cost} XP", PALETTE["red"], cx, cy)
        cost_note = f"  (−{cost} XP)" if cost else ""
        self._message(f"Hint revealed.{cost_note}", PALETTE["yellow"])

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
        self._blink(self._set_square, self._square_pop(res["square"]),
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
            self.render_story()
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
        self._key_bindings: list[str] = []  # root key shortcuts for the live screen
        family = _resolve_font(root)
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
        # The riddle interface's natural size, measured once. Every screen uses
        # this one default size, so the window never jumps between screens.
        self._game_size = self._measure_game_size()
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

    def _menu_button(self, parent, label, desc, color, cmd, key=None) -> None:
        row = tk.Frame(parent, bg=CONFIG["background"])
        row.pack(fill="x", padx=60, pady=6)
        if key is not None:
            # A dim shortcut digit to the left of the button — quiet enough not
            # to clutter the screen, but a hint that the number key works too.
            tk.Label(row, text=str(key), font=self.font, width=2,
                     bg=CONFIG["background"], fg=PALETTE["grey"]).pack(side="left")
            self._bind_key(key, cmd)
        tk.Button(
            row, text=label, command=cmd, font=self.font, width=16,
            bg="#111111", fg=color, activebackground="#222222",
            activeforeground=color, relief="flat", bd=0, cursor="hand2", pady=8,
        ).pack(side="left")
        if desc:
            tk.Label(row, text=desc, font=self.font,
                     bg=CONFIG["background"], fg=PALETTE["grey"]).pack(
                side="left", padx=14)

    def _bind_key(self, digit: int, cmd) -> None:
        """Bind a number key (top-row and keypad) to a menu action, tracking it
        so ``_clear`` can release it when the screen changes."""
        for seq in (f"<Key-{digit}>", f"<KP_{digit}>"):
            self.root.bind(seq, lambda event, c=cmd: c())
            self._key_bindings.append(seq)

    def _bind_back(self, cmd) -> None:
        """Bind Backspace as a 'back' shortcut for the current sub-screen,
        tracked so ``_clear`` releases it on exit. Safe on screens whose only
        text widgets are read-only, so the key is never needed for editing."""
        self.root.bind("<BackSpace>", lambda event: cmd())
        self._key_bindings.append("<BackSpace>")

    # -- screens ------------------------------------------------------------

    def show_menu(self) -> None:
        self._clear()
        c = self._screen(PALETTE["magenta"])
        self._title(c, "🧩  S P H I N X  🧩", PALETTE["cyan"])
        tk.Label(c, text="Do you have what it take to enter the sphinx?", font=self.font,
                 bg=CONFIG["background"], fg=PALETTE["grey"]).pack(pady=(0, 8))

        # Retro sphinx "photo" — blinks twice, then settles, on every entry.
        sphinx = tk.Label(c, text=_SPHINX_OPEN, font=self.font, justify="center",
                          bg=CONFIG["background"], fg=SPHINX_COLOR)
        sphinx.pack(pady=(0, 14))
        self._blink_sphinx(sphinx, [
            (_SPHINX_OPEN, 550), (_SPHINX_SHUT, 120),
            (_SPHINX_OPEN, 200), (_SPHINX_SHUT, 120), (_SPHINX_OPEN, 50),
        ])

        # Version, pinned quietly to the bottom edge (small, dim).
        tk.Label(c, text=f"- version {__version__} -", font=self.small_font,
                 bg=CONFIG["background"], fg="#555555").pack(side="bottom",
                                                             pady=(0, 12))

        self._menu_button(c, "Start Run", "Easy → Medium → Hard, one life pool",
                          PALETTE["green"], self.start_run, key=1)
        self._menu_button(c, "Practice Mode", "drill any level, no stakes",
                          PALETTE["cyan"], self.show_practice, key=2)
        self._menu_button(c, "View Top 5", "the leaderboard",
                          PALETTE["yellow"], self.show_leaderboard, key=3)
        self._menu_button(c, "About", "the project, and how to reach me",
                          PALETTE["blue"], self.show_about, key=4)
        self._menu_button(c, "Quit", "", PALETTE["red"], self.root.destroy, key=5)

    def _blink_sphinx(self, label, frames, i: int = 0) -> None:
        """Play the sphinx's wake-up blink, stopping quietly if the label is
        gone (the user left the menu before it finished)."""
        try:
            text, delay = frames[i]
            label.configure(text=text)
        except (tk.TclError, IndexError):
            return
        label.after(delay, lambda: self._blink_sphinx(label, frames, i + 1))

    def show_practice(self) -> None:
        self._clear()
        c = self._screen(LEVEL_CHROME["easy"])
        self._title(c, "Practice — pick a level", PALETTE["cyan"])
        riddles = data.load_riddles()
        for i, level in enumerate(data.LEVELS, start=1):
            self._menu_button(
                c, level.capitalize(), f"{len(riddles[level])} riddles",
                LEVEL_CHROME[level], lambda lv=level: self.start_practice(lv), key=i,
            )
        self._menu_button(c, "◀ Back", "  (or press Backspace)",
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
            for rank, (name, score) in enumerate(entries, 1):
                tk.Label(
                    c, text=f"{rank}.  {name[:16].ljust(16)}  {str(score).rjust(5)} XP",
                    font=self.font, bg=CONFIG["background"], fg=PALETTE["cyan"],
                ).pack(pady=2)
        tk.Label(c, text="", bg=CONFIG["background"]).pack(pady=6)
        self._menu_button(c, "◀ Back", "  (or press Backspace)",
                          PALETTE["grey"], self.show_menu)
        self._bind_back(self.show_menu)

    def show_about(self) -> None:
        self._clear()
        c = self._screen(PALETTE["blue"])
        self._title(c, "About Sphinx", PALETTE["cyan"])

        # How to reach the author — a clickable GitHub link.
        github = "github.com/YuvalBogo"
        link = tk.Label(c, text=f"⤷  {github}", font=self.font,
                        bg=CONFIG["background"], fg=PALETTE["magenta"],
                        cursor="hand2")
        link.pack(pady=(0, 10))
        link.bind("<Button-1>", lambda e: self._open_url(f"https://{github}"))

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
        self._render_markdown(readme, self._read_readme())
        readme.configure(state="disabled")   # read-only

        # ↑ / ↓ scroll the README (it is read-only, so the arrows are free to
        # drive the view). Tracked so _clear releases them on exit.
        for seq, step in (("<Up>", -2), ("<Down>", 2)):
            self.root.bind(seq, lambda e, s=step: readme.yview_scroll(s, "units"))
            self._key_bindings.append(seq)

        # Fine print — deliberately quiet (small, grey), easy to miss.
        tk.Label(c, text="© Yuval Bogomoletz — all rights reserved",
                 font=self.small_font, bg=CONFIG["background"],
                 fg=PALETTE["grey"]).pack(pady=(6, 4))
        self._menu_button(c, "◀ Back", "  (↑ ↓ scroll · Backspace to exit)",
                          PALETTE["grey"], self.show_menu)
        self._bind_back(self.show_menu)

    @staticmethod
    def _read_readme() -> str:
        """Load the project README (one level up from this package)."""
        path = Path(__file__).resolve().parent.parent / "README.md"
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return "README.md could not be found."

    def _render_markdown(self, widget: tk.Text, md: str) -> None:
        """Render Markdown into ``widget`` with styled Text tags — a small,
        dependency-free renderer covering what the README uses: headings,
        fenced code blocks, bullets, blockquotes, rules, and inline
        **bold** / `code` / [label](url)."""
        p, mf = PALETTE, self.md_fonts
        widget.tag_configure("h1", font=mf["h1"], foreground=p["cyan"],
                             spacing1=12, spacing3=6)
        widget.tag_configure("h2", font=mf["h2"], foreground=p["magenta"],
                             spacing1=10, spacing3=4)
        widget.tag_configure("h3", font=mf["h3"], foreground=p["yellow"],
                             spacing1=8, spacing3=3)
        widget.tag_configure("bold", font=mf["bold"], foreground=p["fg"])
        widget.tag_configure("code", foreground=p["green"], background="#161616")
        widget.tag_configure("codeblock", foreground=p["green"],
                             background="#101010", lmargin1=24, lmargin2=24)
        widget.tag_configure("bullet", foreground=p["cyan"],
                             lmargin1=18, lmargin2=36)
        widget.tag_configure("quote", foreground=p["grey"],
                             lmargin1=20, lmargin2=20)
        widget.tag_configure("rule", foreground="#3a3a3a")
        self._md_link = 0

        in_code = False
        for raw in md.splitlines():
            stripped = raw.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                widget.insert("end", raw + "\n", ("codeblock",))
            elif stripped in ("---", "***", "___"):
                widget.insert("end", "─" * 46 + "\n", ("rule",))
            elif stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                tag = {1: "h1", 2: "h2", 3: "h3"}.get(level, "h3")
                self._insert_inline(widget, stripped[level:].strip() + "\n", (tag,))
            elif stripped.startswith(">"):
                self._insert_inline(widget, "  " + stripped[1:].strip() + "\n",
                                    ("quote",))
            elif stripped.startswith(("- ", "* ")):
                widget.insert("end", "   •  ", ("bullet",))
                self._insert_inline(widget, raw.split(None, 1)[1] + "\n", ("bullet",))
            else:
                self._insert_inline(widget, raw + "\n", ())

    def _insert_inline(self, widget: tk.Text, text: str, base: tuple) -> None:
        """Insert one line, styling inline **bold** / `code` / [label](url)."""
        for part in _MD_INLINE.split(text):
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                widget.insert("end", part[2:-2], base + ("bold",))
            elif part.startswith("`") and part.endswith("`"):
                widget.insert("end", part[1:-1], base + ("code",))
            elif part.startswith("[") and "](" in part:
                label = part[1:part.index("](")]
                url = part[part.index("](") + 2:-1]
                self._md_link += 1
                tag = f"mdlink{self._md_link}"
                widget.tag_configure(tag, foreground=PALETTE["blue"], underline=True)
                widget.tag_bind(tag, "<Button-1>",
                                lambda e, u=url: self._open_url(u))
                widget.tag_bind(tag, "<Enter>",
                                lambda e: widget.configure(cursor="hand2"))
                widget.tag_bind(tag, "<Leave>",
                                lambda e: widget.configure(cursor=""))
                widget.insert("end", label, base + (tag,))
            else:
                widget.insert("end", part, base)

    @staticmethod
    def _open_url(url: str) -> None:
        """Open a link in the default browser, ignoring any launch failure."""
        try:
            webbrowser.open(url)
        except Exception:
            pass

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

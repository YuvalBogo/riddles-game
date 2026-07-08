"""The live game screen for the tkinter front-end.

``RiddlesGUI`` renders one run: the riddle-card deck, the HUD (progress tiles,
hearts, XP), the per-level story header and banner, chunky un-eased animations,
and input handling. It is pure presentation over ``state.RunState`` — the
flow/scoring logic lives there — and it never imports the terminal front-end.
"""

from __future__ import annotations

import random
import tkinter as tk
from tkinter import font as tkfont

from .. import data
from ..player import SKIP_COST
from .assets import easy_banner
from .state import CONTENT_W, RunState
from .theme import CONFIG, LEVEL_CHROME, PALETTE, resolve_font

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
CARD_ROWS = 22   # deck canvas height in text rows (fits the tallest card)

# The "back to menu" confirmation panel drops in from above the deck and
# retracts the same way — a touch smoother than the card slide, since it is a
# solid block of chrome rather than text.
CONFIRM_FRAMES = 8
CONFIRM_MS = 16


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
        self._confirm = None       # the "back to menu?" panel, while it's up
        self._confirm_y = 0        # its resting y — the retract slide starts here

        family = resolve_font(root)
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
        # A quieter face for fine print — the confirmation panel's key hints.
        self.small_font = tkfont.Font(family=family, size=CONFIG["font_size"] - 4)
        self.charw = self.font.measure("0")
        self.lineh = self.font.metrics("linespace")
        self.card_w_px = (CONTENT_W + 4) * self.charw
        self.deck_w = int(self.card_w_px + 6 * self.charw)
        self.deck_h = CARD_ROWS * self.lineh

        self._build_widgets()
        self._apply_chrome(self.state.level)
        self.render_story()
        self.render_banner()
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

        # Per-level banner image, sitting between the story and the deck. Only
        # the Easy level ("the outer walls") has art; render_banner packs it in
        # or hides it as the level changes. Created unpacked.
        self.banner = tk.Label(content, bg=bg)

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
        # Esc mirrors the ≡ Menu button, the same "go back" key every other
        # screen answers to. It reaches here even from the entry, which has no
        # binding of its own for it.
        self.root.bind("<Escape>", self._to_menu)

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

    def render_banner(self) -> None:
        """Show the current level's banner above the deck, or hide it on levels
        with no art. Only Easy ('the outer walls') has an image today, sized to
        fit the screen; Medium and Hard fall through to a hidden banner."""
        img = easy_banner() if self.state.level == "easy" else None
        if img is not None:
            self.banner.configure(image=img)
            self.banner.image = img   # keep a reference against Tk GC
            self.banner.pack(before=self.deck, pady=(0, 8))
        else:
            self.banner.pack_forget()
            self.banner.image = None

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

    def _busy(self) -> bool:
        """True while an animation is mid-flight or the confirmation panel is
        up — either way the deck is not the player's to touch."""
        return self._animating or self._confirm is not None

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
        if self._busy() or self._viewing_history():
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
        if self._busy() or self._viewing_history():
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
        if self._busy() or self._viewing_history():
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
        if self._busy() or self.view_index <= 0:
            return
        self._animating = True
        self.view_index -= 1
        self._slide(self.state.cards[self.view_index], -1, done=self._unlock)

    def on_forward(self, event=None):
        if self._busy() or self.view_index >= self.state.live_index():
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
            self.render_banner()   # Easy banner disappears past the outer walls
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
        # An animation that lands while the confirmation panel is up must leave
        # the focus on the panel's buttons, not snatch it back to the entry.
        if (not self.state.finished and not self._viewing_history()
                and self._confirm is None):
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

    def _to_menu(self, event=None) -> None:
        """The ≡ Menu button and the Esc key — one action, two ways in.

        Mid-run, leaving throws the run away, so ask first. With the question
        already on screen, Esc (or ≡ Menu again) backs out of it, keeping the
        key a consistent "go back one step". Once the run is over there is
        nothing left to lose, so return to the menu straight away.
        """
        if self._confirm is not None:
            self._close_confirm()
        elif self.state.finished:
            self._leave()
        else:
            self._open_confirm()

    def _leave(self) -> None:
        if self.on_menu:
            self.on_menu()

    # -- "back to menu?" confirmation panel ---------------------------------

    def _open_confirm(self) -> None:
        """Drop a modal confirmation panel down over the deck."""
        self._clear_popup()
        bg, accent = CONFIG["background"], PALETTE["magenta"]

        panel = tk.Frame(self.content, bg=accent)   # accent reads as a 2-px frame
        self._confirm = panel
        inner = tk.Frame(panel, bg=bg)
        inner.pack(padx=2, pady=2)
        tk.Label(inner, text="Are you sure you want to go back to menu?",
                 font=self.font, bg=bg, fg=PALETTE["fg"]).pack(padx=30, pady=(22, 4))
        tk.Label(inner, text="This run will be lost.", font=self.font,
                 bg=bg, fg=PALETTE["grey"]).pack(pady=(0, 18))

        row = tk.Frame(inner, bg=bg)
        row.pack()

        def choice(text, cmd, color):
            # The highlight ring is the only cue for a keyboard player: black
            # against the black card while the button is idle, lit in the
            # button's own colour the moment it takes focus.
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

        yes = choice("Yes — Menu", self._confirm_yes, PALETTE["red"])
        keep = choice("No — Keep going", self._close_confirm, PALETTE["cyan"])

        def focus_on(btn):
            def handler(_event=None):
                btn.focus_set()
                return "break"   # don't fall through to the deck's ◀ ▶ binding
            return handler

        # ← and → land on the button that sits that way on screen.
        for btn in (yes, keep):
            btn.bind("<Left>", focus_on(yes))
            btn.bind("<Right>", focus_on(keep))
        keep.focus_set()   # the safe choice starts under Return and Space

        tk.Label(inner, text="← → choose  ·  Enter to confirm  ·  Esc to cancel",
                 font=self.small_font, bg=bg,
                 fg=PALETTE["grey"]).pack(pady=(16, 20))

        # Sized before it is placed, so the slide knows where it comes to rest:
        # centred over the deck, having fallen in from just above the content.
        panel.update_idletasks()
        h = panel.winfo_reqheight()
        self._confirm_y = self.deck.winfo_y() + max(0, (self.deck_h - h) // 2)
        panel.place(relx=0.5, y=-h, anchor="n")
        self._slide_panel(-h, self._confirm_y)

    def _confirm_yes(self) -> None:
        self._close_confirm(done=self._leave)

    def _close_confirm(self, done=None) -> None:
        """Retract the panel upward, drop it, then run ``done``."""
        panel = self._confirm
        if panel is None:
            return
        h = panel.winfo_height() or panel.winfo_reqheight()

        def finish():
            panel.destroy()
            self._confirm = None
            if done:
                done()
                return
            self._sync_input_state()
            if not self.state.finished and not self._viewing_history():
                self.entry.focus_set()

        self._slide_panel(self._confirm_y, -h, done=finish)

    def _slide_panel(self, y_from, y_to, done=None, i=1) -> None:
        """Walk the panel from ``y_from`` to ``y_to`` in chunky, even steps."""
        if not self._alive or self._confirm is None:
            return
        y = y_from + (y_to - y_from) * i / CONFIRM_FRAMES
        try:
            self._confirm.place_configure(y=int(y))
        except tk.TclError:
            return
        if i >= CONFIRM_FRAMES:
            if done:
                done()
            return
        self.root.after(
            CONFIRM_MS, lambda: self._slide_panel(y_from, y_to, done, i + 1))

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
            self._message("New Top 5! Saved. Press ≡ Menu (or Esc) to return.",
                          PALETTE["green"])
        else:
            self._message("Press ≡ Menu (or Esc) to return.", PALETTE["fg"])

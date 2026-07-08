"""A tiny, dependency-free Markdown renderer for the About screen.

Renders the project README into a Tk ``Text`` widget using styled tags, in the
app's palette — covering what the README actually uses: headings, fenced code
blocks, bullets, blockquotes, rules, and inline **bold** / `code` /
[label](url). Also owns reading the README and opening links in a browser.
"""

from __future__ import annotations

import re
import tkinter as tk
import webbrowser
from pathlib import Path

from .theme import PALETTE

# Inline spans handled below: **bold**, `code`, and [label](url) links.
INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def open_url(url: str) -> None:
    """Open a link in the default browser, ignoring any launch failure."""
    try:
        webbrowser.open(url)
    except Exception:
        pass


def read_readme() -> str:
    """Load the project README (at the repository root)."""
    path = Path(__file__).resolve().parent.parent.parent / "README.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "README.md could not be found."


def render(widget: tk.Text, md: str, fonts: dict) -> None:
    """Render Markdown ``md`` into ``widget`` with styled Text tags. ``fonts``
    supplies the ``h1``/``h2``/``h3``/``bold`` faces."""
    p = PALETTE
    widget.tag_configure("h1", font=fonts["h1"], foreground=p["cyan"],
                         spacing1=12, spacing3=6)
    widget.tag_configure("h2", font=fonts["h2"], foreground=p["magenta"],
                         spacing1=10, spacing3=4)
    widget.tag_configure("h3", font=fonts["h3"], foreground=p["yellow"],
                         spacing1=8, spacing3=3)
    widget.tag_configure("bold", font=fonts["bold"], foreground=p["fg"])
    widget.tag_configure("code", foreground=p["green"], background="#161616")
    widget.tag_configure("codeblock", foreground=p["green"],
                         background="#101010", lmargin1=24, lmargin2=24)
    widget.tag_configure("bullet", foreground=p["cyan"],
                         lmargin1=18, lmargin2=36)
    widget.tag_configure("quote", foreground=p["grey"],
                         lmargin1=20, lmargin2=20)
    widget.tag_configure("rule", foreground="#3a3a3a")
    links = [0]   # mutable counter for unique per-link tag names

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
            _insert_inline(widget, stripped[level:].strip() + "\n", (tag,), links)
        elif stripped.startswith(">"):
            _insert_inline(widget, "  " + stripped[1:].strip() + "\n",
                           ("quote",), links)
        elif stripped.startswith(("- ", "* ")):
            widget.insert("end", "   •  ", ("bullet",))
            _insert_inline(widget, raw.split(None, 1)[1] + "\n", ("bullet",), links)
        else:
            _insert_inline(widget, raw + "\n", (), links)


def _insert_inline(widget: tk.Text, text: str, base: tuple, links: list) -> None:
    """Insert one line, styling inline **bold** / `code` / [label](url)."""
    for part in INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            widget.insert("end", part[2:-2], base + ("bold",))
        elif part.startswith("`") and part.endswith("`"):
            widget.insert("end", part[1:-1], base + ("code",))
        elif part.startswith("[") and "](" in part:
            label = part[1:part.index("](")]
            url = part[part.index("](") + 2:-1]
            links[0] += 1
            tag = f"mdlink{links[0]}"
            widget.tag_configure(tag, foreground=PALETTE["blue"], underline=True)
            widget.tag_bind(tag, "<Button-1>", lambda e, u=url: open_url(u))
            widget.tag_bind(tag, "<Enter>",
                            lambda e: widget.configure(cursor="hand2"))
            widget.tag_bind(tag, "<Leave>",
                            lambda e: widget.configure(cursor=""))
            widget.insert("end", label, base + (tag,))
        else:
            widget.insert("end", part, base)

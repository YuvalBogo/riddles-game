"""Image assets for the GUI.

Loads the pixel-art PNGs in ``sphinx/images`` and scales the Easy-level
banner to a height the app picks at startup (see ``App._compute_layout``).
The source files are pre-sized with a solid-black background, so they load
natively via Tk's ``PhotoImage`` (no dependency) and sit seamlessly on the
black UI. A returned ``PhotoImage`` must be kept referenced by its widget or
Tk garbage-collects the pixels, so callers hold their own reference.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

_IMAGE_DIR = Path(__file__).resolve().parent / "images"
IMAGE_FOR = {
    "menu": "sphinx_start_menu.png",     # welcome screen — the sphinx bust
    "about": "sphinx_with_friends.png",  # About screen — the four canopic jars
    "easy": "outer_walls_wide.png",      # Easy level banner — the outer walls
}
_IMAGE_CACHE: dict[str, "tk.PhotoImage | None"] = {}

# Display height (px) for the Easy banner, set by the app from the screen size.
# 0 hides it. Banners are cached per height.
_BANNER_H = 0
_BANNER_CACHE: dict[int, "tk.PhotoImage | None"] = {}


def load_image(key: str):
    """Return the cached PhotoImage for a screen ``key`` (see ``IMAGE_FOR``),
    or ``None`` if the file is missing or Tk cannot decode it — every caller
    degrades gracefully to a text-only screen."""
    if key in _IMAGE_CACHE:
        return _IMAGE_CACHE[key]
    try:
        img = tk.PhotoImage(file=str(_IMAGE_DIR / IMAGE_FOR[key]))
    except (tk.TclError, KeyError):
        img = None
    _IMAGE_CACHE[key] = img
    return img


def _scaled_photo(path, target_h: int):
    """A PhotoImage of ``path`` scaled to ``target_h`` px tall (aspect kept).

    Prefers Pillow to resample cleanly — it writes a temp PNG that Tk then
    loads, so ``ImageTk`` isn't required — and falls back to Tk's integer
    ``subsample`` (coarser), then the unscaled image. ``None`` if unloadable.
    """
    try:
        import os
        import tempfile
        from PIL import Image
        im = Image.open(path)
        w, h = im.size
        if 0 < target_h < h:
            im = im.resize((max(1, round(w * target_h / h)), target_h), Image.LANCZOS)
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            im.save(tmp, optimize=True)
            return tk.PhotoImage(file=tmp)
        finally:
            os.unlink(tmp)
    except Exception:
        pass
    try:
        img = tk.PhotoImage(file=str(path))
        if target_h and target_h < img.height():
            img = img.subsample(max(1, round(img.height() / target_h)))
        return img
    except tk.TclError:
        return None


def natural_banner_height() -> int:
    """Pixel height of the Easy banner at its native size, or 0 if unloadable —
    the ceiling the app scales down from."""
    img = load_image("easy")
    return img.height() if img is not None else 0


def set_banner_height(px: int) -> None:
    """Choose the display height for the Easy banner (0 hides it)."""
    global _BANNER_H
    _BANNER_H = px


def easy_banner():
    """The Easy-level banner scaled to the current height, or ``None`` when
    there's no room for it on this screen."""
    if _BANNER_H <= 0:
        return None
    if _BANNER_H not in _BANNER_CACHE:
        _BANNER_CACHE[_BANNER_H] = _scaled_photo(
            _IMAGE_DIR / IMAGE_FOR["easy"], _BANNER_H)
    return _BANNER_CACHE[_BANNER_H]

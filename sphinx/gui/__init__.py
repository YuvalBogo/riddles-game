"""tkinter GUI front-end for Sphinx.

An alternate skin over the same engine (``Player`` / ``Riddle`` / ``data``).
Submodules: ``app`` (the controller + entry), ``game`` (the live screen),
``state`` (run flow), ``theme`` / ``assets`` / ``widgets`` / ``markdown``.
``main`` is re-exported here so ``from sphinx.gui import main`` keeps working.
"""

from .app import main

__all__ = ["main"]

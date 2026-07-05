#!/usr/bin/env python3
"""Launch the experimental tkinter GUI: ``python play_gui.py``.

Requires tkinter (Fedora: ``sudo dnf install python3-tkinter``). The terminal
version (``python play.py`` / ``python -m riddles``) is unaffected by this.
"""

import sys

try:
    import tkinter  # noqa: F401
except ModuleNotFoundError:
    sys.exit(
        "tkinter is not installed.\n"
        "  Fedora/RHEL : sudo dnf install python3-tkinter\n"
        "  Debian/Ubuntu: sudo apt install python3-tk"
    )

from riddles.gui import main

if __name__ == "__main__":
    main()

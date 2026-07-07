#!/usr/bin/env python3
"""Single launcher for Riddles 2.0.

    python play.py                   # ask whether to play in terminal or GUI
    python play.py -t / --terminal   # terminal (text) version
    python play.py -g / --gui        # GUI (tkinter) version
"""

from riddles.__main__ import main

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Single launcher for Sphinx.

    python play.py                      # GUI (default)
    python play.py -g / --gui           # GUI (tkinter) version
    python play.py -t / --terminal      # terminal (text) version
    python play.py -i / --interactive   # ask which one (also -c / --choose)
"""

from sphinx.__main__ import main

if __name__ == "__main__":
    main()

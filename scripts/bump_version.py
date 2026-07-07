#!/usr/bin/env python3
"""Bump the game's Semantic Version (MAJOR.MINOR.PATCH).

The single source of truth is ``__version__`` in ``riddles/__init__.py``;
this script reads it, increments it, and writes it back.

Usage:
    python scripts/bump_version.py            # PATCH:  2.0.0 -> 2.0.1
    python scripts/bump_version.py --minor    # MINOR:  2.0.5 -> 2.1.0
    python scripts/bump_version.py --major    # MAJOR:  2.4.2 -> 3.0.0

Dependency-free: plain regex on the one line that defines __version__.
No git tagging is done here — see the "Versioning" section of README.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# riddles/__init__.py lives one directory up from scripts/.
INIT_PATH = Path(__file__).resolve().parent.parent / "riddles" / "__init__.py"

# Matches:  __version__ = "2.0.0"   (single or double quotes)
_VERSION_RE = re.compile(
    r'^(?P<prefix>__version__\s*=\s*["\'])(?P<ver>\d+\.\d+\.\d+)(?P<suffix>["\'])',
    re.MULTILINE,
)


def bump(version: str, part: str) -> str:
    """Return ``version`` with the given part ('major'|'minor'|'patch') bumped,
    resetting the lower-order parts to 0."""
    major, minor, patch = (int(n) for n in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bump the game version.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--major", action="store_true",
                       help="bump MAJOR, reset MINOR and PATCH to 0")
    group.add_argument("--minor", action="store_true",
                       help="bump MINOR, reset PATCH to 0")
    args = parser.parse_args(argv)
    part = "major" if args.major else "minor" if args.minor else "patch"

    text = INIT_PATH.read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    if not match:
        sys.exit(f"Could not find __version__ = \"X.Y.Z\" in {INIT_PATH}")

    old = match.group("ver")
    new = bump(old, part)
    text = text[:match.start()] + match.group("prefix") + new + \
        match.group("suffix") + text[match.end():]
    INIT_PATH.write_text(text, encoding="utf-8")

    print(f"Version bumped: {old} -> {new}")


if __name__ == "__main__":
    main()

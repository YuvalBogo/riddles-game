# Contributing to Sphinx

Bug reports, fixes and new riddles are all welcome. This file describes how the
project is put together, so a change lands where it belongs.

## Getting set up

No dependencies to install, no virtualenv required:

```bash
git clone https://github.com/YuvalBogo/riddles-game.git
cd riddles-game
python play.py --terminal      # the terminal version needs nothing at all
python play.py                 # the GUI needs tkinter
```

`tkinter` is standard library, but Linux distributions package it separately
(`python3-tkinter` on Fedora, `python3-tk` on Debian and Ubuntu). Running
`./install.sh` will offer to install it for you.

## Project layout

```
riddles-game/
├── play.py                    # single launcher (-g gui / -t terminal / -i choose)
├── install.sh                 # Linux installer: <prefix>/bin/sphinx + desktop entry
├── ABOUT.md                   # rendered by the GUI's About screen — see below
├── scripts/
│   └── bump_version.py        # manual SemVer bump helper
└── sphinx/
    ├── __init__.py            # __version__ — the single source of truth
    ├── __main__.py            # front-end dispatch (terminal / GUI) + flags
    ├── riddle.py              # Riddle models (+ from_dict)   ← shared engine
    ├── player.py              # Player: lives, XP, streak, stats  ← shared engine
    ├── data.py                # content + leaderboard loading  ← shared engine
    ├── ui.py                  # terminal rendering: colors, banners, input
    ├── game.py                # terminal flow: real & practice loops
    ├── gui/
    │   ├── app.py             # window, screens, wiring
    │   ├── game.py            # GUI game flow
    │   ├── state.py           # GUI state (imports no tkinter)
    │   ├── theme.py           # palette and fonts
    │   ├── widgets.py         # small reusable widgets
    │   ├── assets.py          # image loading and scaling
    │   └── markdown.py        # the tiny Markdown renderer for About
    ├── images/                # banners and artwork
    └── content/
        └── riddles.json       # all riddle content (data, not code)
```

The **leaderboard is deliberately not in this tree.** It is written to the
player's own data directory (`~/.local/share/Sphinx/leaderboard.json`, or
`%APPDATA%\Sphinx\` on Windows) so that it survives reinstalls, and so that a
copy of the game installed somewhere read-only — `/usr/local`, or the temporary
directory a packaged `.exe` unpacks into — can still record a score. `seen.json`
lives beside it.

### How a run is drawn

`load_riddles()` returns the whole pool. Practice Mode drills it directly; a
real run calls `draw_run()`, which takes `RIDDLES_PER_LEVEL` from each level.

The ids it hands out are remembered in `seen.json`, so the next run reaches for
riddles the last one did not use. When a level has too few unseen riddles left
it starts over — but only back as far as the *previous* run's draw, never to a
clean slate, or the run right after a reset could serve up the run just played.

A draw also guarantees at least one non-classic riddle per level. Without it, a
pool that is mostly plain questions occasionally deals a level of nothing but
plain questions.

Scores are a percentage of `run_max_exp()`, the XP a flawless run of that length
could earn. Raw XP is not comparable across run lengths, because the streak
bonus grows with each consecutive answer and so dominates a long run.

## Architecture

One shared engine with two independent front-ends over it. **The engine never
imports a front-end.**

- **Content is data, not code.** Riddles live in `content/riddles.json`, so
  adding one never means touching game logic.
- **Shared engine, two skins.** `riddle.py` / `player.py` / `data.py` are
  front-end-agnostic. The terminal (`ui.py` + `game.py`) and the GUI
  (`sphinx/gui/`) each render that engine their own way.
- **`Player`** is the finished version of the `User` class the original project
  trailed off on — lives, XP and a full stats block.
- **`ui` degrades gracefully.** Colors switch off when output is not a
  terminal or when `NO_COLOR` is set, and nothing there assumes a console
  exists at all — a windowed build has no `sys.stdout`.

### The About screen renders ABOUT.md

`sphinx/gui/markdown.py` is a small, dependency-free Markdown renderer, and the
GUI's About screen is `ABOUT.md` drawn through it. That makes `ABOUT.md` part
of the program, not just documentation.

It supports only what it needs to:

- `#`, `##`, `###` headings
- fenced code blocks
- `- ` and `* ` bullets
- `> ` blockquotes
- `---` horizontal rules
- inline `**bold**`, `` `code` ``, and `[label](url)`

**Anything else is inserted verbatim.** A Markdown table in `ABOUT.md` shows up
in-game as raw `|---|---|` pipes. Keep tables and images in `README.md`, which
GitHub renders and the game never reads.

Both `install.sh` and the Windows PyInstaller spec copy `ABOUT.md` alongside the
code. A new top-level file that the game reads at runtime must be added to both,
or it will be missing from installed and packaged copies.

## Adding a riddle

Append an object to the relevant level in `sphinx/content/riddles.json`:

```json
{
  "id": "easy-16",
  "type": "classic",
  "prompt": "What has to be broken before you can use it?",
  "answers": ["an egg", "egg"],
  "hint": "You'll find it in the fridge.",
  "exp": 10
}
```

`id` must be unique and must never change: it is how the game remembers which
riddles a player has already been shown, so that consecutive runs draw fresh
ones. Rewording a prompt is fine; renaming its `id` makes the riddle new again.

`exp` is **not currently read by anything.** `Player.solve()` never sees the
riddle and awards a flat `BASE_XP` for any correct answer, so a hard riddle
pays exactly what an easy one does. The field is kept because the content
plainly intends otherwise — wiring it up is an obvious improvement, and would
make the difficulty curve mean something.

Other types extend the schema minimally:

```json
{ "type": "logic",    "constraints": ["clue 1", "clue 2"], ... }
{ "type": "cipher",   "cipher_type": "caesar", "shift": 3, "plain": "puzzle", ... }
{ "type": "cipher",   "cipher_type": "atbash", "plain": "sphinx", ... }
{ "type": "sequence", "sequence": ["2", "4", "8", "16"], "answers": ["32"], ... }
{ "type": "ascii_art", "art": " /\\_/\\\n( o.o )\n > ^ <", "answers": ["cat"], ... }
```

For `cipher`, the `plain` text is encoded automatically for display and is also
accepted as the answer (add more phrasings via `answers`).

`answers` is matched case-insensitively, so list the phrasings a player might
reasonably type rather than every capitalisation of them.

## Versioning

Sphinx uses [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.
The version is shown on the title screen and lives in exactly one place:
`__version__` in `sphinx/__init__.py`. Everything else reads it from there.

The **2.0.0** baseline was the pre-overhaul state (before the progression
overhaul, XP economy, HUD, leaderboard, sphinx art and the GUI). **2.1.0** was
the first release with the GUI and the unified launcher. **2.7.0** is the first
that installs itself — `install.sh` on Linux, and a packaged `Sphinx.exe` for
Windows.

Bump it after merging to `main`, using the script:

```bash
python scripts/bump_version.py            # a small fix:       2.1.0 -> 2.1.1
python scripts/bump_version.py --minor    # a new feature:     2.1.5 -> 2.2.0
python scripts/bump_version.py --major    # a breaking change: 2.4.2 -> 3.0.0
```

## Releases

The Windows executable is built by GitHub Actions, on the `windows` branch —
PyInstaller cannot cross-compile, so a `.exe` cannot be produced from Linux.

Pushing a `v*` tag builds the executable and attaches it to a GitHub Release:

```bash
git tag v2.7.0
git push origin v2.7.0
```

Without a tag, a push to `main` or `windows` still builds the executable and
leaves it as a downloadable CI artifact — which expires, and requires being
signed in to GitHub. Release assets do neither, so tag anything a player is
meant to download.

## Testing a change

There is no test suite yet. At a minimum, exercise both front-ends:

```bash
python play.py --terminal      # menus, a run, the leaderboard
python play.py                 # the GUI, including the About screen
```

If you touch `install.sh`, install into a throwaway prefix rather than your own
home directory, and check that removing it leaves nothing behind:

```bash
./install.sh --prefix /tmp/sphinx-test -y
/tmp/sphinx-test/bin/sphinx --terminal
./install.sh --prefix /tmp/sphinx-test --uninstall
```

`./install.sh --detect` prints the detected distribution and the package names
it would use, which is the quickest way to check the distribution mapping
without installing anything.

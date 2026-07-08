# Sphinx — riddles game project 🧩

A modular, interactive riddle game with two front-ends — a colorful terminal
version and a tkinter GUI — over one shared engine.

> A full rebuild of the very first program I wrote when I was just starting to
> learn to code. The original was a rough terminal riddle script; **Sphinx** is
> the overhaul of that first project — same spirit, rebuilt properly.

No external dependencies beyond the standard library. Pure Python 3.10+.
(The GUI uses `tkinter`, which ships with most Python installs.)

## Play

```bash
cd Sphinx
python play.py                # GUI — the default when no flag is given
python play.py --gui          # -g: the windowed (tkinter) version
python play.py --terminal     # -t: the terminal (text) version
python play.py --interactive  # -i (or -c / --choose): ask which one
```

`python -m sphinx` works the same way and takes the same flags. The GUI is the
default; it needs `tkinter` (Fedora: `sudo dnf install python3-tkinter`,
Debian/Ubuntu: `sudo apt install python3-tk`). The terminal version needs
nothing extra.

## Start menu

Launching the game opens a menu (same options in both front-ends):

1. **Start Run** — a full run through all three levels.
2. **Practice Mode** — drill any single level, no stakes.
3. **View Top 5** — the leaderboard.
4. **Quit**

## Gameplay

- A **run always starts at Easy**; Medium unlocks after clearing Easy, Hard
  after clearing Medium — one continuous session across the three themed
  levels: **The Outer Halls** → **The Inner Vault** → **The Sphinx's Chamber**.
- **Lives, XP and streak carry over** across the whole run.
- Riddles within a level appear in **random order** each time.
- A **wrong answer costs a life** (you start with ♥♥♥; the lost heart flickers
  out). **Zero lives = the run is over** — next time you start fresh at Easy.
- Finish a level with **zero mistakes** and you earn a life back.
- Between levels, a short **descent effect** darkens the palette as tension
  rises (skipped when colors are off).
- Stuck? Type `hint` — hints are limited per level (3 / 2 / 2).
- `skip` costs **65 XP** in a run (only if you can afford it); `quit` leaves.
- Riddle prompts reveal with a typewriter effect — **press any key to skip** it.
- At the end you get a bordered **report card**: title, XP, solved, longest
  streak, mistakes, hints and time.

### XP economy

- **+10 XP** per correct answer.
- **Streak bonus** from the 3rd correct in a row: 3rd `+2`, 4th `+4`, 5th `+6`,
  … (grows by +2 each further consecutive correct). Any wrong answer or `skip`
  resets the streak.
- A run-mode `skip` deducts **65 XP** from your score.

### Practice Mode

Pick any level and drill it directly. **Skips are free** (and never reveal the
answer), and nothing you do counts toward the run stats, title, or leaderboard.

### Leaderboard

The **Top 5** scores are kept in `content/leaderboard.json` (never more than
five entries). A qualifying run is added automatically at the end.

### Riddle types

- **classic** — a plain question with accepted answers.
- **logic** — like classic, but displays a list of clues/constraints.
- **cipher** — the message is Caesar- or Atbash-encoded; decode it.
- **sequence** — "what comes next?" number or letter patterns.
- **ascii_art** — a small ASCII picture; name what it shows.

## Architecture

One shared engine (riddle/player/data) with two independent front-ends over it:
the terminal UI and the tkinter GUI. The engine never imports either front-end.

```
Sphinx/
├── play.py                    # single launcher (-g gui / -t terminal / -i choose)
├── scripts/
│   └── bump_version.py        # manual SemVer bump helper
└── sphinx/
    ├── __init__.py            # __version__ — the single source of truth
    ├── __main__.py            # front-end dispatch (terminal / GUI) + flags
    ├── game.py                # terminal flow: real & practice loops
    ├── ui.py                  # terminal rendering: colors, banners, input
    ├── gui.py                 # tkinter rendering, animation, input
    ├── gui_state.py           # tkinter game-flow state (no tkinter imports)
    ├── riddle.py              # Riddle models (+ from_dict)  ← shared engine
    ├── player.py              # Player: lives, XP, streak, stats  ← shared engine
    ├── data.py                # content + leaderboard loading  ← shared engine
    └── content/
        ├── riddles.json       # all riddle content (data, not code)
        └── leaderboard.json   # Top 5 scores (created on first qualifying run)
```

Design notes:

- **Content is data, not code.** Riddles live in `content/riddles.json`,
  so adding a riddle never means touching game logic.
- **Shared engine, two skins.** `riddle.py` / `player.py` / `data.py` are
  front-end-agnostic; the terminal (`ui.py` + `game.py`) and the GUI
  (`gui.py` + `gui_state.py`) each render that engine their own way.
- **`Player`** is the finished version of the `User` class the original
  project trailed off on — lives, XP and a full stats block.
- **`ui`** degrades gracefully: colors switch off automatically when
  output isn't a terminal or when `NO_COLOR` is set.

## Adding a riddle

Append an object to the relevant level in `content/riddles.json`:

```json
{
  "type": "classic",
  "prompt": "What has to be broken before you can use it?",
  "answers": ["an egg", "egg"],
  "hint": "You'll find it in the fridge.",
  "exp": 10
}
```

Other types extend the schema minimally:

```json
{ "type": "logic",    "constraints": ["clue 1", "clue 2"], ... }
{ "type": "cipher",   "cipher_type": "caesar", "shift": 3, "plain": "puzzle", ... }
{ "type": "cipher",   "cipher_type": "atbash", "plain": "sphinx", ... }
{ "type": "sequence", "sequence": ["2", "4", "8", "16"], "answers": ["32"], ... }
{ "type": "ascii_art", "art": " /\\_/\\\n( o.o )\n > ^ <", "answers": ["cat"], ... }
```

For `cipher`, the `plain` text is encoded automatically for display and is
also accepted as the answer (you can add more phrasings via `answers`).

## Versioning

Sphinx uses [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.
The version is shown on the title screen and lives in exactly one place:
`__version__` in `sphinx/__init__.py`. Everything else reads it from there.

The **2.0.0** baseline was the pre-overhaul state (before the progression
overhaul, XP economy, HUD, leaderboard, sphinx art and the GUI). The current
version is **2.1.0**, the first release with the GUI and the unified launcher.

Bump it manually after merging to `main`, using the script:

```bash
python scripts/bump_version.py            # a small fix:     2.1.0 -> 2.1.1
python scripts/bump_version.py --minor    # a new feature:   2.1.5 -> 2.2.0
python scripts/bump_version.py --major    # a breaking change: 2.4.2 -> 3.0.0
```

- **After a small fix** merged to `main` → `python scripts/bump_version.py`.
- **After a real new feature** merged to `main` →
  `python scripts/bump_version.py --minor`.

Optionally, tag that exact commit in git so you can jump back to it later:

```bash
git tag v2.2.0
git push origin v2.2.0
```

## Contact

Made by Yuval Bogomoletz. Find me — and the rest of my projects — on GitHub at
[github.com/YuvalBogo](https://github.com/YuvalBogo).

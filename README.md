# Riddles 2.0 🧩

A modular, interactive terminal riddle game — a full rebuild of the very
first program I wrote when I was just starting to learn to code.

No external dependencies. Pure Python 3.10+.

## Play

```bash
cd Riddles2.0
python play.py              # asks whether to play in the terminal or GUI
python play.py --terminal   # -t: the terminal (text) version
python play.py --gui        # -g: the windowed (tkinter) version
```

`python -m riddles` works the same way and takes the same `-t` / `--terminal`
and `-g` / `--gui` flags. The GUI needs `tkinter` (Fedora:
`sudo dnf install python3-tkinter`).

## Start menu

Launching the game opens a menu:

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

The project is a small package where each module has one job:

```
Riddles2.0/
├── play.py                    # single launcher (-t terminal / -g gui)
└── riddles/
    ├── __main__.py            # front-end dispatch (terminal / GUI) + menu
    ├── game.py                # Game: real & practice loops, flow control
    ├── riddle.py              # Riddle models (+ from_dict)
    ├── player.py              # Player: lives, XP, streak, stats, timing
    ├── data.py                # content + leaderboard loading, messages
    ├── ui.py                  # colors, banners, transitions, input
    └── content/
        ├── riddles.json       # all riddle content (data, not code)
        └── leaderboard.json   # Top 5 scores (created on first qualifying run)
```

Design notes:

- **Content is data, not code.** Riddles live in `content/riddles.json`,
  so adding a riddle never means touching game logic.
- **`Riddle` → `LogicRiddle` inheritance** carries over from the original
  design; the logic subclass adds displayed *clues/constraints*.
- **`Player`** is the finished version of the `User` class the original
  project trailed off on — lives, EXP and a full stats block.
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

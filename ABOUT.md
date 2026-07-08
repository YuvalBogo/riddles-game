# Sphinx — riddles game project 🧩

A modular, interactive riddle game with two front-ends — a colorful terminal
version and a tkinter GUI — over one shared engine.

> A full rebuild of the very first program I wrote when I was just starting to
> learn to code. The original was a rough terminal riddle script; **Sphinx** is
> the overhaul of that first project — same spirit, rebuilt properly.

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
- Each level draws **five riddles** from a much larger pool, and the tomb never
  deals the same ones twice in a row. The halls are not as you left them.
- **Lives, XP and streak carry over** across the whole run.
- A **wrong answer costs a life** (you start with ♥♥♥; the lost heart flickers
  out). **Zero lives = the run is over** — next time you start fresh at Easy.
- Finish a level with **zero mistakes** and you earn a life back.
- Between levels, a short **descent effect** darkens the palette as tension
  rises (skipped when colors are off).
- Stuck? Type `hint` — it costs **15 XP**, and hints are limited per level
  (3 / 2 / 2).
- `skip` costs **25 XP** in a run (only if you can afford it); `quit` leaves.
- Riddle prompts reveal with a typewriter effect — **press any key to skip** it.
- At the end you get a bordered **report card**: title, XP, solved, longest
  streak, mistakes, hints and time.

### XP economy

- **+10 XP** per correct answer.
- **Streak bonus** from the 3rd correct in a row: 3rd `+2`, 4th `+4`, 5th `+6`,
  … (grows by +2 each further consecutive correct). Any wrong answer or `skip`
  resets the streak.
- A run-mode `skip` deducts **25 XP** from your score, a `hint` **15 XP**.

### Practice Mode

Pick any level and drill it directly. **Skips are free** (and never reveal the
answer), and nothing you do counts toward the run stats, title, or leaderboard.

### Leaderboard

The **Top 5** is kept as a **percentage** — how much of a run's possible XP you
actually took. A flawless run is 100%, whatever the tomb dealt you, and scores
from runs of different lengths stay comparable.

Scores live outside the game's own folder, in your personal data directory —
`~/.local/share/Sphinx/leaderboard.json` on Linux, `%APPDATA%\Sphinx\` on
Windows — so they survive upgrades and uninstalls. A qualifying run is added
automatically at the end (never more than five entries).

### Riddle types

- **classic** — a plain question with accepted answers.
- **logic** — like classic, but displays a list of clues/constraints.
- **cipher** — the message is Caesar- or Atbash-encoded; decode it.
- **sequence** — "what comes next?" number or letter patterns.
- **ascii_art** — a small ASCII picture; name what it shows.

## Contact

Made by Yuval Bogomoletz. Find me — and the rest of my projects — on GitHub at
[github.com/YuvalBogo](https://github.com/YuvalBogo).

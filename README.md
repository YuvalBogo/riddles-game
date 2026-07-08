# Sphinx — riddles game project 🧩

A riddle game for the terminal and the desktop. Three levels, one pool of
lives, and a sphinx that is not especially nice about wrong answers.

> A full rebuild of the very first program I wrote when I was just starting to
> learn to code — same spirit, rebuilt properly. The longer story is in
> [ABOUT.md](ABOUT.md).

Pure Python, no dependencies beyond the standard library. Runs on Linux,
Windows and macOS.

---

## Install

### Linux

```bash
git clone https://github.com/YuvalBogo/riddles-game.git
cd riddles-game
./install.sh
```

That installs for the current user — **no root required** — and puts a `sphinx`
command on your `PATH`. The game also appears in your desktop's application
menu.

The installer reads `/etc/os-release` to identify your distribution, and offers
to install `tkinter` for you if it is missing. Fedora, Ubuntu, Debian, Mint,
Pop!_OS, RHEL, Rocky, Arch, Manjaro and openSUSE are recognised; on anything
else it prints the package to install by hand and carries on.

| Command | Effect |
|---|---|
| `./install.sh` | install for the current user, under `~/.local` |
| `./install.sh --system` | install for every user, under `/usr/local` (needs `sudo`) |
| `./install.sh --uninstall` | remove it again — your scores are kept |
| `./install.sh --detect` | print which distribution it thinks you are on |
| `./install.sh --help` | all options |

Where things end up:

| Path | Contents |
|---|---|
| `~/.local/share/sphinx-game/` | the program |
| `~/.local/bin/sphinx` | the command |
| `~/.local/share/Sphinx/` | your leaderboard — survives upgrades **and** uninstalls |

### Windows

Download `Sphinx.exe` from the
[latest release](https://github.com/YuvalBogo/riddles-game/releases/latest) and
double-click it. Nothing to install, and no Python needed.

Windows will warn that the file is unrecognised, because it is not
code-signed — choose **More info → Run anyway**. The first launch takes a few
seconds while the program unpacks itself.

### Without installing

The game runs straight from a checkout, on any platform:

```bash
python play.py
```

---

## Playing

There are two front-ends over the same engine. The windowed one is the default.

```bash
sphinx                  # GUI — the default
sphinx --gui            # -g: the same thing, explicitly
sphinx --terminal       # -t: the colorful text version
sphinx --interactive    # -i: ask which one to launch
```

From a checkout, `python play.py` and `python -m sphinx` take exactly the same
flags.

**Which should you use?**

| | GUI | Terminal |
|---|---|---|
| Needs `tkinter` | yes | no |
| Works over SSH | no | yes |
| Mouse, images, animation | yes | — |
| Colors | yes | yes, unless `NO_COLOR` is set |

The GUI needs `tkinter`, which ships with most Python installs but is packaged
separately on Linux (`sudo dnf install python3-tkinter` on Fedora,
`sudo apt install python3-tk` on Debian and Ubuntu). `install.sh` handles that
for you. The terminal version needs nothing at all.

[Pillow](https://python-pillow.org/) is optional. If it is present the GUI
scales its artwork more smoothly; without it, Tk's coarser scaler is used and
nothing breaks.

---

## The game

A run starts at **Easy** and continues through **Medium** and **Hard** — *The
Outer Halls*, *The Inner Vault*, and *The Sphinx's Chamber* — carrying your
lives, XP and streak the whole way. A wrong answer costs a life; clear a level
without mistakes and you earn one back. At zero lives the run ends.

Correct answers earn XP, which buys hints, and consecutive correct answers pay
a growing streak bonus. The top five scores are kept in a leaderboard outside
the game folder, so they survive reinstalling.

Riddles come in five flavours — classic, logic, cipher, sequence and ASCII
art — and appear in a random order every run.

Full rules, the XP economy, and Practice Mode are described in
[ABOUT.md](ABOUT.md), which is also what the game shows on its own **About**
screen.

---

## Project structure

```
riddles-game/
├── play.py             # launcher: -g gui / -t terminal / -i choose
├── install.sh          # Linux installer
├── ABOUT.md            # the game's in-app About screen
└── sphinx/
    ├── riddle.py       # riddle models          ┐
    ├── player.py       # lives, XP, streak      │ shared engine
    ├── data.py         # content + leaderboard  ┘
    ├── ui.py           # terminal rendering     ┐ two front-ends
    ├── game.py         # terminal game loop     │
    ├── gui/            # tkinter front-end      ┘
    └── content/
        └── riddles.json    # all riddle content — data, not code
```

The engine never imports a front-end. Riddles are data, so adding one means
editing JSON, not code.

A fuller tour — the architecture, how to add a riddle, how releases work — is
in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Contributing

Bug reports and new riddles are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the project layout, the riddle schema,
and the versioning rules.

## Contact

Made by Yuval Bogomoletz. Find me — and the rest of my projects — on GitHub at
[github.com/YuvalBogo](https://github.com/YuvalBogo).

#!/usr/bin/env bash
#
# Install Sphinx so that it runs by typing `sphinx` in a terminal.
#
#   ./install.sh              install for the current user (no root needed)
#   ./install.sh --system     install for every user (needs sudo)
#   ./install.sh --uninstall  remove it again
#   ./install.sh --help       full options
#
# A user install lands under ~/.local, which mirrors the system-wide
# /usr/local layout — that is precisely why it needs no root: it is your own
# copy, on your own PATH.

set -euo pipefail

APP_NAME="sphinx"
# Deliberately not "sphinx": the leaderboard already lives in <prefix>/share/
# Sphinx, and two directories differing only in case is a collision waiting to
# happen on any case-insensitive filesystem.
APP_DIR_NAME="sphinx-game"
# Matches the floor the README promises. No 3.10-only syntax is actually used
# — every module defers its annotations — but nothing is tested below this, so
# the installer holds the documented line rather than inventing a looser one.
MIN_PY_MINOR=10

PREFIX=""
MODE="install"
ASSUME_YES=0

RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
[ -t 1 ] || { RED=""; GREEN=""; YELLOW=""; BOLD=""; OFF=""; }

info()  { printf '  %s\n' "$*"; }
good()  { printf '  %s%s%s\n' "$GREEN" "$*" "$OFF"; }
warn()  { printf '  %s%s%s\n' "$YELLOW" "$*" "$OFF"; }
die()   { printf '\n  %sError:%s %s\n\n' "$RED$BOLD" "$OFF" "$*" >&2; exit 1; }

usage() {
    cat <<EOF
Install Sphinx so it runs by typing \`${APP_NAME}\`.

Usage: ./install.sh [options]

  --system         install to /usr/local for all users (requires sudo)
  --prefix DIR     install under DIR instead (advanced; implies no sudo)
  --uninstall      remove a previous installation
  --detect         print the detected distribution and package names, then exit
  -y, --yes        do not prompt before installing system packages
  -h, --help       show this message

With no options, installs under ~/.local for the current user only.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --system)    PREFIX="/usr/local" ;;
        --prefix)    shift; [ $# -gt 0 ] || die "--prefix needs a directory"; PREFIX="$1" ;;
        --uninstall) MODE="uninstall" ;;
        --detect)    MODE="detect" ;;
        -y|--yes)    ASSUME_YES=1 ;;
        -h|--help)   usage; exit 0 ;;
        *)           die "unknown option: $1  (try --help)" ;;
    esac
    shift
done

# Default to a user install under the XDG data home.
if [ -z "$PREFIX" ]; then
    PREFIX="$HOME/.local"
fi

APP_DIR="$PREFIX/share/$APP_DIR_NAME"
BIN_DIR="$PREFIX/bin"
LAUNCHER="$BIN_DIR/$APP_NAME"
DESKTOP_DIR="$PREFIX/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/$APP_NAME.desktop"
ICON_DIR="$PREFIX/share/icons/hicolor/512x512/apps"
ICON_FILE="$ICON_DIR/$APP_NAME.png"
# Earlier versions installed a 256x256 icon. Left behind, it wins the icon-theme
# lookup on some desktops, so uninstall sweeps it too.
LEGACY_ICON_FILE="$PREFIX/share/icons/hicolor/256x256/apps/$APP_NAME.png"

# Writing outside $HOME needs root; re-exec under sudo rather than failing
# halfway through with a pile of permission errors.
maybe_sudo() {
    if [ -w "$(dirname "$PREFIX")" ] || [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

# --- uninstall --------------------------------------------------------------

if [ "$MODE" = "uninstall" ]; then
    printf '\n%sRemoving Sphinx%s\n\n' "$BOLD" "$OFF"
    removed=0
    for path in "$APP_DIR" "$LAUNCHER" "$DESKTOP_FILE" "$ICON_FILE" "$LEGACY_ICON_FILE"; do
        if [ -e "$path" ]; then
            maybe_sudo rm -rf "$path"
            info "removed $path"
            removed=1
        fi
    done
    [ "$removed" -eq 1 ] || warn "nothing found under $PREFIX"
    # Scores are the player's, not the program's. Deleting them on uninstall
    # would be a nasty surprise; say where they are and leave them alone.
    if [ -d "${XDG_DATA_HOME:-$HOME/.local/share}/Sphinx" ]; then
        printf '\n'
        info "Your leaderboard was left at ${XDG_DATA_HOME:-$HOME/.local/share}/Sphinx"
    fi
    printf '\n'; good "Done."; printf '\n'
    exit 0
fi

# --- work out where we are running from -------------------------------------

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for required in "$SRC_DIR/play.py" "$SRC_DIR/sphinx/__main__.py" \
                "$SRC_DIR/sphinx/content/riddles.json" "$SRC_DIR/ABOUT.md"; do
    [ -e "$required" ] || die "run this from the Sphinx source directory (missing ${required#$SRC_DIR/})"
done

printf '\n%sInstalling Sphinx%s\n\n' "$BOLD" "$OFF"

# --- identify the distribution ----------------------------------------------

DISTRO_ID=""; DISTRO_LIKE=""; DISTRO_NAME="your distribution"
PKG_INSTALL=""; TK_PKG=""; PIL_PKG=""

# Overridable so the mapping below can be exercised against other distributions
# than the one doing the testing.
OS_RELEASE_FILE="${OS_RELEASE_FILE:-/etc/os-release}"

detect_distro() {
    if [ -r "$OS_RELEASE_FILE" ]; then
        # shellcheck disable=SC1090
        . "$OS_RELEASE_FILE"
        DISTRO_ID="${ID:-}"; DISTRO_LIKE="${ID_LIKE:-}"; DISTRO_NAME="${NAME:-$DISTRO_ID}"
    fi

    # Resolve to a package manager and the names tkinter/Pillow go by there.
    # ID is matched first, then ID_LIKE, so derivatives (Mint, Pop!_OS, Rocky)
    # are covered without having to name every one of them.
    case " $DISTRO_ID $DISTRO_LIKE " in
        *" fedora "*|*" rhel "*|*" centos "*)
            PKG_INSTALL="dnf install -y"; TK_PKG="python3-tkinter"; PIL_PKG="python3-pillow" ;;
        *" debian "*|*" ubuntu "*)
            PKG_INSTALL="apt-get install -y"; TK_PKG="python3-tk"; PIL_PKG="python3-pil" ;;
        *" arch "*)
            PKG_INSTALL="pacman -S --noconfirm"; TK_PKG="tk"; PIL_PKG="python-pillow" ;;
        *" suse "*|*" opensuse "*)
            PKG_INSTALL="zypper install -y"; TK_PKG="python3-tk"; PIL_PKG="python3-Pillow" ;;
    esac
}

detect_distro

if [ "$MODE" = "detect" ]; then
    printf 'id=%s like=%s name=%s\npkg=%s tk=%s pil=%s\n' \
        "$DISTRO_ID" "$DISTRO_LIKE" "$DISTRO_NAME" \
        "${PKG_INSTALL:-<unsupported>}" "${TK_PKG:-none}" "${PIL_PKG:-none}"
    exit 0
fi

info "Detected: $DISTRO_NAME"

# --- Python ------------------------------------------------------------------

command -v python3 >/dev/null 2>&1 || die "python3 is not installed."
PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, $MIN_PY_MINOR) else 1)" \
    || die "Python 3.$MIN_PY_MINOR+ required, found $PY_VER."
info "Python $PY_VER"

# tkinter is stdlib but ships separately on most distributions, so a plain
# python3 install can still be missing it.
install_pkg() {   # $1 = package, $2 = human description
    if [ -z "$PKG_INSTALL" ]; then
        warn "Cannot auto-install on $DISTRO_NAME. Please install $2 yourself."
        return 1
    fi
    if [ "$ASSUME_YES" -ne 1 ]; then
        printf '  %s is missing. Install it with: sudo %s %s\n' "$2" "$PKG_INSTALL" "$1"
        read -r -p "  Go ahead? [Y/n] " reply
        case "$reply" in [nN]*) return 1 ;; esac
    fi
    # shellcheck disable=SC2086
    sudo $PKG_INSTALL "$1"
}

if python3 -c 'import tkinter' 2>/dev/null; then
    info "tkinter present"
else
    warn "tkinter missing — the GUI needs it"
    if install_pkg "$TK_PKG" "tkinter"; then
        python3 -c 'import tkinter' 2>/dev/null \
            || die "tkinter still not importable after installing $TK_PKG."
        good "tkinter installed"
    else
        warn "Continuing without tkinter: only \`$APP_NAME --terminal\` will work."
    fi
fi

# Pillow is genuinely optional — assets.py falls back to Tk's coarser
# subsample — so a refusal here is not fatal and must not read like an error.
if python3 -c 'import PIL' 2>/dev/null; then
    info "Pillow present (banners will scale cleanly)"
else
    if [ "$ASSUME_YES" -eq 1 ] && [ -n "$PIL_PKG" ]; then
        # shellcheck disable=SC2086
        sudo $PKG_INSTALL "$PIL_PKG" || true
    else
        info "Pillow not found — optional, banners will just scale more coarsely."
        info "  install with: sudo ${PKG_INSTALL:-<your package manager>} ${PIL_PKG:-python3-pillow}"
    fi
fi

# --- copy the program into place ---------------------------------------------

maybe_sudo mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"
maybe_sudo rm -rf "${APP_DIR:?}/sphinx"     # drop files a previous version left

maybe_sudo cp -r "$SRC_DIR/sphinx" "$APP_DIR/sphinx"
maybe_sudo cp    "$SRC_DIR/play.py" "$APP_DIR/play.py"
# markdown.py reads ../../ABOUT.md relative to itself: the GUI's About screen is
# that file, rendered. It is program content, not documentation, so it ships.
maybe_sudo cp    "$SRC_DIR/ABOUT.md" "$APP_DIR/ABOUT.md"
# A stale leaderboard could ride along in the copy; scores live elsewhere now.
maybe_sudo rm -f "$APP_DIR/sphinx/content/leaderboard.json"
maybe_sudo find "$APP_DIR" -name __pycache__ -type d -prune -exec rm -rf {} +
info "Program files -> $APP_DIR"

# The launcher does not cd anywhere: `python3 /path/to/play.py` already puts
# that directory at the front of sys.path, so the game finds its package no
# matter where it is run from, and leaves your shell where you were.
tmp_launcher="$(mktemp)"
cat > "$tmp_launcher" <<EOF
#!/usr/bin/env bash
# Sphinx launcher — installed by install.sh. Delete via: ./install.sh --uninstall
exec python3 "$APP_DIR/play.py" "\$@"
EOF
maybe_sudo install -m 755 "$tmp_launcher" "$LAUNCHER"
rm -f "$tmp_launcher"
info "Launcher     -> $LAUNCHER"

# Carry an existing leaderboard across. Scores used to live beside the code, so
# a player upgrading from a checkout would otherwise watch their Top 5 vanish
# the moment they started running the installed copy. Never overwrite a board
# already in the data directory — that one is newer.
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/Sphinx"
LEGACY_BOARD="$SRC_DIR/sphinx/content/leaderboard.json"
if [ -f "$LEGACY_BOARD" ] && [ ! -f "$DATA_DIR/leaderboard.json" ]; then
    # Deliberately un-sudo'd: even a --system install writes this to the
    # invoking user's home, because a leaderboard belongs to a player.
    mkdir -p "$DATA_DIR"
    cp "$LEGACY_BOARD" "$DATA_DIR/leaderboard.json"
    info "Existing scores -> $DATA_DIR/leaderboard.json"
fi

# The desktop icon. game_logo.png is a 512x512 transparent render of the SVG,
# committed alongside it. The SVG cannot be dropped in here directly: a hicolor
# size directory holds rasters of exactly that size, and naming an SVG
# "sphinx.png" leaves the desktop to guess. Shipping the render also means an
# install needs no rasterizer, and the game can use the same file as its window
# icon — Tk reads PNG and does not read SVG.
maybe_sudo install -m 644 "$SRC_DIR/sphinx/images/game_logo.png" "$ICON_FILE"
maybe_sudo rm -f "$LEGACY_ICON_FILE"    # an older, smaller icon would outrank it

tmp_desktop="$(mktemp)"
cat > "$tmp_desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Sphinx
Comment=Match wits with the sphinx — a riddle game
Exec=$LAUNCHER
Icon=$APP_NAME
Terminal=false
Categories=Game;LogicGame;
# The window class Tk reports for tk.Tk(className="sphinx") — it capitalises the
# name. Without this key a Wayland dock shows the running window under a generic
# icon rather than this entry's.
StartupWMClass=Sphinx
EOF
maybe_sudo install -m 644 "$tmp_desktop" "$DESKTOP_FILE"
rm -f "$tmp_desktop"
info "Menu entry   -> $DESKTOP_FILE"

# Refresh the menu so the entry appears without a re-login. Harmless if absent.
command -v update-desktop-database >/dev/null 2>&1 \
    && maybe_sudo update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

# --- report -------------------------------------------------------------------

printf '\n'; good "Sphinx is installed."; printf '\n'

case ":$PATH:" in
    *":$BIN_DIR:"*)
        info "Run it by typing:  ${BOLD}$APP_NAME${OFF}"
        ;;
    *)
        warn "$BIN_DIR is not on your PATH, so \`$APP_NAME\` will not be found yet."
        info "Add it by running:"
        printf '\n      echo '\''export PATH="%s:$PATH"'\'' >> ~/.bashrc && source ~/.bashrc\n\n' "$BIN_DIR"
        ;;
esac

info "  $APP_NAME              the windowed version"
info "  $APP_NAME --terminal   the text version"
info "  ./install.sh --uninstall  to remove it"
printf '\n'

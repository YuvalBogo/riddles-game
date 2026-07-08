# PyInstaller build recipe for Sphinx.  Build with:  pyinstaller sphinx.spec
#
# The bundle mirrors the repository layout, because the game finds its content
# by walking up from __file__ — and inside a frozen build __file__ points into
# PyInstaller's unpack directory. Keep these paths in step with:
#
#     sphinx/data.py:11          content/riddles.json
#     sphinx/gui/assets.py:16    ../images/
#     sphinx/gui/markdown.py:32  ../../README.md
#
# Anything listed here is read-only at runtime: the unpack directory is deleted
# when the game exits. Save data goes to sphinx.data._user_data_dir() instead.

datas = [
    ("sphinx/content/riddles.json", "sphinx/content"),  # fatal if missing
    ("sphinx/images", "sphinx/images"),                 # banners; degrades
    ("README.md", "."),                                 # in-game help; degrades
]

a = Analysis(
    ["play.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    # Pillow is optional (assets.py falls back to Tk's subsample), but when it
    # is present at build time PyInstaller must pull in the C extension that
    # the lazy `from PIL import Image` needs.
    hiddenimports=["PIL", "PIL.Image"],
    hookspath=[],
    runtime_hooks=[],
    # The leaderboard is the only file the game writes, and it no longer lives
    # in the package, so nothing here needs to be excluded for writability.
    excludes=["pytest", "setuptools"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Sphinx",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # No console window: this is a tkinter game, and a stray terminal behind it
    # looks broken. Requires that importing sphinx.ui tolerate sys.stdout being
    # None — see the _isatty() guard in sphinx/ui.py.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

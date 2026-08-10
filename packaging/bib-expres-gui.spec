# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller packaging/bib-expres-gui.spec (desde la raiz del repo)
from pathlib import Path

repo_root = Path(SPECPATH).parent
static_dir = repo_root / "src" / "bib_expres" / "gui" / "static"

a = Analysis(
    [str(Path(SPECPATH) / "run_gui.py")],
    pathex=[str(repo_root / "src")],
    binaries=[],
    datas=[(str(static_dir), "bib_expres/gui/static")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="bib-expres-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

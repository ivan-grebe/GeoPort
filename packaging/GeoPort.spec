# Build from the repository root: uv run --group windows-build pyinstaller packaging/GeoPort.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
datas = collect_data_files("geoport") + copy_metadata("geoport", recursive=True)
datas += [(str(root / "LICENSE"), "licenses/GeoPort")]

a = Analysis(
    [str(root / "packaging" / "windows_entry.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "IPython", "xonsh"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GeoPort",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    uac_admin=False,
)

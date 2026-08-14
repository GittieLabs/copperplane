# -*- mode: python ; coding: utf-8 -*-
#
# SPEC-401/CTX-401.1: freezes the daemon into a single, real executable via
# PyInstaller, so core/tauri-rust's spawn_daemon can ship it as a Tauri
# `externalBin` sidecar instead of assuming a system `python3` with
# kicad-python/pynng/trimesh/gittielabs-agentflow already importable.
#
# Must be run with a Python interpreter built with a real shared library
# (`--enable-shared` or `--enable-framework`) -- PyInstaller refuses to run
# against one that isn't, and this repo's own platformio-managed
# interpreter is exactly that case (a real, concrete finding from CTX-401.1
# Plan Drift, not a hypothetical). A Homebrew-installed `python3.11`
# (`brew install python@3.11`) is a real, working alternative, verified
# against this exact spec file.
#
# No `hiddenimports` were needed for a real, working freeze, including
# AgentFlow's lazily-imported provider SDK classes (llm_providers.py's own
# `_build_provider`, `from agentflow import AnthropicProvider` etc., each
# only reached at runtime once a specific provider is actually selected) --
# PyInstaller's static analysis parses `from X import Y` statements
# wherever they appear in a module's AST, function body or not, so this
# was never the risk SPEC-401's own first draft predicted it might be
# (recorded honestly in CTX-401.1 Plan Drift, including the correction).

import os

# SPECPATH is PyInstaller's own global for the directory containing this
# .spec file -- daemon.py lives right next to it, so no other path
# resolution is needed regardless of the cwd this is invoked from.
_HERE = os.path.abspath(SPECPATH)

a = Analysis(
    [os.path.join(_HERE, "daemon.py")],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="hardware-agent-studio-daemon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

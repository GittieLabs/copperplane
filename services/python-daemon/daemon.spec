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
# Plan Drift, not a hypothetical). Note that `sysconfig`'s own
# `Py_ENABLE_SHARED` is misleading here and reports 0 even on a working
# framework build -- check `PYTHONFRAMEWORK` instead.
#
# On macOS, use python.org's official universal2 3.11 pkg, which is what
# `release.yml` installs and therefore the only interpreter this freeze is
# actually verified against:
#
#     /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11
#
# CTX-401.1 originally recommended a Homebrew `python@3.11` here. CTX-402.4
# superseded that -- Homebrew's is single-arch only, so it cannot serve both
# matrix legs -- and this header went stale rather than being updated with
# it. Corrected by SPEC-407 after the stale advice cost a real build session.
#
# `target_arch=None` below means "match the invoking interpreter". That makes
# arch consistency the caller's job: the interpreter that creates the venv,
# the pip that installs into it, and the pyinstaller that reads it must all
# run under the SAME architecture. Mixing them (easy on an Apple Silicon Mac
# whose shell happens to be running under Rosetta) produces either a build
# error or -- if PyInstaller's `build/` cache lets the arch check be skipped
# on a re-run -- a binary that fails with a `dlopen` architecture error at
# runtime instead. Clear `build/` when changing arch; see SPEC-407 §2.1.
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

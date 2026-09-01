#!/usr/bin/env python3
"""
SPEC-407 §2.3: the real PyInstaller freeze, factored out of
`ensure_sidecar.py` so the fast "is the sidecar already fine" check has no
dependency on it, and so `release.yml` can call this half directly.

Every requirement encoded here was learned the hard way and is recorded in a
context file rather than inferred:

*   The interpreter must be a framework build (CTX-401.1). `PYTHONFRAMEWORK`
    is the signal; `Py_ENABLE_SHARED` misleadingly reports 0 even on a working
    framework build.
*   On macOS that means python.org's universal2 3.11, not Homebrew's, which is
    single-arch only (CTX-402.4 superseding CTX-401.1).
*   `daemon.spec` uses `target_arch=None`, meaning "match the invoking
    interpreter", so the venv, the pip install and the pyinstaller run must
    all execute under ONE architecture. Mixing them is what produced a
    runtime `dlopen` error instead of a build failure (SPEC-407 §2.1).
*   PyInstaller's `build/` cache can bypass its own arch check on a re-run,
    so it is cleared whenever the arch could have changed.
"""
import os
import shutil
import subprocess
import sys

_MACOS_FRAMEWORK_PYTHON = (
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11"
)


def find_freeze_python() -> str:
    """An interpreter PyInstaller will actually accept. Returns a path or
    raises with the exact remedy -- never a vague 'not found'."""
    candidates = []
    if sys.platform == "darwin":
        candidates.append(_MACOS_FRAMEWORK_PYTHON)
    candidates.append(sys.executable)

    for candidate in candidates:
        if not candidate or not os.path.exists(candidate):
            continue
        probe = subprocess.run(
            [candidate, "-c",
             "import sysconfig;print(sysconfig.get_config_var('PYTHONFRAMEWORK') or '')"],
            capture_output=True, text=True,
        )
        if probe.returncode != 0:
            continue
        # Only macOS requires a framework build; elsewhere any CPython works.
        if sys.platform != "darwin" or probe.stdout.strip():
            return candidate

    raise RuntimeError(
        "no interpreter PyInstaller can freeze with. On macOS install "
        "python.org's universal2 Python 3.11 (the same build release.yml uses):\n"
        "    curl -fsSL -o /tmp/python311.pkg "
        "https://www.python.org/ftp/python/3.11.9/python-3.11.9-macos11.pkg\n"
        "    sudo installer -pkg /tmp/python311.pkg -target /\n"
        "Homebrew's python@3.11 is single-arch and was superseded for this "
        "purpose by CTX-402.4."
    )


def _arch_prefix(triple: str) -> list:
    """`arch -x86_64` / `arch -arm64` so every step runs under ONE
    architecture. macOS only -- no other platform has the concept, and
    inheriting one there would be a check that cannot pass."""
    if sys.platform != "darwin":
        return []
    if triple.startswith("x86_64"):
        return ["arch", "-x86_64"]
    if triple.startswith("aarch64"):
        return ["arch", "-arm64"]
    return []


def freeze(triple: str, daemon_dir: str, dist_dir: str, final_name: str) -> None:
    """Freeze the daemon and leave it at `dist/<final_name>`."""
    python = find_freeze_python()
    prefix = _arch_prefix(triple)
    venv = os.path.join(daemon_dir, ".build-venv")
    build_cache = os.path.join(daemon_dir, "build")

    # PyInstaller's cache can silently reuse a binary processed for the other
    # architecture, turning a build-time error into a runtime dlopen failure.
    for stale in (venv, build_cache):
        if os.path.isdir(stale):
            shutil.rmtree(stale)

    def run(cmd, why):
        result = subprocess.run(prefix + cmd, cwd=daemon_dir)
        if result.returncode != 0:
            raise RuntimeError(f"{why} failed (exit {result.returncode}): {' '.join(cmd)}")

    run([python, "-m", "venv", venv], "creating the build venv")
    venv_bin = os.path.join(venv, "Scripts" if os.name == "nt" else "bin")
    venv_python = os.path.join(venv_bin, "python.exe" if os.name == "nt" else "python")

    run([venv_python, "-m", "pip", "install", "--quiet",
         "-r", "requirements.txt", "-r", "requirements-build.txt"],
        "installing daemon runtime and build dependencies")
    run([venv_python, "-m", "PyInstaller", "daemon.spec"], "the PyInstaller freeze")

    produced = os.path.join(dist_dir, "hardware-agent-studio-daemon")
    if os.name == "nt":
        produced += ".exe"
    if not os.path.isfile(produced):
        raise RuntimeError(f"PyInstaller reported success but produced no binary at {produced}")

    # Tauri looks for the target-triple name; PyInstaller writes the bare one.
    # Skipping this rename is what leaves the committed placeholder in place
    # and bundles it instead (SPEC-407 §2.1, failure mode 5).
    shutil.move(produced, os.path.join(dist_dir, final_name))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-triple", required=True)
    args = parser.parse_args()

    _here = os.path.dirname(os.path.abspath(__file__))
    _daemon = os.path.dirname(_here)
    sys.path.insert(0, _here)
    from ensure_sidecar import sidecar_name

    freeze(args.target_triple, _daemon, os.path.join(_daemon, "dist"),
           sidecar_name(args.target_triple))

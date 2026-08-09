"""
Headless FreeCAD subprocess bridge (SPEC-104). Rather than importing the
FreeCAD Python module directly into this long-running daemon — risking
memory leaks/segfaults from FreeCAD's C++ global state — each request
spawns a fresh, short-lived `freecadcmd` subprocess that runs a generated
script and exits.
"""
import glob
import os
import platform
import shutil
import subprocess
import tempfile
import time
import uuid

import trimesh


class FreeCADUnavailableError(Exception):
    """Raised when the `freecadcmd` executable can't be located."""


class FreeCADBuildError(Exception):
    """Raised when `freecadcmd` runs but the build script fails, times
    out, or doesn't produce the expected output file."""


class FreeCADCancelledError(Exception):
    """Raised when a `cancel_event` is set while `generate_enclosure` is
    still waiting on `freecadcmd` (CTX-105.1) -- distinct from a timeout
    or a build failure, both of which are the subprocess's own doing."""


# How often the wait loop checks in on the subprocess. Short enough that a
# cancel_event set mid-run is noticed promptly, long enough not to busy-spin.
_POLL_INTERVAL_S = 0.1


# Standard per-OS install locations to fall back to if `freecadcmd` isn't
# on PATH (SPEC-104 §3, "Path Resolution"). Globs, since the exact
# version-numbered directory name varies by install.
_CANDIDATE_GLOBS = {
    "Darwin": [
        "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
    ],
    "Linux": [
        "/usr/bin/freecadcmd",
        "/usr/lib/freecad*/bin/freecadcmd",
        "/opt/freecad*/bin/freecadcmd",
        "/snap/freecad/current/usr/bin/freecadcmd",
    ],
    "Windows": [
        r"C:\Program Files\FreeCAD*\bin\freecadcmd.exe",
    ],
}


_path_override = None


def configure(path_override=None):
    """Applies CTX-106.1's daemon-injected config: an explicit
    `freecadcmd` path override, when set, takes priority over the
    PATH/glob search `find_freecadcmd` otherwise falls back to."""
    global _path_override
    _path_override = path_override


def find_freecadcmd() -> str:
    """Locates the `freecadcmd` executable: a configured override first
    (SPEC-106), then PATH, then a handful of standard per-OS install
    locations. Raises a clean error rather than letting a caller hit a
    confusing `FileNotFoundError` from `subprocess`."""
    if _path_override:
        if os.path.isfile(_path_override):
            return _path_override
        raise FreeCADUnavailableError(
            f"Configured freecadcmd path override does not exist: {_path_override}"
        )

    on_path = shutil.which("freecadcmd")
    if on_path:
        return on_path

    for pattern in _CANDIDATE_GLOBS.get(platform.system(), []):
        matches = sorted(glob.glob(pattern), reverse=True)
        if matches:
            return matches[0]

    raise FreeCADUnavailableError(
        "Could not find the freecadcmd executable. Install FreeCAD 0.20+, "
        "or ensure it's on PATH."
    )


_BUILD_SCRIPT_TEMPLATE = """\
import FreeCAD
import Part

doc = FreeCAD.newDocument("enclosure")
box = doc.addObject("Part::Box", "Enclosure")
box.Length = {width}
box.Width = {depth}
box.Height = {height}
doc.recompute()
box.Shape.exportStl({stl_path!r})
"""


def _wait_with_cancellation(proc: subprocess.Popen, timeout_s: float, cancel_event) -> tuple:
    """Polls `proc` in short intervals instead of blocking uninterruptibly
    on a single `communicate(timeout=timeout_s)` call, so a `cancel_event`
    set from another thread (CTX-105.1's job-cancellation path) gets
    noticed and acted on promptly rather than only after the full timeout
    elapses."""
    start = time.monotonic()
    while True:
        try:
            stdout_data, stderr_data = proc.communicate(timeout=_POLL_INTERVAL_S)
            return stdout_data, stderr_data, proc.returncode
        except subprocess.TimeoutExpired:
            if cancel_event is not None and cancel_event.is_set():
                proc.kill()
                proc.communicate()
                raise FreeCADCancelledError("generate_enclosure cancelled before completion")
            if time.monotonic() - start > timeout_s:
                proc.kill()
                proc.communicate()
                raise FreeCADBuildError(f"freecadcmd did not finish within {timeout_s}s")


def generate_enclosure(
    width: float,
    depth: float,
    height: float,
    timeout_s: float = 30.0,
    cancel_event=None,
) -> str:
    """Runs a headless FreeCAD subprocess that builds a parametric box
    enclosure and returns the path to a generated `.glb` mesh.

    FreeCAD's own scripting API has no direct glTF/`.glb` exporter (see
    CTX-104.1 Plan Drift), so the subprocess exports `.stl` — which is
    well-supported — and this function converts that to `.glb` itself via
    `trimesh`, entirely outside the FreeCAD subprocess.

    `cancel_event` (an optional `threading.Event`, CTX-105.1) lets a
    caller running this on a worker thread actually kill the underlying
    `freecadcmd` process early, rather than only stopping the caller's own
    reporting on it once it eventually finishes.
    """
    freecadcmd = find_freecadcmd()

    build_id = uuid.uuid4().hex
    tmp_dir = tempfile.gettempdir()
    script_path = os.path.join(tmp_dir, f"temp_build_{build_id}.py")
    stl_path = os.path.join(tmp_dir, f"enclosure_{build_id}.stl")
    glb_path = os.path.join(tmp_dir, f"enclosure_{build_id}.glb")

    with open(script_path, "w") as f:
        f.write(_BUILD_SCRIPT_TEMPLATE.format(width=width, depth=depth, height=height, stl_path=stl_path))

    try:
        proc = subprocess.Popen(
            [freecadcmd, script_path],
            # freecadcmd drops into an interactive console prompt
            # after running the script and hangs forever waiting on
            # stdin unless it's redirected to hit EOF immediately.
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _stdout_data, stderr_data, returncode = _wait_with_cancellation(proc, timeout_s, cancel_event)

        if returncode != 0:
            raise FreeCADBuildError(
                f"freecadcmd exited with code {returncode}: {stderr_data.strip()}"
            )
        if not os.path.exists(stl_path):
            raise FreeCADBuildError(
                f"freecadcmd exited cleanly but did not produce the expected STL "
                f"file: {stderr_data.strip()}"
            )

        mesh = trimesh.load(stl_path)
        mesh.export(glb_path)
        return glb_path
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)
        if os.path.exists(stl_path):
            os.remove(stl_path)

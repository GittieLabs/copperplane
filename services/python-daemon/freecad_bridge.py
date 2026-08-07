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
import uuid

import trimesh


class FreeCADUnavailableError(Exception):
    """Raised when the `freecadcmd` executable can't be located."""


class FreeCADBuildError(Exception):
    """Raised when `freecadcmd` runs but the build script fails, times
    out, or doesn't produce the expected output file."""


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


def find_freecadcmd() -> str:
    """Locates the `freecadcmd` executable: PATH first, then a handful of
    standard per-OS install locations. Raises a clean error rather than
    letting a caller hit a confusing `FileNotFoundError` from `subprocess`."""
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


def generate_enclosure(width: float, depth: float, height: float, timeout_s: float = 30.0) -> str:
    """Runs a headless FreeCAD subprocess that builds a parametric box
    enclosure and returns the path to a generated `.glb` mesh.

    FreeCAD's own scripting API has no direct glTF/`.glb` exporter (see
    CTX-104.1 Plan Drift), so the subprocess exports `.stl` — which is
    well-supported — and this function converts that to `.glb` itself via
    `trimesh`, entirely outside the FreeCAD subprocess.
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
        try:
            result = subprocess.run(
                [freecadcmd, script_path],
                # freecadcmd drops into an interactive console prompt
                # after running the script and hangs forever waiting on
                # stdin unless it's redirected to hit EOF immediately.
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            raise FreeCADBuildError(f"freecadcmd did not finish within {timeout_s}s") from e

        if result.returncode != 0:
            raise FreeCADBuildError(
                f"freecadcmd exited with code {result.returncode}: {result.stderr.strip()}"
            )
        if not os.path.exists(stl_path):
            raise FreeCADBuildError(
                f"freecadcmd exited cleanly but did not produce the expected STL "
                f"file: {result.stderr.strip()}"
            )

        mesh = trimesh.load(stl_path)
        mesh.export(glb_path)
        return glb_path
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)
        if os.path.exists(stl_path):
            os.remove(stl_path)

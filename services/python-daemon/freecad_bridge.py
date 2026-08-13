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
_output_dir_override = None
_last_glb_path = None
_last_step_path = None


def configure(path_override=None, output_dir=None):
    """Applies CTX-106.1/CTX-301.1's daemon-injected config: an explicit
    `freecadcmd` path override, when set, takes priority over the
    PATH/glob search `find_freecadcmd` otherwise falls back to.
    `output_dir` (SPEC-301 §2), when set, is where `generate_enclosure`
    writes its `.glb` output instead of the shared OS temp directory --
    Rust always sets this to the same directory `tauri.conf.json`'s
    `assetProtocol.scope` is narrowed to."""
    global _path_override, _output_dir_override
    _path_override = path_override
    _output_dir_override = output_dir


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
box.Shape.exportStep({step_path!r})
"""


# SPEC-109: a real hollow shell (outer box minus an inset inner box) with a
# standoff cylinder unioned in at every real mounting-hole position, and a
# fillet applied to every vertical edge of the result -- outer corners and
# the inner cavity's own corners alike, a real and unremarkable enclosure
# design choice, not an oversight. Prototyped and run for real against
# freecadcmd 1.1.1 before being wired in here (CTX-109.1 Plan Drift):
# Part.Shape has no exportStl/exportStep-adjacent helper for "just the
# vertical edges", so they're selected by real geometry -- two straight-line
# vertices whose X and Y agree but whose Z doesn't.
_HOLLOW_SHELL_SCRIPT_TEMPLATE = """\
import FreeCAD
import Part

doc = FreeCAD.newDocument("enclosure")

outer = Part.makeBox({outer_w}, {outer_d}, {height})
inner = Part.makeBox({inner_w}, {inner_d}, {height}, FreeCAD.Vector({wall}, {wall}, 0))
result = outer.cut(inner)

{standoff_lines}
vertical_edges = []
for e in result.Edges:
    verts = e.Vertexes
    if len(verts) == 2:
        v0, v1 = verts[0].Point, verts[1].Point
        dx, dy, dz = abs(v0.x - v1.x), abs(v0.y - v1.y), abs(v0.z - v1.z)
        if dx < 1e-6 and dy < 1e-6 and dz > 1e-6:
            vertical_edges.append(e)

if vertical_edges and {fillet_radius} > 0:
    result = result.makeFillet({fillet_radius}, vertical_edges)

obj = doc.addObject("Part::Feature", "Enclosure")
obj.Shape = result
doc.recompute()
obj.Shape.exportStl({stl_path!r})
obj.Shape.exportStep({step_path!r})
"""

_STANDOFF_CYLINDER_TEMPLATE = (
    "cyl = Part.makeCylinder({radius}, {height}, FreeCAD.Vector({x}, {y}, 0))\n"
    "result = result.fuse(cyl)\n"
)


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
    height: float,
    width: float = None,
    depth: float = None,
    board_outline: dict = None,
    wall_thickness_mm: float = 2.0,
    clearance_mm: float = 0.5,
    standoffs: list = None,
    fillet_radius_mm: float = 1.0,
    timeout_s: float = 30.0,
    cancel_event=None,
) -> dict:
    """Runs a headless FreeCAD subprocess that builds a parametric box
    enclosure and returns `{"glb_path": ..., "step_path": ...}`.

    Two modes (SPEC-109 §2):
    - **Manual dims** (`width`/`depth` given, `board_outline` is `None`):
      the original SPEC-104 plain solid box, byte-for-byte unchanged
      geometry -- SPEC-109 §3's explicit no-board-data fallback, for a
      project with no live KiCad connection.
    - **Board-driven** (`board_outline` given -- `kicad_bridge.get_board_
      outline`'s real return shape): a real hollow shell sized from the
      board outline plus `clearance_mm` plus `wall_thickness_mm` on every
      side, with a standoff cylinder at every real `standoffs` position
      (each `{"x_mm", "y_mm", "diameter_mm", "height_mm"}`), and
      `fillet_radius_mm` applied to every vertical edge of the result --
      the outer corners and the inner cavity's own corners alike, a real
      and unremarkable design choice, not an oversight. `height` is
      always required in both modes -- a board outline is 2D and has no Z
      dimension to derive it from.

    FreeCAD's own scripting API has no direct glTF/`.glb` exporter (see
    CTX-104.1 Plan Drift), so the subprocess exports `.stl` — which is
    well-supported — and this function converts that to `.glb` itself via
    `trimesh`, entirely outside the FreeCAD subprocess. `.step` (SPEC-109's
    own real mechanical-CAD interchange requirement) is exported by the
    subprocess directly, alongside `.stl`, from the same final shape.

    `cancel_event` (an optional `threading.Event`, CTX-105.1) lets a
    caller running this on a worker thread actually kill the underlying
    `freecadcmd` process early, rather than only stopping the caller's own
    reporting on it once it eventually finishes.

    Both returned files land in the configured `output_dir` (SPEC-301 §2)
    if one was set, or the shared OS temp directory otherwise (e.g.
    running this module standalone, outside the Tauri app). The
    intermediate script and `.stl` always use the OS temp directory --
    only the persistent outputs a frontend or another CAD tool might load
    need to live somewhere `assetProtocol.scope` can be narrowed to.
    """
    global _last_glb_path, _last_step_path

    if board_outline is None and (width is None or depth is None):
        raise ValueError(
            "generate_enclosure requires either board_outline, or width and depth "
            "for the no-board-data fallback."
        )

    freecadcmd = find_freecadcmd()

    build_id = uuid.uuid4().hex
    tmp_dir = tempfile.gettempdir()
    script_path = os.path.join(tmp_dir, f"temp_build_{build_id}.py")
    stl_path = os.path.join(tmp_dir, f"enclosure_{build_id}.stl")

    output_dir = _output_dir_override or tmp_dir
    os.makedirs(output_dir, exist_ok=True)
    glb_path = os.path.join(output_dir, f"enclosure_{build_id}.glb")
    step_path = os.path.join(output_dir, f"enclosure_{build_id}.step")

    if board_outline is None:
        script = _BUILD_SCRIPT_TEMPLATE.format(
            width=width, depth=depth, height=height, stl_path=stl_path, step_path=step_path,
        )
    else:
        margin = clearance_mm + wall_thickness_mm
        outer_w = board_outline["width_mm"] + 2 * margin
        outer_d = board_outline["height_mm"] + 2 * margin
        # Each standoff sits at the real hole position relative to the
        # board outline's own origin, offset by the same margin that
        # positions the board inside the shell. The template's own
        # boolean cut line runs unconditionally above this -- these are
        # purely the additional fuse() calls appended after it.
        standoff_lines = "".join(
            _STANDOFF_CYLINDER_TEMPLATE.format(
                radius=s["diameter_mm"] / 2,
                height=s["height_mm"],
                x=s["x_mm"] - board_outline["x_mm"] + margin,
                y=s["y_mm"] - board_outline["y_mm"] + margin,
            )
            for s in (standoffs or [])
        )
        script = _HOLLOW_SHELL_SCRIPT_TEMPLATE.format(
            outer_w=outer_w,
            outer_d=outer_d,
            inner_w=board_outline["width_mm"] + 2 * clearance_mm,
            inner_d=board_outline["height_mm"] + 2 * clearance_mm,
            wall=wall_thickness_mm,
            height=height,
            standoff_lines=standoff_lines,
            fillet_radius=fillet_radius_mm,
            stl_path=stl_path,
            step_path=step_path,
        )

    with open(script_path, "w") as f:
        f.write(script)

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
        if not os.path.exists(step_path):
            raise FreeCADBuildError(
                f"freecadcmd exited cleanly but did not produce the expected STEP "
                f"file: {stderr_data.strip()}"
            )

        mesh = trimesh.load(stl_path)
        mesh.export(glb_path)

        # SPEC-301 §3's flagged known debt: nothing previously deleted a
        # generated .glb (harmless in a self-cleaning OS temp dir, a real
        # leak in a persistent output_dir). Deleting the *previous*
        # successful output on each new success bounds the leak to at
        # most one extra file at a time, rather than unbounded growth.
        # Deliberately not zero: a daemon killed/restarted mid-session
        # never cleans up its very last output. See CTX-301.1 Plan Drift.
        # Applies to .step now too, the same real persistent-output leak.
        if _last_glb_path and _last_glb_path != glb_path and os.path.exists(_last_glb_path):
            os.remove(_last_glb_path)
        _last_glb_path = glb_path
        if _last_step_path and _last_step_path != step_path and os.path.exists(_last_step_path):
            os.remove(_last_step_path)
        _last_step_path = step_path

        return {"glb_path": glb_path, "step_path": step_path}
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)
        if os.path.exists(stl_path):
            os.remove(stl_path)

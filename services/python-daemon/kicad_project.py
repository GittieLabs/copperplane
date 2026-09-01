"""SPEC-325: resolve a KiCad project file to the files it owns.

The app's existing path derives a schematic from whatever board KiCad
currently has open, over the IPC API (`kicad_bridge.list_project_schematics`).
That needs KiCad running, its API enabled, and the right document focused --
three preconditions, each a silent failure mode, for a fact that is sitting
in a file.

A `.kicad_pro` is JSON, and KiCad's own convention names its siblings after
the project rather than after any individual file. `kicad_bridge` already
relies on that convention for the same reason; this reads it from disk
instead of from a running editor.

Nothing here writes, and nothing here needs KiCad running.
"""
from __future__ import annotations

import json
import os


class KicadProjectError(Exception):
    """A project file that cannot be read or does not resolve, reported
    with a specific reason rather than a bare OSError/KeyError."""


def resolve_project(pro_path: str) -> dict:
    """The schematic and PCB a `.kicad_pro` owns.

    Returns `{"project_name", "project_dir", "pro_path", "schematic_path",
    "pcb_path", "sheet_count"}`. `schematic_path`/`pcb_path` are `None`
    when the file is genuinely absent -- a project with no board yet is an
    ordinary state, not an error, and saying "no PCB" is more useful than
    refusing to load the project at all.

    `sheet_count` comes from the project's own `sheets` list. It is
    reported rather than acted on: whether `kicad-cli sch export bom`
    walks a hierarchy from the root sheet is **unverified** (SPEC-325 §3),
    so a caller can at least tell that a project has more than one sheet
    and treat its component list with appropriate suspicion.
    """
    if not pro_path or not pro_path.endswith(".kicad_pro"):
        raise KicadProjectError(
            f"Not a KiCad project file: {pro_path!r}. Expected a path ending in .kicad_pro."
        )
    if not os.path.isfile(pro_path):
        raise KicadProjectError(f"KiCad project file does not exist: {pro_path}")

    try:
        with open(pro_path, encoding="utf-8") as handle:
            project = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise KicadProjectError(f"Could not read {pro_path}: {exc}") from exc

    project_dir = os.path.dirname(os.path.abspath(pro_path))
    stem = os.path.splitext(os.path.basename(pro_path))[0]

    def sibling(ext: str) -> str | None:
        candidate = os.path.join(project_dir, stem + ext)
        return candidate if os.path.isfile(candidate) else None

    sheets = project.get("sheets")
    return {
        "project_name": stem,
        "project_dir": project_dir,
        "pro_path": os.path.abspath(pro_path),
        "schematic_path": sibling(".kicad_sch"),
        "pcb_path": sibling(".kicad_pcb"),
        "sheet_count": len(sheets) if isinstance(sheets, list) else None,
    }

"""
Real board outline + mounting-hole extraction from a `.kicad_pcb` FILE,
independent of any live KiCad connection (SPEC-310) -- unlike
kicad_bridge.get_board_outline/get_mounting_holes, which require a live
IPC session and can only ever read whatever board KiCad currently has
open.

Uses kicad-cli's own real DXF and Excellon drill export (the same real
subprocess pattern kicad_cli.py already established for ERC/DRC) rather
than parsing the .kicad_pcb S-expression format directly, or using a
third-party parser. This choice was verified, not assumed: kiutils 1.4.8
(the latest PyPI release), a real third-party KiCad-file-parsing
library, crashed with a real IndexError on a real, current KiCad 10
board file during this spec's own research -- a genuine compatibility
gap in that library, not something in this project's control.
kicad-cli's own DXF/drill export is guaranteed to match whatever KiCad
version actually wrote the file, since the same real KiCad install
produces both.
"""
import glob
import os
import re
import subprocess
import tempfile

import kicad_cli


class BoardOutlineMissingError(Exception):
    """Raised when a .kicad_pcb file has no Edge.Cuts geometry at all --
    mirrors kicad_bridge.BoardOutlineMissingError's own real message for
    the live path, applied here to the file-based one."""


def _run_dxf_export(pcb_path: str) -> str:
    """Runs kicad-cli pcb export dxf, restricted to Edge.Cuts, and
    returns the real DXF text. A thin wrapper around kicad_cli's own
    subprocess machinery -- kicad_cli.py doesn't expose a generic
    "export" helper today (only run_erc/run_drc), so this calls its
    real, private _run_report-equivalent shape directly rather than
    duplicating find_kicad_cli's own real location logic."""
    cli = kicad_cli.find_kicad_cli()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "outline.dxf")
        result = subprocess.run(
            [cli, "pcb", "export", "dxf", "--layers", "Edge.Cuts", "--mode-single",
             "--output-units", "mm", "-o", out_path, pcb_path],
            capture_output=True, text=True, timeout=60,
        )
        if not os.path.exists(out_path):
            raise kicad_cli.KicadCliError(
                f"kicad-cli did not produce a DXF outline export (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
        with open(out_path, encoding="utf-8") as f:
            return f.read()


def _run_drill_export(pcb_path: str) -> str:
    """Runs kicad-cli pcb export drill (Excellon format) and returns the
    real drill file text. kicad-cli writes it to <board_name>.drl inside
    the output directory -- the exact filename isn't predictable from
    the CLI invocation alone (it's derived from the board's own name),
    so this looks for whatever .drl file actually appeared rather than
    guessing the name."""
    cli = kicad_cli.find_kicad_cli()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [cli, "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm",
             "-o", tmpdir + os.sep, pcb_path],
            capture_output=True, text=True, timeout=60,
        )
        drl_files = glob.glob(os.path.join(tmpdir, "*.drl"))
        if not drl_files:
            raise kicad_cli.KicadCliError(
                f"kicad-cli did not produce a drill export (exit {result.returncode}): "
                f"{result.stderr.strip()}"
            )
        with open(drl_files[0], encoding="utf-8") as f:
            return f.read()


def _parse_dxf_edge_cuts_bbox(dxf_text: str) -> dict:
    """A small, purpose-built DXF reader -- not a general DXF library,
    just enough to compute a real bounding box from the entity types
    kicad-cli's own Edge.Cuts export actually produces. Real ARC
    handling is a conservative over-approximation (the arc's own full
    circle bbox, center +/- radius) -- always safe (never smaller than
    the arc's true extent), simple, and explicitly not verified against
    a real rounded-corner board this session (see CTX-310.1 Plan
    Drift). LWPOLYLINE vertices are each included directly."""
    lines = [line.strip() for line in dxf_text.splitlines() if line.strip() != ""]
    pairs = []
    i = 0
    while i + 1 < len(lines):
        try:
            code = int(lines[i])
        except ValueError:
            i += 1
            continue
        pairs.append((code, lines[i + 1]))
        i += 2

    xs, ys = [], []
    in_entities = False
    entity_type = None
    cur = {}
    pending_lwpoly_x = None

    def flush():
        if entity_type == "LINE" and {"10", "20", "11", "21"} <= cur.keys():
            xs.extend([cur["10"], cur["11"]])
            ys.extend([cur["20"], cur["21"]])
        elif entity_type in ("CIRCLE", "ARC") and {"10", "20", "40"} <= cur.keys():
            cx, cy, r = cur["10"], cur["20"], cur["40"]
            xs.extend([cx - r, cx + r])
            ys.extend([cy - r, cy + r])
        elif entity_type == "LWPOLYLINE":
            for vx, vy in cur.get("vertices", []):
                xs.append(vx)
                ys.append(vy)

    for code, value in pairs:
        if code == 0:
            if entity_type is not None:
                flush()
            entity_type = value if (in_entities and value in ("LINE", "CIRCLE", "ARC", "LWPOLYLINE")) else None
            cur = {}
            pending_lwpoly_x = None
            if value == "ENDSEC":
                in_entities = False
            continue

        if code == 2 and value == "ENTITIES":
            in_entities = True
            continue

        if entity_type is None:
            continue

        if entity_type == "LWPOLYLINE" and code in (10, 20):
            cur.setdefault("vertices", [])
            if code == 10:
                pending_lwpoly_x = float(value)
            elif pending_lwpoly_x is not None:
                # Y negated -- see the group-code branch below for why.
                cur["vertices"].append((pending_lwpoly_x, -float(value)))
                pending_lwpoly_x = None
        elif code in (10, 20, 11, 21, 40):
            # kicad-cli's DXF export uses the standard drafting convention
            # (Y increases upward) -- confirmed for real against
            # board_with_outline.kicad_pcb, whose Edge.Cuts rectangle is
            # (0,0)-(50,30) in the .kicad_pcb file's own raw coordinates
            # (the same convention kicad_bridge.get_board_outline's live
            # IPC path uses, straight from bbox.pos): the real DXF export
            # comes back as (0,0)-(50,-30), an exact Y-axis sign flip with
            # no offset. Y (codes 20/21) is negated here so this file-based
            # path returns the same coordinate convention the live path
            # already does -- otherwise freecad_bridge.generate_enclosure's
            # standoff-relative-to-outline placement would come out
            # vertically mirrored for any board whose mounting holes aren't
            # symmetric top-to-bottom.
            cur[str(code)] = -float(value) if code in (20, 21) else float(value)

    if entity_type is not None:
        flush()

    if not xs or not ys:
        raise BoardOutlineMissingError(
            "This board file has no Edge.Cuts geometry -- draw a real board outline in KiCad "
            "before generating an enclosure from it."
        )

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return {"x_mm": min_x, "y_mm": min_y, "width_mm": max_x - min_x, "height_mm": max_y - min_y}


_TOOL_DEF_RE = re.compile(r"^T(\d+)C([\d.]+)$")
_TOOL_SELECT_RE = re.compile(r"^T(\d+)$")
_COORD_RE = re.compile(r"^X(-?[\d.]+)Y(-?[\d.]+)$")


def _parse_excellon_npth_holes(drill_text: str) -> list:
    """A real Excellon drill file: tool definitions (T<N>C<diameter_mm>)
    each preceded by a real `; #@! TA.AperFunction,{Plated,PTH|
    NonPlated,NPTH},...` comment classifying the hole type -- KiCad's own
    real, unambiguous PTH/NPTH signal, confirmed against real board
    files, not guessed. Only NPTH-tooled holes are returned (SPEC-310
    §2's own real, accepted tradeoff -- PTH holes are component leads/
    vias, never mounting-standoff candidates), each with
    `recognized: True` -- there's no footprint-library/refdes signal
    available from a drill file the way live IPC's `recognized` flag
    uses, so every NPTH hole here is treated as a real candidate,
    matching the shape kicad_bridge.get_mounting_holes' own live NPTH
    entries already have."""
    npth_tools = set()
    tool_diameters = {}
    pending_npth = False

    for raw_line in drill_text.splitlines():
        line = raw_line.strip()
        if line.startswith("; #@! TA.AperFunction,NonPlated,NPTH"):
            pending_npth = True
            continue
        if line.startswith("; #@! TA.AperFunction,Plated,PTH"):
            pending_npth = False
            continue

        match = _TOOL_DEF_RE.match(line)
        if match:
            tool_num = int(match.group(1))
            tool_diameters[tool_num] = float(match.group(2))
            if pending_npth:
                npth_tools.add(tool_num)

    holes = []
    current_tool = None
    for raw_line in drill_text.splitlines():
        line = raw_line.strip()
        select = _TOOL_SELECT_RE.match(line)
        if select:
            current_tool = int(select.group(1))
            continue

        coord = _COORD_RE.match(line)
        if coord and current_tool is not None and current_tool in npth_tools:
            holes.append({
                "x_mm": float(coord.group(1)),
                # Y negated -- kicad-cli's Excellon export uses the same
                # drafting Y-up convention DXF export does (confirmed for
                # real, same fixture); see the DXF parser's own comment
                # in _parse_dxf_edge_cuts_bbox for the full explanation.
                "y_mm": -float(coord.group(2)),
                "diameter_mm": tool_diameters.get(current_tool, 0.0),
                "recognized": True,
            })

    return holes


def extract_board_outline(pcb_path: str) -> dict:
    """Returns {x_mm, y_mm, width_mm, height_mm} -- exactly
    kicad_bridge.get_board_outline's own real live shape, from a real
    .kicad_pcb file instead of a live connection."""
    dxf_text = _run_dxf_export(pcb_path)
    return _parse_dxf_edge_cuts_bbox(dxf_text)


def extract_mounting_holes(pcb_path: str) -> list:
    """Returns [{x_mm, y_mm, diameter_mm, recognized}] -- exactly
    kicad_bridge.get_mounting_holes' own real live shape (already
    filtered to NPTH-only, always recognized=True; see
    _parse_excellon_npth_holes's own docstring for why)."""
    drill_text = _run_drill_export(pcb_path)
    return _parse_excellon_npth_holes(drill_text)

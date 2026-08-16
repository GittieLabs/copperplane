"""
Connection lifecycle to a running KiCad instance via the IPC API
(SPEC-103). The connection is opened lazily on first use and held open
for the rest of the daemon's life, to avoid paying a handshake on every
call.
"""
import logging
import os
import re

from kipy import KiCad
from kipy.board_types import PadType
from kipy.errors import ApiError, ConnectionError as KiCadConnectionError, FutureVersionError
from kipy.geometry import Vector2
from kipy.proto.common.types import DocumentType
from kipy.util.board_layer import BoardLayer

import kicad_write

logger = logging.getLogger(__name__)

# kipy's internal unit is nanometers (confirmed against Vector2.from_xy_mm's
# own round trip) -- every board-read function below converts back to mm
# explicitly, the same conversion CTX-108.1 already established on the
# KiCad-write side of this same boundary.
_NM_PER_MM = 1_000_000

# SPEC-109 §2: a footprint is a recognized mounting hole when it comes from
# KiCad's own standard MountingHole library, or carries that library's
# default H<digits> reference-designator convention -- not a one-off
# heuristic invented here.
_MOUNTING_HOLE_REF_PATTERN = re.compile(r"^H\d+$")


class KiCadUnavailableError(Exception):
    """Raised whenever KiCad can't be reached, with a clean, user-facing
    message instead of a raw kipy traceback."""


class KiCadWriteError(Exception):
    """Raised when injecting a component into the open board fails --
    an unsupported package (kicad_write.UnsupportedPackageError) or a
    real KiCad API failure during the write itself. The board is left
    unchanged either way: drop_commit runs on any failure before the
    commit is pushed."""


class BoardOutlineMissingError(Exception):
    """Raised when the board has no Edge.Cuts shapes at all -- SPEC-109
    requires a real, designed board edge to size an enclosure against,
    never a silently guessed size."""


def _nm_to_mm(value_nm: int) -> float:
    return value_nm / _NM_PER_MM


_client = None
_socket_path_override = None
_timeout_ms_override = None


def configure(socket_path=None, timeout_ms=None):
    """Applies CTX-106.1's daemon-injected config. Resets the held-open
    client so the *next* `get_client()` call reconnects using these
    settings -- without this, a config change wouldn't take effect until
    a full daemon restart, since the client is normally held open for the
    daemon's whole life (SPEC-103 §2)."""
    global _socket_path_override, _timeout_ms_override, _client
    _socket_path_override = socket_path
    _timeout_ms_override = timeout_ms
    _client = None


def get_client() -> KiCad:
    """Returns the held-open KiCad client, connecting on first use with
    any configured `socket_path`/`timeout_ms` override (SPEC-106)."""
    global _client
    if _client is not None:
        return _client

    kwargs = {}
    if _socket_path_override:
        kwargs["socket_path"] = _socket_path_override
    if _timeout_ms_override:
        kwargs["timeout_ms"] = _timeout_ms_override

    client = KiCad(**kwargs)
    try:
        client.check_version()
    except FutureVersionError:
        # kicad-python's declared API version routinely lags a few patch
        # releases behind the actual KiCad app (e.g. package built against
        # 10.0.1, app is 10.0.3) — this is normal and not worth blocking
        # the connection over, since patch releases don't break the wire
        # protocol. Only a genuine unreachable/incompatible KiCad (caught
        # below) should stop the daemon from connecting.
        logger.warning(
            "KiCad reports a newer version than kicad-python declares support "
            "for; continuing anyway since this is usually just package lag."
        )
    except (KiCadConnectionError, ApiError) as e:
        raise KiCadUnavailableError(
            "Could not connect to KiCad. Ensure KiCad 9 or later is running "
            "with the IPC API enabled (Preferences > Plugins)."
        ) from e

    _client = client
    return _client


def reset_connection() -> None:
    """Drops the held connection so the next call reconnects from scratch.
    Call this after a broken-pipe/State-Desync error (SPEC-103 §3) — the
    old client's socket is unusable once the connection has failed."""
    global _client
    _client = None


def get_kicad_version() -> dict:
    """Real, read-only round trip proving the bridge: returns KiCad's own
    version. A mid-call disconnect (e.g. the user closes KiCad) is caught
    and re-raised as `KiCadUnavailableError` rather than an unhandled
    exception that would take down the daemon."""
    client = get_client()
    try:
        version = client.get_version()
    except (KiCadConnectionError, ApiError) as e:
        reset_connection()
        raise KiCadUnavailableError(
            "Lost connection to KiCad mid-request. It may have been closed."
        ) from e

    return {
        "full_version": version.full_version,
        "major": version.major,
        "minor": version.minor,
        "patch": version.patch,
    }


def get_open_board_path() -> str | None:
    """SPEC-309: resolves the real, full filesystem path of whatever
    board is currently open in KiCad -- `project.path` + `board_filename`
    from `get_open_documents(DOCTYPE_PCB)`, confirmed live against a real
    running KiCad 10.0.3 instance during SPEC-309's own research. Returns
    `None` if nothing is open, rather than raising -- "no board open" is
    a normal, expected state for the board-advisor route to handle
    (report it plainly and ask for an explicit path), not an error.

    Deliberately PCB-only: the identical call for `DOCTYPE_SCHEMATIC`
    raises a real `no handler available` `ApiError` -- confirmed the
    same way, not assumed -- so this function doesn't attempt it; the
    schematic side of SPEC-309 always needs an explicit user-supplied
    path."""
    client = get_client()
    try:
        docs = list(client.get_open_documents(DocumentType.DOCTYPE_PCB))
    except (KiCadConnectionError, ApiError) as e:
        reset_connection()
        raise KiCadUnavailableError(
            "Lost connection to KiCad mid-request. It may have been closed."
        ) from e

    if not docs:
        return None

    doc = docs[0]
    return os.path.join(doc.project.path, doc.board_filename)


def get_board_outline() -> dict:
    """SPEC-109: unions every real Edge.Cuts shape's own `bounding_box`
    into one real board bounding box, in mm. A bounding box is the real,
    sufficient board-outline data for SPEC-109's fixed-rectangular-
    enclosure scope -- not a fallback standing in for a true polygon
    trace this spec was never going to build."""
    client = get_client()
    try:
        board = client.get_board()
        shapes = board.get_shapes()
    except (KiCadConnectionError, ApiError) as e:
        reset_connection()
        raise KiCadUnavailableError(
            "Lost connection to KiCad mid-request. It may have been closed."
        ) from e

    edge_shapes = [s for s in shapes if s.layer == BoardLayer.BL_Edge_Cuts]
    if not edge_shapes:
        raise BoardOutlineMissingError(
            "This board has no Edge.Cuts shapes -- draw a real board outline in KiCad "
            "before generating an enclosure from it."
        )

    bbox = edge_shapes[0].bounding_box()
    for shape in edge_shapes[1:]:
        bbox.merge(shape.bounding_box())

    return {
        "x_mm": _nm_to_mm(bbox.pos.x),
        "y_mm": _nm_to_mm(bbox.pos.y),
        "width_mm": _nm_to_mm(bbox.size.x),
        "height_mm": _nm_to_mm(bbox.size.y),
    }


def get_mounting_holes() -> list:
    """SPEC-109: reads real FootprintInstance items (not raw pads --
    Board.get_pads() returns Pad objects with no link back to their
    parent footprint). A footprint is a recognized mounting hole when it
    comes from KiCad's own standard MountingHole library, or carries that
    library's default H<digits> reference-designator convention -- not a
    one-off heuristic invented here. Every real non-plated-through-hole
    (NPTH) pad is returned with its real position (the footprint
    instance's own absolute board position -- correct for KiCad's
    MountingHole library, whose single NPTH pad sits at the footprint's
    local origin) and drill diameter in mm, flagged `recognized`. An
    NPTH on an unrecognized footprint is still returned, not dropped --
    SPEC-109 §3 fails closed on ambiguity at the calling route, not
    silently here."""
    client = get_client()
    try:
        board = client.get_board()
        footprints = board.get_footprints()
    except (KiCadConnectionError, ApiError) as e:
        reset_connection()
        raise KiCadUnavailableError(
            "Lost connection to KiCad mid-request. It may have been closed."
        ) from e

    holes = []
    for fp in footprints:
        library = (fp.definition.id.library or "").lower()
        reference = fp.reference_field.text.value if fp.reference_field else ""
        recognized = "mountinghole" in library or bool(_MOUNTING_HOLE_REF_PATTERN.match(reference))

        for pad in fp.definition.pads:
            if pad.pad_type != PadType.PT_NPTH:
                continue
            holes.append({
                "x_mm": _nm_to_mm(fp.position.x),
                "y_mm": _nm_to_mm(fp.position.y),
                "diameter_mm": _nm_to_mm(pad.padstack.drill.diameter.x),
                "recognized": recognized,
            })

    return holes


def inject_component(schema: dict, position_mm: tuple) -> dict:
    """The kicad.inject_component route (SPEC-108): builds a real
    FootprintInstance from a SPEC-202-validated schema and writes it
    into the board KiCad already has open, at `position_mm`. Mutates
    the board the instant it's called -- no confirmation check of its
    own; the caller (eventually SPEC-204's gate) is solely responsible
    for only invoking this after approval.

    Reuses get_client() unchanged -- no additional version-check
    strictness for writes beyond CTX-103.1's existing
    FutureVersionError warning (see CTX-108.1 Plan Drift)."""
    client = get_client()

    try:
        board = client.get_board()
    except (KiCadConnectionError, ApiError) as e:
        reset_connection()
        raise KiCadUnavailableError(
            "Lost connection to KiCad mid-request. It may have been closed."
        ) from e

    try:
        pin_numbers = [pin["number"] for pin in schema["pins"]]
        pads = kicad_write.generate_pad_layout(schema["package"], pin_numbers, schema["package_dimensions"])
        footprint = kicad_write.build_footprint_instance(schema, pads, schema["courtyard"])
    except kicad_write.UnsupportedPackageError as e:
        raise KiCadWriteError(str(e)) from e

    footprint.position = Vector2.from_xy_mm(*position_mm)

    commit = board.begin_commit()
    try:
        board.create_items([footprint])
    except Exception as e:
        board.drop_commit(commit)
        raise KiCadWriteError(f"Failed to write '{schema['part_number']}' to the board: {e}") from e

    board.push_commit(commit, f"Add {schema['part_number']}")

    try:
        board.save()
    except Exception as e:
        raise KiCadWriteError(
            f"'{schema['part_number']}' was added in KiCad but the board file could not be saved: {e}"
        ) from e

    return {"part_number": schema["part_number"], "package": schema["package"], "pins": len(pads)}

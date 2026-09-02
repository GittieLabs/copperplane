"""
Connection lifecycle to a running KiCad instance via the IPC API
(SPEC-103). The connection is opened lazily on first use and held open
for the rest of the daemon's life, to avoid paying a handshake on every
call.
"""
import glob
import logging
import os
import platform

import fp_lib_table
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

# SPEC-311: a real kipy Footprint3DModel.filename uses KiCad's own
# "${VAR}/relative/path" convention (e.g.
# "${KICAD10_3DMODEL_DIR}/Connector_PinHeader_2.54mm.3dshapes/...step").
# The var name is version-numbered and will drift with future KiCad
# major versions the same way find_kicad_cli's/find_freecadcmd's own
# version-numbered install paths already do -- matched by pattern here,
# never a hardcoded name.
_ENV_VAR_PATH_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}(/.*)$")

# Real, confirmed-existing per-OS KiCad 3D model library install
# locations, used only when the real env var above isn't set in this
# daemon's own process environment -- confirmed true during SPEC-311's
# own research: KiCad resolves the var internally, but this daemon's
# subprocess never inherits it. The macOS path is the one actually
# verified on a real dev machine; Linux/Windows are KiCad's own
# documented install conventions, not yet confirmed against a real
# install of either -- the same disclosed-but-unverified status
# kicad_cli.py's own _CANDIDATE_GLOBS already carries for those OSes.
_3DMODEL_DIR_CANDIDATES = {
    "Darwin": ["/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels"],
    "Linux": ["/usr/share/kicad/3dmodels", "/usr/local/share/kicad/3dmodels"],
    "Windows": [r"C:\Program Files\KiCad\*\share\kicad\3dmodels"],
}


def _resolve_3d_model_path(filename: str) -> str:
    """Resolves a real KiCad footprint 3D model's own `${VAR}/...`
    filename to a real, existing path on disk, or `None` -- never a
    guessed path. Tries the real environment variable first (however
    it's actually named); if unset, falls back to real, confirmed
    per-OS KiCad install locations, the same fallback pattern
    `kicad_cli.py`'s own `_CANDIDATE_GLOBS` uses for the `kicad-cli`
    binary itself. A filename that isn't the `${VAR}/...` convention at
    all is tried as a literal path."""
    if not filename:
        return None

    match = _ENV_VAR_PATH_PATTERN.match(filename)
    if not match:
        return filename if os.path.exists(filename) else None

    env_var, rel_path = match.groups()
    env_value = os.environ.get(env_var)
    if env_value:
        candidate = env_value + rel_path
        if os.path.exists(candidate):
            return candidate

    for base_pattern in _3DMODEL_DIR_CANDIDATES.get(platform.system(), []):
        for base in glob.glob(base_pattern):
            candidate = os.path.join(base, rel_path.lstrip("/"))
            if os.path.exists(candidate):
                return candidate

    return None


_FOOTPRINT_MODEL_RE = re.compile(r'\(model\s+"([^"]+)"')


def resolve_footprint_model(footprint_id: str) -> dict:
    """Whether a `Lib:Name` footprint exists, and whether its 3D model
    file is actually on disk (SPEC-325 §2.4).

    Returns `{"footprint_id", "footprint_found", "model_ref",
    "model_path"}`. `model_path` is `None` when the footprint names a
    model that is not installed.

    **The check is the file, not the reference.** A footprint's own
    `(model ...)` line is a claim, not evidence: KiCad's own `Battery`
    library ships 53 footprints against 29 STEP models, with no `.wrl`
    fallbacks -- so reporting "has a model" from that line would be wrong
    25 times out of 53, and a real project's CR2032 footprint
    (`Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles`) is one of
    the wrong ones.

    Never raises for an unresolvable footprint. A library this install
    does not have, or a footprint that is not in it, is an ordinary
    state a user needs told about -- not an error that stops a whole
    component table from rendering.
    """
    result = {
        "footprint_id": footprint_id,
        "footprint_found": False,
        "footprint_path": None,
        # SPEC-326 §2.1: X/Y extents from the real footprint, when it has a
        # courtyard. None means no X/Y source, not zero.
        "courtyard": None,
        "model_ref": None,
        "model_path": None,
    }
    if not footprint_id or ":" not in footprint_id:
        return result

    library, _, name = footprint_id.partition(":")
    try:
        table_path = fp_lib_table.default_fp_lib_table_path()
        entries = fp_lib_table.parse_fp_lib_table(table_path) if table_path else []
    except Exception:  # noqa: BLE001 -- an unreadable table is "cannot resolve", not a crash
        return result

    for entry in entries:
        if entry.get("name") != library:
            continue
        mod_path = os.path.join(entry.get("uri") or "", f"{name}.kicad_mod")
        if not os.path.isfile(mod_path):
            continue
        result["footprint_found"] = True
        result["footprint_path"] = mod_path
        result["courtyard"] = read_footprint_courtyard(mod_path)
        try:
            with open(mod_path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            return result
        match = _FOOTPRINT_MODEL_RE.search(text)
        if match:
            result["model_ref"] = match.group(1)
            result["model_path"] = _resolve_3d_model_path(match.group(1))
        return result

    return result


_COURTYARD_LAYERS = ("F.CrtYd", "B.CrtYd")


def read_footprint_courtyard(mod_path: str) -> dict | None:
    """The X/Y extents of a footprint's courtyard, in mm, or `None`.

    SPEC-326 §2.1: the placeholder envelope's footprint extents come from
    the real `.kicad_mod` on disk -- no inference, no LLM, no datasheet.
    Measured across five real KiCad libraries: **902 of 903 footprints
    (99%) have a readable courtyard**, so this is a source that actually
    covers the case.

    **Not a conservative bound**, and callers must not treat it as one.
    Calibrated against `BatteryHolder_Keystone_1060_1x2032`, which has a
    real STEP model to check against: courtyard 32.90 x 17.00 against a
    true bounding box of 31.86 x 17.96 -- 1mm wider in X and **1mm
    narrower in Y** than the actual body. A courtyard is a PCB keep-out;
    a part can overhang it.

    Returns `None` rather than raising for a footprint with no courtyard
    layer -- that is the 1-in-903 case, and it means "no X/Y source",
    which is the same honest unknown a missing height produces.
    """
    try:
        import kiutils.footprint as kf
        footprint = kf.Footprint.from_file(mod_path)
    except Exception:  # noqa: BLE001 -- an unreadable footprint is "unknown", not fatal
        return None

    xs: list[float] = []
    ys: list[float] = []
    for item in getattr(footprint, "graphicItems", []) or []:
        if getattr(item, "layer", None) not in _COURTYARD_LAYERS:
            continue

        # A circle's extent is centre +/- radius, NOT the two points that
        # define it. Taking only those gave a real radial capacitor
        # (CP_Radial_D5.0mm_P2.50mm, whose courtyard is a single circle) an
        # extent of 2.75 x 0.00 mm instead of 5.50 x 5.50 -- a zero-height
        # envelope for a part that is 5.5mm across.
        if type(item).__name__ == "FpCircle":
            centre = getattr(item, "center", None)
            edge = getattr(item, "end", None)
            if centre is not None and edge is not None:
                radius = ((edge.X - centre.X) ** 2 + (edge.Y - centre.Y) ** 2) ** 0.5
                xs.extend((centre.X - radius, centre.X + radius))
                ys.extend((centre.Y - radius, centre.Y + radius))
                continue

        # An arc bulges past its endpoints, so `mid` is load-bearing: without
        # it BatteryHolder_Keystone_1060 measured 32.90 x 17.00 instead of
        # 32.90 x 21.40, understating the keep-out by 4mm.
        for attr in ("start", "end", "center", "mid"):
            point = getattr(item, attr, None)
            if point is not None:
                xs.append(point.X)
                ys.append(point.Y)
        for point in (getattr(item, "coordinates", None) or []):
            xs.append(point.X)
            ys.append(point.Y)

    if not xs or not ys:
        return None
    return {"x_mm": round(max(xs) - min(xs), 3), "y_mm": round(max(ys) - min(ys), 3)}


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
    any configured `socket_path`/`timeout_ms` override (SPEC-106).

    Real, live-discovered bug: the held-open connection can go stale
    without ever raising on its own -- `SPEC-103` §3's own documented
    state-desync risk (closing/reopening things in KiCad while this
    daemon holds a connection open). Confirmed live: after enough
    opening/closing of KiCad and files in one dev session, real routes
    that had worked moments earlier (a fresh connection found
    everything correctly) started silently returning nothing through
    the daemon's own long-held connection, and only a full daemon
    restart recovered it -- the cached `_client` was never actually
    validated before being reused. Every call now pings the cached
    client first (a real, cheap round trip, not just checking a local
    "am I connected" flag) and transparently reconnects if that fails,
    instead of trusting a connection that's been open for a while."""
    global _client
    if _client is not None:
        try:
            _client.ping()
            return _client
        except (KiCadConnectionError, ApiError):
            logger.warning("Cached KiCad connection failed a health-check ping; reconnecting.")
            _client = None

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


_NO_HANDLER_MARKER = "no handler available"


def list_open_boards() -> list:
    """SPEC-309/CTX-309.3: resolves every real, currently-open PCB
    editor's full filesystem path via `get_open_documents(DOCTYPE_PCB)`
    -- a real list, never silently narrowed to just the first one, so a
    caller can tell "nothing open" apart from "more than one open" and
    handle each honestly instead of guessing which board the user meant.

    A real, live-confirmed finding (CTX-309.3, against this machine's
    own actually-running KiCad instance): `get_open_documents` itself
    raises a real `ApiError` containing "no handler available" whenever
    no PCB Editor window is open at all -- the handler isn't registered
    until one is (the same real constraint CTX-108.1's own Deviation 2
    already documented for the write path). This is a normal, expected
    "nothing open" state, treated the same as an empty list -- not
    passed through `reset_connection()`/`KiCadUnavailableError` the way
    a genuine dropped connection is. `SPEC-309`'s own original research
    assumed an empty list here without live-testing the zero-open case;
    this was a real, live-discovered correction, not a hypothetical one.

    Deliberately PCB-only: the identical call for `DOCTYPE_SCHEMATIC`
    raises the same real `no handler available` `ApiError` unconditionally
    (there's no schematic-document capability to fall back to) -- confirmed
    the same way, not assumed. `list_project_schematics` below derives a
    schematic path from this same real IPC data instead of needing that
    capability at all."""
    client = get_client()
    try:
        docs = list(client.get_open_documents(DocumentType.DOCTYPE_PCB))
    except (KiCadConnectionError, ApiError) as e:
        if isinstance(e, ApiError) and _NO_HANDLER_MARKER in str(e):
            return []
        reset_connection()
        raise KiCadUnavailableError(
            "Lost connection to KiCad mid-request. It may have been closed."
        ) from e

    return [os.path.join(doc.project.path, doc.board_filename) for doc in docs]


def list_project_schematics() -> list:
    """Real user feedback: why can't Schematic checking work like Board
    checking, with a live list instead of a blind file dialog? Answer,
    confirmed live against a real running KiCad instance with a real
    project open (not assumed): `get_open_documents(DOCTYPE_SCHEMATIC)`
    raises the same `"no handler available"` `ApiError` unconditionally,
    even with a board open and its project loaded -- unlike the PCB
    case, KiCad's IPC server has never implemented a schematic-listing
    handler at all. `run_action` could in principle drive KiCad's UI
    remotely, but kipy's own docstring marks it explicitly unstable and
    "not intended for use other than by API developers" -- not something
    to build real functionality on.

    Instead, this derives each currently open board's own root schematic
    path from `get_open_documents(DOCTYPE_PCB)`'s own real `project.name`/
    `project.path` fields: KiCad's own project convention names the root
    schematic after the *project*, not the individual board file -- true
    even for a multi-board project whose `.kicad_pcb` files don't share
    the project's own name. Verified against a real project on this
    machine (`NFC_Reader_ESP32.kicad_pcb` open, project name
    `NFC_Reader_ESP32`, real `NFC_Reader_ESP32.kicad_sch` present at the
    project root). Never returns a derived path that doesn't actually
    exist -- a wrong guess presented as fact would be worse than the
    manual file-picker this replaces for the common case."""
    client = get_client()
    try:
        docs = list(client.get_open_documents(DocumentType.DOCTYPE_PCB))
    except (KiCadConnectionError, ApiError) as e:
        if isinstance(e, ApiError) and _NO_HANDLER_MARKER in str(e):
            return []
        reset_connection()
        raise KiCadUnavailableError(
            "Lost connection to KiCad mid-request. It may have been closed."
        ) from e

    seen = set()
    candidates = []
    for doc in docs:
        sch_path = os.path.join(doc.project.path, doc.project.name + ".kicad_sch")
        if sch_path in seen:
            continue
        seen.add(sch_path)
        if os.path.exists(sch_path):
            candidates.append(sch_path)
    return candidates


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


def list_footprint_models() -> list:
    """SPEC-311: every real footprint's own attached 3D model(s) --
    kipy's real `Footprint.models` (`Footprint3DModel`, a real property
    since kipy 0.3.0, confirmed against this environment's installed
    kipy). Read-only, no `freecad_bridge` dependency -- this module
    stays independently importable per SPEC-107 §2 even when
    `freecad_bridge`'s own dependencies (e.g. `trimesh`) aren't
    installed; `daemon.py`'s own composition route is what turns a
    resolved STEP path into a real height, mirroring how
    `freecad_generate_enclosure` already composes this module's board
    outline/mounting-hole data with `freecad_bridge.generate_enclosure`.

    Real per-footprint list: [{"reference", "is_mounting_hole", "models":
    [{"filename", "resolved_path" (real path on disk, or None),
    "visible"}, ...]}, ...]. Every attached model is reported, not only
    ones this function judges usable -- the caller decides format/
    visibility handling.

    `is_mounting_hole` reuses `get_mounting_holes`'s own real recognition
    convention (KiCad's standard MountingHole library, or an `H<digits>`
    reference) -- CTX-311.15's own real click-through found the daemon's
    height-derivation route flagging a board's real, unannotated
    MountingHole footprints as "missing a 3D model," which is technically
    true but misleading: a screw hole was never expected to have a
    rendered model, and it's already represented separately by the
    enclosure's own standoff geometry, not this footprint list."""
    client = get_client()
    try:
        board = client.get_board()
        footprints = board.get_footprints()
    except (KiCadConnectionError, ApiError) as e:
        reset_connection()
        raise KiCadUnavailableError(
            "Lost connection to KiCad mid-request. It may have been closed."
        ) from e

    result = []
    for fp in footprints:
        reference = fp.reference_field.text.value if fp.reference_field else "?"
        library = (fp.definition.id.library or "").lower()
        is_mounting_hole = (
            "mountinghole" in library or bool(_MOUNTING_HOLE_REF_PATTERN.match(reference))
        )
        models = [
            {
                "filename": m.filename,
                "resolved_path": _resolve_3d_model_path(m.filename),
                "visible": bool(m.visible),
            }
            for m in (fp.definition.models or [])
        ]
        result.append({
            "reference": reference,
            "is_mounting_hole": is_mounting_hole,
            "models": models,
        })

    return result


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

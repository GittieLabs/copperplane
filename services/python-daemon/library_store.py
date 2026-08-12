"""
File-based storage (SPEC-304) for the six persisted objects SPEC-300 §2.1
defines: Project, Part, Symbol, Footprint, Artifact, Conversation. Files
are truth -- this module never opens a database; the `.index/` SQLite
cache PRODUCT-PLAN.md §4 describes is deliberately out of scope for this
first pass (CTX-304.1 Plan Drift explains why).

Layout, exactly matching PRODUCT-PLAN.md §4:

    <storage_root>/
      library/
        parts/<part_id>.part.json
        symbols/<symbol_id>.json
        footprints/<footprint_id>.json
        datasheets/<part_id>.pdf          (cache_datasheet, SPEC-306)
      projects/
        <project_name>/
          project.json
          conversation.jsonl
          artifacts/<artifact_id>.json

Deliberately decoupled from daemon.py's CONFIG global, matching
kicad_bridge/freecad_bridge's own pattern (SPEC-107 §2's rationale) --
`configure()` is called explicitly from `_apply_env_config()`, this
module never reaches into a daemon-owned global itself.
"""
import json
import os
import ssl
import urllib.error
import urllib.request

import certifi


class SchemaValidationError(Exception):
    """Raised when a record fails a required-field or provenance check --
    SPEC-300 §2.2's "must reject," never merely document, requirement.
    A record that fails this is never written to disk."""


class DatasheetFetchError(Exception):
    """Raised when a datasheet can't be fetched or cached -- SPEC-306 §3:
    fails closed with a specific reason, matching kicad_bridge/
    freecad_bridge's own convention, never a silently-skipped cache."""


class StorageRootUnconfiguredError(Exception):
    """Raised if a caller tries to read/write before `configure()` has
    run. In production Rust always injects a real storage_root at every
    spawn (CTX-304.1 Phase 1) -- this should only ever fire in a test
    that forgot to call `configure()` first."""


_storage_root_override = None


def configure(storage_root: str = None) -> None:
    """Sets the resolved storage root this module reads/writes under --
    called once from `_apply_env_config()` at daemon startup, and
    directly by tests that want a real, isolated temp directory."""
    global _storage_root_override
    _storage_root_override = storage_root


def _root() -> str:
    if not _storage_root_override:
        raise StorageRootUnconfiguredError(
            "library_store.configure() was never called with a real storage_root."
        )
    return _storage_root_override


def _ensure_dir(*parts: str) -> str:
    path = os.path.join(_root(), *parts)
    os.makedirs(path, exist_ok=True)
    return path


def _write_json(path: str, record: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, sort_keys=True)


def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --- Part -------------------------------------------------------------
# Every field a Part carries that came from an inference (not a plain
# identifier) must record where it came from -- SPEC-300 §2.2's required-
# provenance promise, enforced here as a schema check, not a convention.
PART_PROVENANCE_REQUIRED_FIELDS = ("manufacturer", "package", "pins", "datasheet_url")


def _parts_dir() -> str:
    return _ensure_dir("library", "parts")


def _validate_part_provenance(part: dict) -> None:
    provenance = part.get("provenance")
    if not isinstance(provenance, dict):
        raise SchemaValidationError(
            "Part.provenance is required and must be a dict keyed by field name."
        )
    missing = [f for f in PART_PROVENANCE_REQUIRED_FIELDS if f not in provenance]
    if missing:
        raise SchemaValidationError(
            f"Part is missing provenance for required field(s): {', '.join(missing)}. "
            "SPEC-300 §2.2: every inferred field must record its source, not just carry a value."
        )


def save_part(part: dict) -> dict:
    """Writes a Part record to library/parts/<part_id>.part.json.
    `footprint_id` may be `None` -- a Part with pins and a datasheet is
    useful before any Footprint exists (SPEC-300 §2.1). Raises
    SchemaValidationError, never writes a partially-provenanced record."""
    part_id = part.get("part_id")
    if not part_id:
        raise SchemaValidationError("Part.part_id is required.")
    _validate_part_provenance(part)

    record = {**part, "schema_version": 1}
    _write_json(os.path.join(_parts_dir(), f"{part_id}.part.json"), record)
    return record


def load_part(part_id: str) -> dict:
    return _read_json(os.path.join(_parts_dir(), f"{part_id}.part.json"))


def list_parts() -> list:
    suffix = ".part.json"
    return sorted(f[: -len(suffix)] for f in os.listdir(_parts_dir()) if f.endswith(suffix))


# --- Symbol -------------------------------------------------------------
def _symbols_dir() -> str:
    return _ensure_dir("library", "symbols")


def save_symbol(symbol: dict) -> dict:
    symbol_id = symbol.get("symbol_id")
    if not symbol_id:
        raise SchemaValidationError("Symbol.symbol_id is required.")
    record = {**symbol, "schema_version": 1}
    _write_json(os.path.join(_symbols_dir(), f"{symbol_id}.json"), record)
    return record


def load_symbol(symbol_id: str) -> dict:
    return _read_json(os.path.join(_symbols_dir(), f"{symbol_id}.json"))


# --- Symbol -> real .kicad_sym export (SPEC-307) --------------------------
# The exact real format, confirmed by reading actual KiCad 10 library files
# on this machine (both user-authored and KiCad's own bundled system
# libraries) -- not guessed from documentation. Pin electrical-type
# keywords and the left-angle-0/right-angle-180 convention were confirmed
# the same way, via `grep` across real .kicad_sym files, not assumed.
_KICAD_SYM_VERSION = 20251024
_KICAD_PIN_LENGTH_MM = 2.54
_KICAD_PIN_PITCH_MM = 2.54
_KICAD_SYM_HALF_WIDTH_MM = 5.08

# SPEC-202's electrical_type enum -> KiCad's own real pin-type vocabulary
# (confirmed present across KiCad's bundled symbol libraries). "power" and
# "ground" both map to power_in -- real KiCad libraries mark GND pins as
# power_in too, not a separate "ground" keyword; there isn't one.
_KICAD_PIN_TYPE = {
    "input": "input",
    "output": "output",
    "bidirectional": "bidirectional",
    "power": "power_in",
    "ground": "power_in",
    "passive": "passive",
    "no_connect": "no_connect",
}


def _layout_pins(pins: list) -> dict:
    """A pure, testable auto-layout: pins split evenly left/right, stacked
    on KiCad's own real 2.54mm grid. Not an attempt at a real pinout
    diagram (no visual symbol editor exists) -- just a real, valid
    geometry every pin can hang off of. Returns each pin's real (x, y,
    angle) plus the body rectangle's half-width/half-height."""
    left_count = (len(pins) + 1) // 2
    right_count = len(pins) - left_count

    def _side_positions(count: int) -> list:
        top = (count - 1) / 2 * _KICAD_PIN_PITCH_MM
        return [top - i * _KICAD_PIN_PITCH_MM for i in range(count)]

    left_ys = _side_positions(left_count)
    right_ys = _side_positions(right_count)

    placed = []
    for pin, y in zip(pins[:left_count], left_ys):
        x = -(_KICAD_SYM_HALF_WIDTH_MM + _KICAD_PIN_LENGTH_MM)
        placed.append({**pin, "x": x, "y": y, "angle": 0})
    for pin, y in zip(pins[left_count:], right_ys):
        x = _KICAD_SYM_HALF_WIDTH_MM + _KICAD_PIN_LENGTH_MM
        placed.append({**pin, "x": x, "y": y, "angle": 180})

    max_count = max(left_count, right_count, 1)
    half_height = (max_count - 1) / 2 * _KICAD_PIN_PITCH_MM + _KICAD_PIN_PITCH_MM

    return {"pins": placed, "half_width": _KICAD_SYM_HALF_WIDTH_MM, "half_height": half_height}


def _sexpr_str(value: str) -> str:
    """Escapes a string for a KiCad S-expression quoted token."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _sexpr_num(value: float) -> str:
    """Formats a coordinate for a KiCad S-expression -- rounded to avoid
    float noise like 7.619999999999999 from plain mm arithmetic, and
    without a trailing '.0' for whole numbers, matching real .kicad_sym
    files' own formatting."""
    rounded = round(value, 4)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


def _build_kicad_sym_text(symbol: dict) -> str:
    """Hand-builds a real, valid .kicad_sym file for one symbol -- the
    same "write the real format directly" approach kicad_write.py already
    established for .kicad_mod-shaped geometry (CTX-108.1), applied here
    to a standalone library file instead of a live board transaction."""
    symbol_id = symbol["symbol_id"]
    reference_prefix = symbol.get("reference_prefix", "U")
    layout = _layout_pins(symbol.get("pins", []))
    half_width = layout["half_width"]
    half_height = layout["half_height"]

    pin_lines = []
    for pin in layout["pins"]:
        kicad_type = _KICAD_PIN_TYPE.get(pin.get("electrical_type"), "unspecified")
        pin_lines.append(
            f'\t\t\t(pin {kicad_type} line\n'
            f'\t\t\t\t(at {_sexpr_num(pin["x"])} {_sexpr_num(pin["y"])} {pin["angle"]})\n'
            f'\t\t\t\t(length {_sexpr_num(_KICAD_PIN_LENGTH_MM)})\n'
            f'\t\t\t\t(name "{_sexpr_str(pin.get("name", ""))}" (effects (font (size 1.27 1.27))))\n'
            f'\t\t\t\t(number "{_sexpr_str(pin.get("number", ""))}" (effects (font (size 1.27 1.27))))\n'
            f'\t\t\t)'
        )
    pins_block = "\n".join(pin_lines)

    return (
        f'(kicad_symbol_lib\n'
        f'\t(version {_KICAD_SYM_VERSION})\n'
        f'\t(generator "hardware-agent-studio")\n'
        f'\t(generator_version "0.1")\n'
        f'\t(symbol "{_sexpr_str(symbol_id)}"\n'
        f'\t\t(exclude_from_sim no)\n'
        f'\t\t(in_bom yes)\n'
        f'\t\t(on_board yes)\n'
        f'\t\t(property "Reference" "{_sexpr_str(reference_prefix)}"\n'
        f'\t\t\t(at 0 {_sexpr_num(half_height + 1.27)} 0)\n'
        f'\t\t\t(effects (font (size 1.27 1.27)))\n'
        f'\t\t)\n'
        f'\t\t(property "Value" "{_sexpr_str(symbol_id)}"\n'
        f'\t\t\t(at 0 {_sexpr_num(-(half_height + 1.27))} 0)\n'
        f'\t\t\t(effects (font (size 1.27 1.27)))\n'
        f'\t\t)\n'
        f'\t\t(symbol "{_sexpr_str(symbol_id)}_0_1"\n'
        f'\t\t\t(rectangle\n'
        f'\t\t\t\t(start {_sexpr_num(-half_width)} {_sexpr_num(half_height)})\n'
        f'\t\t\t\t(end {_sexpr_num(half_width)} {_sexpr_num(-half_height)})\n'
        f'\t\t\t\t(stroke (width 0) (type default))\n'
        f'\t\t\t\t(fill (type none))\n'
        f'\t\t\t)\n'
        f'\t\t)\n'
        f'\t\t(symbol "{_sexpr_str(symbol_id)}_1_1"\n'
        f'{pins_block}\n'
        f'\t\t)\n'
        f'\t)\n'
        f')\n'
    )


def export_symbol_kicad_sym(symbol_id: str) -> str:
    """Writes a real .kicad_sym file for an already-saved Symbol to
    library/symbols/<symbol_id>.kicad_sym, returning that path. Real
    verification (this module's own test suite) is KiCad's own
    `kicad-cli sym export svg` successfully parsing and rendering the
    result -- not just plausible-looking text."""
    symbol = load_symbol(symbol_id)
    text = _build_kicad_sym_text(symbol)
    path = os.path.join(_symbols_dir(), f"{symbol_id}.kicad_sym")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# --- Footprint ------------------------------------------------------------
def _footprints_dir() -> str:
    return _ensure_dir("library", "footprints")


def save_footprint(footprint: dict) -> dict:
    """A Footprint is deliberately its own object, shared by many Parts --
    SPEC-300 §2.1's explicit cardinality call. This module doesn't enforce
    the many-to-one sharing itself; a Part just stores a footprint_id."""
    footprint_id = footprint.get("footprint_id")
    if not footprint_id:
        raise SchemaValidationError("Footprint.footprint_id is required.")
    record = {**footprint, "schema_version": 1}
    _write_json(os.path.join(_footprints_dir(), f"{footprint_id}.json"), record)
    return record


def load_footprint(footprint_id: str) -> dict:
    return _read_json(os.path.join(_footprints_dir(), f"{footprint_id}.json"))


# --- Project --------------------------------------------------------------
def _project_dir(name: str) -> str:
    return _ensure_dir("projects", name)


def save_project(project: dict) -> dict:
    name = project.get("name")
    if not name:
        raise SchemaValidationError("Project.name is required.")
    record = {**project, "schema_version": 1}
    _write_json(os.path.join(_project_dir(name), "project.json"), record)
    return record


def load_project(name: str) -> dict:
    return _read_json(os.path.join(_project_dir(name), "project.json"))


def list_projects() -> list:
    projects_root = _ensure_dir("projects")
    return sorted(
        entry for entry in os.listdir(projects_root)
        if os.path.isfile(os.path.join(projects_root, entry, "project.json"))
    )


# --- Artifact ---------------------------------------------------------
# The one real gap the SPEC-304 ID-collision resolution carried forward
# (ROADMAP.md §3.3): enclosure revisions must be trackable alongside the
# board revision they were generated against. Enforced here, not just
# documented -- an enclosure Artifact without one is rejected.
def _artifacts_dir(project_name: str) -> str:
    return _ensure_dir("projects", project_name, "artifacts")


def save_artifact(project_name: str, artifact: dict) -> dict:
    artifact_id = artifact.get("artifact_id")
    if not artifact_id:
        raise SchemaValidationError("Artifact.artifact_id is required.")
    if artifact.get("kind") == "enclosure" and not artifact.get("board_revision"):
        raise SchemaValidationError(
            "An enclosure Artifact must record board_revision -- the requirement carried forward "
            "from the SPEC-304 ID-collision resolution (ROADMAP.md §3.3), not present in "
            "PRODUCT-PLAN.md's own storage section."
        )
    record = {**artifact, "schema_version": 1}
    _write_json(os.path.join(_artifacts_dir(project_name), f"{artifact_id}.json"), record)
    return record


def load_artifact(project_name: str, artifact_id: str) -> dict:
    return _read_json(os.path.join(_artifacts_dir(project_name), f"{artifact_id}.json"))


def list_artifacts(project_name: str) -> list:
    suffix = ".json"
    directory = _artifacts_dir(project_name)
    return sorted(f[: -len(suffix)] for f in os.listdir(directory) if f.endswith(suffix))


# --- Datasheet cache ------------------------------------------------------
# SPEC-306 §2: the one piece of PRODUCT-PLAN.md §4's own layout this
# module previously named as "not managed by this module yet" -- the
# first real consumer (Component Discovery's disambiguation card) needs
# a real fetch, not a URL string carried around unchecked.
_DATASHEET_FETCH_TIMEOUT_S = 15

# Real end-to-end verification found this: `services/python-daemon`'s
# python3 build's own baked-in default OpenSSL cert path points at a
# path from *that build's own CI runner* (a GitHub Actions
# /Users/runner/... path), which doesn't exist on a real machine --
# urlopen's default SSL context fails closed with
# CERTIFICATE_VERIFY_FAILED on every real HTTPS host. certifi (already
# an installed transitive dependency via gittielabs-agentflow's httpx/
# google-genai deps) ships a real, working CA bundle -- used explicitly
# here rather than trusting this interpreter's own broken default.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _datasheets_dir() -> str:
    return _ensure_dir("library", "datasheets")


def cache_datasheet(part_number: str, datasheet_url: str) -> str:
    """Fetches `datasheet_url` and writes it to
    library/datasheets/<part_number>.pdf, returning that real local path.
    Never writes a partial file -- the full response is read into memory
    before anything touches disk, so a fetch that fails partway through
    raises DatasheetFetchError with nothing written. Does not touch
    save_part/_validate_part_provenance: a cached datasheet is a new,
    additional fact about a part number, not a replacement for the
    datasheet_url provenance entry that check already enforces."""
    if not part_number or "/" in part_number or "\\" in part_number or ".." in part_number:
        raise DatasheetFetchError(f"'{part_number}' is not a safe part_number for a cache filename.")

    request = urllib.request.Request(
        datasheet_url, headers={"User-Agent": "hardware-agent-studio/0.1"}
    )
    try:
        with urllib.request.urlopen(
            request, timeout=_DATASHEET_FETCH_TIMEOUT_S, context=_SSL_CONTEXT
        ) as response:
            if response.status != 200:
                raise DatasheetFetchError(
                    f"Datasheet fetch for '{part_number}' returned HTTP {response.status}."
                )
            content = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # A real, slow/stalling host proved this necessary: `urlopen`
        # only wraps a connection-phase failure in URLError. A timeout
        # during `response.read()` itself (the connection opened fine,
        # the body never finished arriving) raises a bare TimeoutError/
        # OSError instead, which URLError alone does not catch.
        raise DatasheetFetchError(f"Datasheet fetch for '{part_number}' failed: {e}") from e

    path = os.path.join(_datasheets_dir(), f"{part_number}.pdf")
    with open(path, "wb") as f:
        f.write(content)
    return path


# --- Conversation -------------------------------------------------------
# Append-only, per SPEC-300 §2.1 -- a plain JSONL file, not one JSON
# record rewritten on every turn.
def _conversation_path(project_name: str) -> str:
    return os.path.join(_project_dir(project_name), "conversation.jsonl")


def append_conversation_turn(project_name: str, turn: dict) -> None:
    with open(_conversation_path(project_name), "a", encoding="utf-8") as f:
        f.write(json.dumps(turn, sort_keys=True) + "\n")


def load_conversation(project_name: str) -> list:
    path = _conversation_path(project_name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

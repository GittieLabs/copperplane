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
from datetime import datetime, timezone

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


class ProjectDirectoryMissingError(Exception):
    """CTX-312.1: raised when a `directory`-linked project's own real
    manifest can't be found at `<directory>/.hardware-agent-studio/
    project.json` -- the folder was moved, renamed, or deleted outside
    the app since it was linked. A real, specific, user-facing error
    (matching kicad_bridge/freecad_bridge's own clean-error convention),
    never a bare `FileNotFoundError` a caller has to guess the meaning
    of."""


class ProjectNotLinkedError(Exception):
    """CTX-312.3: raised by `open_project_from_directory` when the given
    folder has no real `.hardware-agent-studio/project.json` at all --
    distinct from `ProjectDirectoryMissingError` above, which is about a
    project *this app already knows about* losing its linked folder.
    Deliberately does not fall back to silently creating a new project
    from the folder's own basename -- that would risk a real, un-obvious
    name collision against an existing `storage_root/projects/<name>/`,
    and creating new projects already has its own real entry point (the
    Rail's own "+ New…")."""


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


def current_storage_root() -> str:
    """The real, currently-active storage root, or None if never
    configured -- unlike _root(), never raises. SPEC-110: lets
    daemon.get_capabilities report the real resolved path (the same
    Rust-computed value spawn_daemon injected, whether from the app's
    default data directory or a user's real storage_root_override) so
    Settings can display it without config.json ever needing to hold it."""
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
# package_dimensions/courtyard (CTX-308.5) are exactly as LLM-inferred as
# package/pins -- required for the same reason, not a lesser field.
PART_PROVENANCE_REQUIRED_FIELDS = (
    "manufacturer", "package", "pins", "datasheet_url", "package_dimensions", "courtyard",
)


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


def list_footprints() -> list:
    """Mirrors list_parts()'s own real pattern -- .json files in the
    footprints dir, extension stripped, sorted."""
    suffix = ".json"
    return sorted(f[: -len(suffix)] for f in os.listdir(_footprints_dir()) if f.endswith(suffix))


def search_footprints(query: str) -> list:
    """SPEC-308/CTX-308.4: the second of PRODUCT-PLAN.md SS8 item 3's
    three ranked footprint sources -- footprints this app has already
    saved, not KiCad's own libraries (fp_lib_table.py's job). Falls back
    to matching on footprint_id when footprint_name is missing -- a real,
    already-possible shape (this module's own tests save footprints with
    no footprint_name at all, e.g. {"footprint_id": "SOIC-8", "pads":
    [...]}), not a hypothetical edge case."""
    query_lower = query.lower()
    results = []
    for footprint_id in list_footprints():
        record = load_footprint(footprint_id)
        name = record.get("footprint_name") or footprint_id
        if query_lower in name.lower():
            results.append(record)
    return results


# --- Footprint -> real .pretty library export (SPEC-308, CTX-308.6) -------
# Real format, confirmed by reading actual .kicad_mod files on this machine
# -- both a plain SMD 2-terminal part (Resistor_SMD.pretty/
# R_0603_1608Metric.kicad_mod) and a real thru_hole pad (Package_DIP.pretty)
# -- not guessed from documentation, the same verification approach
# _build_kicad_sym_text already established for symbols.
_KICAD_MOD_VERSION = 20260206
_KICAD_MOD_GENERATOR = "hardware-agent-studio"

# A footprint library is a directory whose name ends in .pretty -- KiCad's
# own real convention (unlike a symbol library, which is a single
# .kicad_sym file with no wrapper directory) -- confirmed against every
# real footprint library on this machine, all of them "<Name>.pretty/".
# This directory can be pointed at directly from a real fp-lib-table entry.
_FOOTPRINTS_PRETTY_DIR_NAME = "footprints.pretty"


def _footprints_pretty_dir() -> str:
    return _ensure_dir("library", _FOOTPRINTS_PRETTY_DIR_NAME)


def _build_kicad_mod_text(footprint: dict) -> str:
    """Hand-builds a real, valid standalone .kicad_mod file from a
    Footprint's own pads/courtyard -- the same shape
    kicad_write.generate_pad_layout already produces and
    kicad_write.build_footprint_instance already consumes for a live
    board write, applied here to a standalone library file instead.
    Pad shape choices deliberately mirror build_footprint_instance's own
    (rect for SMD copper, circle for a PTH's copper layer/drill) so a
    footprint looks the same whether it reaches KiCad via a live inject
    or via this exported file."""
    footprint_id = footprint["footprint_id"]
    pad_lines = []
    for pad in footprint["pads"]:
        is_pth = pad["pad_type"] == "pth"
        pad_type = "thru_hole" if is_pth else "smd"
        shape = "circle" if is_pth else "rect"
        layers = '"*.Cu" "*.Mask"' if is_pth else '"F.Cu" "F.Mask" "F.Paste"'
        drill_line = f'\n\t\t(drill {_sexpr_num(pad["drill_mm"])})' if is_pth else ""
        pad_lines.append(
            f'\t(pad "{_sexpr_str(pad["number"])}" {pad_type} {shape}\n'
            f'\t\t(at {_sexpr_num(pad["x_mm"])} {_sexpr_num(pad["y_mm"])})\n'
            f'\t\t(size {_sexpr_num(pad["width_mm"])} {_sexpr_num(pad["height_mm"])}){drill_line}\n'
            f'\t\t(layers {layers})\n'
            f'\t)'
        )
    pads_block = "\n".join(pad_lines)

    courtyard = footprint["courtyard"]
    half_length = courtyard["length_mm"] / 2
    half_width = courtyard["width_mm"] / 2

    return (
        f'(footprint "{_sexpr_str(footprint_id)}"\n'
        f'\t(version {_KICAD_MOD_VERSION})\n'
        f'\t(generator "{_KICAD_MOD_GENERATOR}")\n'
        f'\t(layer "F.Cu")\n'
        f'\t(attr smd)\n'
        f'\t(fp_rect\n'
        f'\t\t(start {_sexpr_num(-half_length)} {_sexpr_num(-half_width)})\n'
        f'\t\t(end {_sexpr_num(half_length)} {_sexpr_num(half_width)})\n'
        f'\t\t(stroke (width 0.05) (type solid))\n'
        f'\t\t(fill no)\n'
        f'\t\t(layer "F.CrtYd")\n'
        f'\t)\n'
        f'{pads_block}\n'
        f')\n'
    )


def export_footprint_kicad_mod(footprint_id: str) -> str:
    """Writes a real .kicad_mod file for an already-saved Footprint to
    library/footprints.pretty/<footprint_id>.kicad_mod, returning that
    path -- SPEC-308 §1's own stated goal ("export it to a real .pretty
    library"). Only meaningful for a footprint that actually has pad
    geometry: a footprint found via kicad.search_footprints (installed
    KiCad library or the user's own saved library, CTX-308.1/.4) is
    already a real .kicad_mod sitting exactly where it needs to be --
    only a CTX-308.5-generated footprint has pads/courtyard to export at
    all. Raises SchemaValidationError with a clear, specific reason for
    a footprint with no geometry, rather than writing a meaningless
    pad-less file.

    Real verification (this module's own test suite) is KiCad's own
    `kicad-cli fp export svg` successfully parsing and rendering the
    result -- not just plausible-looking text, the same standard
    export_symbol_kicad_sym already holds itself to."""
    footprint = load_footprint(footprint_id)
    if not footprint.get("pads") or not footprint.get("courtyard"):
        raise SchemaValidationError(
            f"Footprint '{footprint_id}' has no pad geometry to export -- only a footprint "
            f"generated from datasheet dimensions (kicad.generate_footprint_from_part) has real "
            f"pads/courtyard. A footprint found in an installed KiCad library or your own saved "
            f"library is already a real .kicad_mod file; there is nothing new to export."
        )

    text = _build_kicad_mod_text(footprint)
    path = os.path.join(_footprints_pretty_dir(), f"{footprint_id}.kicad_mod")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# --- Project --------------------------------------------------------------
# CTX-312.1: the real, on-disk subdirectory a `directory`-linked project's
# own state lives in -- named to match this app's own already-established
# real identifier (`core/tauri-rust/src/secrets.rs`'s keychain service
# name, `hardware-agent-studio`), not a new brand invented here.
_PROJECT_STATE_SUBDIR = ".hardware-agent-studio"


def _project_dir(name: str) -> str:
    return _ensure_dir("projects", name)


def _project_pointer_path(name: str) -> str:
    """CTX-312.1: the storage-root pointer record every project has,
    linked or not -- `list_projects()`'s own directory scan, and
    `load_project`'s own first read (to discover a linked project's real
    `directory` before it can go read the real manifest there), both
    depend on this always existing regardless of link state."""
    return os.path.join(_project_dir(name), "project.json")


def project_directory(name: str) -> str:
    """CTX-311.13: the one real, public source of truth for a project's
    own real directory path on disk -- used to default the Enclosure
    Export dialog's save location to the project's own folder, so a
    caller outside this module never has to hand-build the same
    `<storage_root>/projects/<name>/` convention `_project_dir` already
    owns.

    CTX-312.1: once a project is real-linked to a directory on disk,
    that's the more correct real default for a save dialog than this
    app's own internal storage location -- returns the linked directory
    when set, the original storage-root path otherwise (an unlinked
    project has nowhere else real to point at)."""
    pointer = _read_json(_project_pointer_path(name)) if os.path.isfile(
        _project_pointer_path(name)
    ) else {}
    return pointer.get("directory") or _project_dir(name)


def _project_state_path(directory: str) -> str:
    """Pure path computation, no filesystem side effects -- `load_project`
    (below) calls this to check whether a linked project's own real
    manifest exists at all. `save_project`'s own write path is
    responsible for creating the directory when it actually writes."""
    return os.path.join(directory, _PROJECT_STATE_SUBDIR, "project.json")


def save_project(project: dict) -> dict:
    """CTX-312.1: real, project-directory-aware routing. A storage-root
    pointer record (`{name, directory, schema_version}`, never the full
    manifest) always gets written -- `list_projects()`'s own directory
    scan and `load_project`'s own first read both depend on it existing
    regardless of link state. When `directory` is real and set, the full
    manifest (every field the caller supplied) is written there instead,
    portable with the project's own real folder; an unlinked project's
    pointer record *is* the full manifest, matching this function's own
    pre-CTX-312.1 behavior exactly."""
    name = project.get("name")
    if not name:
        raise SchemaValidationError("Project.name is required.")
    directory = project.get("directory")
    record = {**project, "schema_version": 1}

    if directory:
        _write_json(
            _project_pointer_path(name),
            {"name": name, "directory": directory, "schema_version": 1},
        )
        state_path = _project_state_path(directory)
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        _write_json(state_path, record)
    else:
        _write_json(_project_pointer_path(name), record)

    return record


def load_project(name: str) -> dict:
    """CTX-110.1 found this gap: identity is the `projects/<name>/` folder
    name, per list_projects() below -- project.json's own `name` field is
    just what was true at save time, and goes stale if a user renames the
    folder on disk (outside the app). Overriding it here with the real
    folder name this record was loaded from means every caller sees
    disk-truth identity, never a stale one, without needing its own
    reconciliation logic.

    CTX-312.1: the storage-root pointer is read first to discover a real
    `directory` link; when one exists, the real, full manifest is read
    from there instead -- a moved, renamed, or deleted linked folder
    raises `ProjectDirectoryMissingError`, a clean, specific error,
    rather than a bare `FileNotFoundError` whose meaning a caller would
    have to guess at.

    CTX-312.3 found a real gap in the disk-truth reasoning above: `name`
    was overridden from the pointer, but `directory` wasn't -- a real
    portable state file (`open_project_from_directory` below) may carry
    a stale `directory` value from whatever machine last saved it, or
    none at all. The pointer's own `directory` (this machine's real,
    current answer) now always wins, the same way its `name` already
    does."""
    pointer = _read_json(_project_pointer_path(name))
    directory = pointer.get("directory")
    if not directory:
        pointer["name"] = name
        return pointer

    state_path = _project_state_path(directory)
    if not os.path.isfile(state_path):
        raise ProjectDirectoryMissingError(
            f"Project '{name}' is linked to '{directory}', but its own project file "
            f"is missing there. The folder may have been moved, renamed, or deleted."
        )
    record = _read_json(state_path)
    record["name"] = name
    record["directory"] = directory
    return record


def list_projects() -> list:
    projects_root = _ensure_dir("projects")
    return sorted(
        entry for entry in os.listdir(projects_root)
        if os.path.isfile(os.path.join(projects_root, entry, "project.json"))
    )


def open_project_from_directory(directory: str) -> dict:
    """CTX-312.3: the real reverse of `save_project`'s own directory-link
    routing -- given a real folder (e.g. one copied from another machine,
    or handed over by a teammate), reads its own real
    `.hardware-agent-studio/project.json`, re-registers this app's own
    storage-root pointer so `list_projects()` discovers it going forward,
    and returns the real, full record. This is the actual payoff of
    `CTX-312.1`'s own portability work -- a project's state travelling
    with its folder only matters if opening that folder on a different
    installation can restore it.

    Raises `ProjectNotLinkedError` if the folder has no real state file
    at all -- deliberately never falls back to creating a new project
    from the folder's own basename (see the exception's own docstring
    for why)."""
    state_path = _project_state_path(directory)
    if not os.path.isfile(state_path):
        raise ProjectNotLinkedError(
            f"'{directory}' isn't linked to a hardware-agent-studio project yet -- "
            f"no project.json found there."
        )
    record = _read_json(state_path)
    name = record.get("name")
    if not name:
        raise ProjectNotLinkedError(
            f"The project file at '{directory}' is missing its own required 'name' field."
        )

    _write_json(
        _project_pointer_path(name),
        {"name": name, "directory": directory, "schema_version": 1},
    )
    return load_project(name)


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

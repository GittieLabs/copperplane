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
import hashlib
import json
import os
import re
import ssl
import urllib.error
import urllib.request
import uuid
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


# CTX-315.1: every real Part/Symbol/Footprint belongs to the always-present
# Default library implicitly -- SPEC-315 §2's own rule that Default
# membership is never shown as something to remove. "default" is force-
# included here rather than trusted from the caller, so a real object can
# never end up missing from it by omission.
DEFAULT_LIBRARY_ID = "default"


def _normalize_library_ids(library_ids: list | None) -> list:
    ids = set(library_ids or [])
    ids.add(DEFAULT_LIBRARY_ID)
    return sorted(ids)


def _resolve_library_ids(record: dict, explicit_library_ids: list | None) -> list:
    """A real, important precedence rule found while wiring this in: every
    existing real caller of save_part (attachFootprintToPart,
    generateFootprintFromPart, saveConfirmedPart's own re-save path) calls
    it with an already-loaded record that may already carry a real,
    user-set `library_ids` -- if this function blindly defaulted to
    Default-only whenever the caller didn't pass `library_ids` explicitly,
    every one of those existing re-save paths would silently wipe a real
    custom tag the moment a user, say, attached a footprint to a Part they
    had already organized into a custom library. Precedence: an explicit
    `library_ids` argument wins; otherwise the record's own already-set
    field is preserved; only a record with neither becomes Default-only."""
    if explicit_library_ids is not None:
        return _normalize_library_ids(explicit_library_ids)
    return _normalize_library_ids(record.get("library_ids"))


def _backfill_library_ids(record: dict) -> dict:
    """A record saved before CTX-315.1 shipped has no `library_ids` key at
    all -- real, honest read-time migration: treat it as Default-only,
    never a crash and never a silently empty library."""
    record.setdefault("library_ids", [DEFAULT_LIBRARY_ID])
    return record


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


_DESIGN_GUIDANCE_ITEM_REQUIRED_FIELDS = ("quote", "page", "category")


def _validate_design_guidance(value: dict) -> None:
    """CTX-205.3: `design_guidance` is optional -- unlike
    `PART_PROVENANCE_REQUIRED_FIELDS`, absence is never an error, so this
    is called from `save_part` only when the field is actually present,
    never added to that required-fields tuple (which would gate every
    real, unrelated Part save with no guidance yet). Real, minimal shape
    check, not a full re-validation of `datasheet_guidance.py`'s own
    already-enforced citation checks -- defense in depth against a
    malformed record reaching disk, matching this codebase's general
    fail-closed-on-malformed-data posture (`_validate_part_provenance`),
    not a duplicate of the pipeline's own real work."""
    if not isinstance(value, dict) or not isinstance(value.get("categories"), dict):
        raise SchemaValidationError(
            "Part.design_guidance must be a dict with a real 'categories' dict."
        )
    for category, items in value["categories"].items():
        if not isinstance(items, list):
            raise SchemaValidationError(
                f"Part.design_guidance.categories['{category}'] must be a list."
            )
        for item in items:
            missing = [f for f in _DESIGN_GUIDANCE_ITEM_REQUIRED_FIELDS if f not in item]
            if missing:
                raise SchemaValidationError(
                    f"Part.design_guidance.categories['{category}'] has an item missing "
                    f"required field(s): {', '.join(missing)}."
                )
    # CTX-205.7: `category_summaries` is optional -- a record saved before
    # this context shipped has none, backfilled by `_backfill_design_guidance`
    # below, not required here. When present, each value is the real
    # plain-language summary text (SPEC-205 §2.1.1) or `None` for a
    # category with no validated items -- never anything else.
    summaries = value.get("category_summaries", {})
    if not isinstance(summaries, dict):
        raise SchemaValidationError("Part.design_guidance.category_summaries must be a dict.")
    for category, summary in summaries.items():
        if summary is not None and not isinstance(summary, str):
            raise SchemaValidationError(
                f"Part.design_guidance.category_summaries['{category}'] must be a string or null."
            )


def _backfill_design_guidance(record: dict) -> dict:
    """A record saved before CTX-205.3 shipped -- or one whose guidance
    has genuinely never been generated -- has no `design_guidance` key
    at all. Backfilled as `None`, never `{}`: SPEC-205 §5's own
    "silence must not be readable as 'no requirements'" principle means
    "never generated" and "generated, every category came back empty"
    must stay two real, distinguishable states, not collapsed into one.

    CTX-205.7: a record whose guidance WAS already generated, but before
    this context shipped `category_summaries`, has a real
    `design_guidance` dict missing that key -- backfilled to `{}` (an
    honest "no summaries exist for this generation" state, distinct from
    a category-keyed `None`, which means "this specific category had no
    valid items to summarize"), never re-triggering generation."""
    record.setdefault("design_guidance", None)
    if record["design_guidance"] is not None:
        record["design_guidance"].setdefault("category_summaries", {})
    return record


_CONNECTION_GUIDANCE_REQUIRED_FIELDS = (
    "generated_at", "pins_hash", "pin_guidance", "general_notes", "provenance",
)


def _validate_connection_guidance_record(value: dict) -> None:
    """CTX-206.1 (SPEC-206 §2.4): a real, minimal shape check on the
    *stored* record, mirroring `_validate_design_guidance`'s own role --
    defense in depth against a malformed record reaching disk, not a
    duplicate of `component_pipeline._validate_connection_guidance`'s
    already-real pin-number check, which runs once at generation time
    and stays there (SPEC-206 §2.4: 'that difference is correct and must
    not be harmonised'). Named `..._record`, not `_validate_connection_guidance`,
    specifically so it never collides in a grep with that other, already
    real, differently-scoped function of nearly the same name."""
    if not isinstance(value, dict):
        raise SchemaValidationError("Part.connection_guidance must be a dict.")
    missing = [f for f in _CONNECTION_GUIDANCE_REQUIRED_FIELDS if f not in value]
    if missing:
        raise SchemaValidationError(
            f"Part.connection_guidance is missing required field(s): {', '.join(missing)}."
        )
    if not isinstance(value["pin_guidance"], list):
        raise SchemaValidationError("Part.connection_guidance.pin_guidance must be a list.")
    for entry in value["pin_guidance"]:
        entry_missing = [f for f in ("pin_number", "guidance") if f not in entry]
        if entry_missing:
            raise SchemaValidationError(
                f"Part.connection_guidance.pin_guidance entry is missing required field(s): "
                f"{', '.join(entry_missing)}."
            )
    if not isinstance(value["general_notes"], str):
        raise SchemaValidationError("Part.connection_guidance.general_notes must be a string.")
    provenance = value["provenance"]
    if not isinstance(provenance, dict) or "provider" not in provenance or "model" not in provenance:
        raise SchemaValidationError(
            "Part.connection_guidance.provenance must be a dict with 'provider' and 'model'."
        )


def _backfill_connection_guidance(record: dict) -> dict:
    """A record saved before CTX-206.1 shipped -- or a real Part whose
    connection guidance has genuinely never been generated -- has no
    `connection_guidance` key at all. Backfilled as `None`, the same
    `setdefault`-only, no-`schema_version`-bump convention
    `_backfill_design_guidance` already established for this exact
    situation (this repo's own read-time-backfill norm, `SPEC-206` §1
    Non-Goals)."""
    record.setdefault("connection_guidance", None)
    return record


def compute_pins_hash(pins: list) -> str:
    """SPEC-206 §2.4: sha256 over the canonical (sorted-key) JSON of a
    Part's real `pins` list -- the same invalidation role `content_hash`
    already plays for `design_guidance` (CTX-205.3), applied here so a
    stored `connection_guidance` can be marked stale if the Part's pins
    are later re-extracted. `sort_keys=True` matches this file's own
    existing canonical-JSON convention (`_write_json`,
    `append_conversation_turn`), not a new one."""
    return hashlib.sha256(json.dumps(pins, sort_keys=True).encode("utf-8")).hexdigest()


def save_part(part: dict, library_ids: list | None = None) -> dict:
    """Writes a Part record to library/parts/<part_id>.part.json.
    `footprint_id` may be `None` -- a Part with pins and a datasheet is
    useful before any Footprint exists (SPEC-300 §2.1). Raises
    SchemaValidationError, never writes a partially-provenanced record.

    CTX-315.1: `library_ids` is a real, independent tag on this one Part
    record (SPEC-315 §2 -- a Part, its Symbol, and its Footprint are
    tagged independently, never bundled), always including Default."""
    part_id = part.get("part_id")
    if not part_id:
        raise SchemaValidationError("Part.part_id is required.")
    _validate_part_provenance(part)
    if part.get("design_guidance") is not None:
        _validate_design_guidance(part["design_guidance"])
    if part.get("connection_guidance") is not None:
        _validate_connection_guidance_record(part["connection_guidance"])

    record = {**part, "schema_version": 1, "library_ids": _resolve_library_ids(part, library_ids)}
    # CTX-205.4: a real inconsistency caught while typing this field on the
    # frontend -- `load_part` already backfills `design_guidance`, but
    # `save_part`'s own returned record didn't, so `library.save_confirmed_part`'s
    # real response (the very first save, before any `load_part` round trip)
    # could omit the key entirely rather than carrying a real `None`. Every
    # caller of `save_part` now gets the same real shape `load_part` does.
    _backfill_design_guidance(record)
    _backfill_connection_guidance(record)
    _write_json(os.path.join(_parts_dir(), f"{part_id}.part.json"), record)
    return record


def load_part(part_id: str) -> dict:
    return _backfill_connection_guidance(_backfill_design_guidance(
        _backfill_library_ids(_read_json(os.path.join(_parts_dir(), f"{part_id}.part.json")))
    ))


def save_part_design_guidance(
    part_id: str, content_hash: str, categories: dict, category_summaries: dict | None = None,
) -> dict:
    """CTX-205.3: persists a real `datasheet_guidance.generate_datasheet_guidance(...)`
    result onto `part_id`'s own real, current record -- loads it fresh
    first (never blind-overwrites with a stale caller-held copy), so a
    concurrent edit to any other field survives. `content_hash` is the
    real sha256 of the exact datasheet PDF bytes guidance was generated
    from (SPEC-205 §3's own "citations drift across revisions" risk).

    `document_revision` (a real, human-readable string like "Rev. C")
    is deliberately left `None` -- honest, unbuilt scope, not a
    fabricated placeholder: no extraction step for it exists yet, and
    inventing one would look like real data when it isn't.

    CTX-205.7: `category_summaries` (SPEC-205 §2.1.1's real
    plain-language layer) defaults to `{}`, matching
    `generate_datasheet_guidance`'s own real return shape when called
    with `categories=[]` -- never `None` itself, since the surrounding
    `design_guidance` dict already carries that "never generated"
    distinction one level up."""
    part = load_part(part_id)
    part["design_guidance"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": content_hash,
        "document_revision": None,
        "categories": categories,
        "category_summaries": category_summaries or {},
    }
    return save_part(part)


def save_part_connection_guidance(
    part_id: str, pin_guidance: list, general_notes: str, provenance: dict,
) -> dict:
    """CTX-206.1 (SPEC-206 §2.4): persists a real, already-validated
    `component_pipeline.generate_connection_guidance(...)` result onto
    `part_id`'s own real, current record -- the prerequisite this
    context exists to close: `kicad.generate_connection_guidance`
    previously returned its result and the daemon discarded it,
    `PartDetail.tsx` held it in `useState` and lost it on unmount, and
    nothing in `SPEC-318` can be verified end-to-end until this is a
    record. Mirrors `save_part_design_guidance`'s exact shape -- loads
    the part fresh first, never blind-overwrites a stale caller-held
    copy, so a concurrent edit to any other field survives.

    `pins_hash` is computed here, from this freshly-loaded part's own
    real `pins`, not accepted as a caller-supplied argument -- the one
    real difference from `content_hash`, which the caller *does* supply
    (it's a hash of external PDF bytes this function has no access to).
    A pin_number in `pin_guidance` referencing a pin outside this exact
    `pins` list is already impossible to reach here: `component_pipeline
    ._validate_connection_guidance` is fail-closed against the same
    `pins` list at generation time (SPEC-206 §2.4 -- 'that difference is
    correct and must not be harmonised'), so this function trusts that
    check already ran rather than repeating it."""
    part = load_part(part_id)
    part["connection_guidance"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pins_hash": compute_pins_hash(part["pins"]),
        "pin_guidance": pin_guidance,
        "general_notes": general_notes,
        "provenance": provenance,
    }
    return save_part(part)


def list_parts(library_id: str | None = None) -> list:
    """CTX-315.1: optional real `library_id` filter, same real O(n)-scan
    shape as list_footprints's own."""
    suffix = ".part.json"
    ids = sorted(f[: -len(suffix)] for f in os.listdir(_parts_dir()) if f.endswith(suffix))
    if library_id is None:
        return ids
    return [i for i in ids if library_id in load_part(i).get("library_ids", [])]


# --- Symbol -------------------------------------------------------------
def _symbols_dir() -> str:
    return _ensure_dir("library", "symbols")


def save_symbol(symbol: dict, library_ids: list | None = None) -> dict:
    symbol_id = symbol.get("symbol_id")
    if not symbol_id:
        raise SchemaValidationError("Symbol.symbol_id is required.")
    record = {**symbol, "schema_version": 1, "library_ids": _resolve_library_ids(symbol, library_ids)}
    _write_json(os.path.join(_symbols_dir(), f"{symbol_id}.json"), record)
    return record


def load_symbol(symbol_id: str) -> dict:
    return _backfill_library_ids(_read_json(os.path.join(_symbols_dir(), f"{symbol_id}.json")))


def list_symbols(library_id: str | None = None) -> list:
    """CTX-315.1: mirrors list_footprints's own real, established pattern
    -- a real, pre-existing gap (Symbol never got a list_* function at
    all) closed here since a library's Datasheets/Pins section needs to
    list Symbols, not just Parts. Optional real `library_id` filter, same
    real O(n)-scan shape as list_footprints's own."""
    suffix = ".json"
    ids = sorted(f[: -len(suffix)] for f in os.listdir(_symbols_dir()) if f.endswith(suffix))
    if library_id is None:
        return ids
    return [i for i in ids if library_id in load_symbol(i).get("library_ids", [])]


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
    result -- not just plausible-looking text.

    CTX-314.2: a symbol imported from a real community library
    (`daemon.library_import_community_footprint`) carries its own real,
    verbatim `raw_kicad_sym` text -- written directly, never re-derived
    through `_build_kicad_sym_text`'s own hand-built-from-JSON path,
    which only ever produced this app's own generated single-symbol
    shape and would lossily discard a real vendor file's actual
    geometry."""
    symbol = load_symbol(symbol_id)
    text = symbol.get("raw_kicad_sym") or _build_kicad_sym_text(symbol)
    path = os.path.join(_symbols_dir(), f"{symbol_id}.kicad_sym")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# --- Footprint ------------------------------------------------------------
def _footprints_dir() -> str:
    return _ensure_dir("library", "footprints")


def save_footprint(footprint: dict, library_ids: list | None = None) -> dict:
    """A Footprint is deliberately its own object, shared by many Parts --
    SPEC-300 §2.1's explicit cardinality call. This module doesn't enforce
    the many-to-one sharing itself; a Part just stores a footprint_id.

    CTX-315.1: real, direct consequence of that sharing -- this
    Footprint's own `library_ids` is tracked independently of whichever
    Part(s) reference it, never inherited from one."""
    footprint_id = footprint.get("footprint_id")
    if not footprint_id:
        raise SchemaValidationError("Footprint.footprint_id is required.")
    record = {
        **footprint, "schema_version": 1,
        "library_ids": _resolve_library_ids(footprint, library_ids),
    }
    _write_json(os.path.join(_footprints_dir(), f"{footprint_id}.json"), record)
    return record


def load_footprint(footprint_id: str) -> dict:
    return _backfill_library_ids(_read_json(os.path.join(_footprints_dir(), f"{footprint_id}.json")))


def list_footprints(library_id: str | None = None) -> list:
    """Mirrors list_parts()'s own real pattern -- .json files in the
    footprints dir, extension stripped, sorted.

    CTX-315.1: an optional real `library_id` filter -- a real, honest
    O(n) scan (loading and checking every real record's own
    `library_ids`), not a SQLite-backed lookup. `SPEC-304`'s own
    `.index/` cache is explicitly out of scope for this slice; acceptable
    at this app's real current scale."""
    suffix = ".json"
    ids = sorted(f[: -len(suffix)] for f in os.listdir(_footprints_dir()) if f.endswith(suffix))
    if library_id is None:
        return ids
    return [i for i in ids if library_id in load_footprint(i).get("library_ids", [])]


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
    # A real bug found by live user testing: this line was hardcoded to
    # `(attr smd)` regardless of the footprint's own real pads, so an
    # exported through-hole (DIP) footprint claimed to be surface-mount
    # -- a real, visible inconsistency in KiCad (every pad genuinely
    # `thru_hole`, the footprint itself tagged `smd`). Real KiCad
    # attribute for a footprint whose pads are entirely through-hole is
    # `through_hole`; anything with at least one real SMD pad keeps
    # `smd`, matching every one of this module's other real
    # already-generated footprints (SOIC/TSSOP), which are 100% SMD.
    all_through_hole = all(pad["pad_type"] == "pth" for pad in footprint["pads"])
    footprint_attr = "through_hole" if all_through_hole else "smd"

    courtyard = footprint["courtyard"]
    half_length = courtyard["length_mm"] / 2
    half_width = courtyard["width_mm"] / 2

    return (
        f'(footprint "{_sexpr_str(footprint_id)}"\n'
        f'\t(version {_KICAD_MOD_VERSION})\n'
        f'\t(generator "{_KICAD_MOD_GENERATOR}")\n'
        f'\t(layer "F.Cu")\n'
        f'\t(attr {footprint_attr})\n'
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
    export_symbol_kicad_sym already holds itself to.

    CTX-314.2: a footprint imported from a real community library
    (`daemon.library_import_community_footprint`) carries its own real,
    verbatim `raw_kicad_mod` text -- written directly, skipping the
    pads/courtyard check below entirely, since a raw-backed record has
    no `pads`/`courtyard` fields of its own and needs none; its real
    geometry already lives in the raw text itself."""
    footprint = load_footprint(footprint_id)
    if footprint.get("raw_kicad_mod"):
        path = os.path.join(_footprints_pretty_dir(), f"{footprint_id}.kicad_mod")
        with open(path, "w", encoding="utf-8") as f:
            f.write(footprint["raw_kicad_mod"])
        return path

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


# --- Library registry (CTX-315.1) ------------------------------------------
# SPEC-315 §2: a real, small registry of user-created custom libraries.
# Default is never a real entry here -- it's implicit (every Part/Symbol/
# Footprint already belongs to it, per `DEFAULT_LIBRARY_ID` above), so a
# missing or empty registry file is a normal, honest starting state, not an
# error.
def _libraries_registry_path() -> str:
    return os.path.join(_ensure_dir("library"), "libraries.json")


def _load_libraries_registry() -> list:
    path = _libraries_registry_path()
    if not os.path.exists(path):
        return []
    return _read_json(path).get("libraries", [])


def _save_libraries_registry(libraries: list) -> None:
    _write_json(_libraries_registry_path(), {"libraries": libraries})


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "library"


def create_library(name: str) -> dict:
    """A real, collision-checked id derived from `name` -- a second
    "ESP32 Boards" gets a real, distinct id, never silently overwrites
    the first. Never collides with the implicit `DEFAULT_LIBRARY_ID`
    either."""
    if not name or not name.strip():
        raise SchemaValidationError("Library name is required.")

    libraries = _load_libraries_registry()
    existing_ids = {lib["id"] for lib in libraries} | {DEFAULT_LIBRARY_ID}
    base_slug = _slugify(name)
    slug = base_slug
    suffix = 2
    while slug in existing_ids:
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    entry = {"id": slug, "name": name.strip()}
    libraries.append(entry)
    _save_libraries_registry(libraries)
    return entry


def list_libraries() -> list:
    """Real Default (implicit, computed over *every* real Part/Symbol/
    Footprint -- not just ones explicitly tagged, since Default
    membership is implicit) plus every real custom registry entry, each
    with its own real, freshly-scanned counts."""
    def counts_for(library_id: str | None) -> dict:
        return {
            "part_count": len(list_parts(library_id)),
            "symbol_count": len(list_symbols(library_id)),
            "footprint_count": len(list_footprints(library_id)),
        }

    result = [{"id": DEFAULT_LIBRARY_ID, "name": "Default", **counts_for(None)}]
    for lib in _load_libraries_registry():
        result.append({**lib, **counts_for(lib["id"])})
    return result


def tag_object(kind: str, object_id: str, library_ids: list) -> dict:
    """The real, chosen replace-not-append semantics for one object's own
    custom-library membership (SPEC-315 §5's own "Add to library..."
    shape -- a user picks the full set, not an incremental add). Raises
    SchemaValidationError for a `library_id` not in the real registry --
    never silently created."""
    known_ids = {DEFAULT_LIBRARY_ID} | {lib["id"] for lib in _load_libraries_registry()}
    unknown = set(library_ids) - known_ids
    if unknown:
        raise SchemaValidationError(
            f"Unknown library id(s): {', '.join(sorted(unknown))}. Real registered libraries: "
            f"{', '.join(sorted(known_ids))}."
        )

    if kind == "part":
        return save_part(load_part(object_id), library_ids=library_ids)
    if kind == "symbol":
        return save_symbol(load_symbol(object_id), library_ids=library_ids)
    if kind == "footprint":
        return save_footprint(load_footprint(object_id), library_ids=library_ids)
    raise SchemaValidationError(f"Unknown kind '{kind}' -- expected 'part', 'symbol', or 'footprint'.")


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


def _validate_project_intent(project: dict) -> None:
    """CTX-206.1 (SPEC-206 §2.1): a real, minimal type check -- `intent`
    is a plain free-text field, no structured shape to validate the way
    `design_guidance`/`connection_guidance` need, but a non-string,
    non-null value reaching disk would still be a malformed record."""
    intent = project.get("intent")
    if intent is not None and not isinstance(intent, str):
        raise SchemaValidationError("Project.intent must be a string or null.")


def _backfill_project_intent(record: dict) -> dict:
    """SPEC-206 §2.1: `None` and `""` must stay distinguishable -- the
    same reason `CTX-205.3` backfilled `design_guidance` as `None`
    rather than `{}`. `None` means never set; `""` means the user
    explicitly cleared it. A project saved before this field existed
    gets `None`, read as "never asked", never a fabricated empty
    string."""
    record.setdefault("intent", None)
    return record


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
    _validate_project_intent(project)
    directory = project.get("directory")
    record = _backfill_project_intent({**project, "schema_version": 1})

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
        return _backfill_project_intent(pointer)

    state_path = _project_state_path(directory)
    if not os.path.isfile(state_path):
        raise ProjectDirectoryMissingError(
            f"Project '{name}' is linked to '{directory}', but its own project file "
            f"is missing there. The folder may have been moved, renamed, or deleted."
        )
    record = _read_json(state_path)
    record["name"] = name
    record["directory"] = directory
    return _backfill_project_intent(record)


def set_project_intent(name: str, intent: str) -> dict:
    """CTX-206.1 (SPEC-206 §2.1): `project.set_intent` -- round-trips
    through `load_project`/`save_project` rather than writing directly,
    so it inherits `save_project`'s own real pointer/manifest routing
    (CTX-312.1) for free instead of re-deriving it. No special handling
    is needed to keep `intent` out of the storage-root pointer record
    for a *linked* project -- `save_project`'s pointer branch already
    hard-codes exactly `{name, directory, schema_version}`, so a linked
    project's intent lands only in the real manifest at
    `<directory>/.hardware-agent-studio/project.json` and travels with
    the folder automatically, same as every other real field."""
    project = load_project(name)
    project["intent"] = intent
    return save_project(project)


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


def datasheet_cache_path(part_number: str) -> str:
    """The real, deterministic local cache path for `part_number`'s
    datasheet PDF -- a pure path computation, no filesystem check, no
    network. `CTX-206.4` (SPEC-206 §2.3) needs this to resolve a
    `datasheet_page` `SourceRef` without re-fetching or re-parsing
    anything."""
    return os.path.join(_datasheets_dir(), f"{part_number}.pdf")


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

    path = datasheet_cache_path(part_number)
    with open(path, "wb") as f:
        f.write(content)
    return path


def ensure_datasheet_cached(part_number: str, datasheet_url: str) -> str:
    """CTX-205.3: returns the real local cached path for `part_number`'s
    datasheet PDF, fetching it first only if it isn't already cached.
    `cache_datasheet` itself always re-fetches unconditionally -- correct
    for its own real caller (Component Discovery's disambiguation card,
    which only ever confirms a candidate once) but a regenerate-guidance
    action would otherwise re-download the same real PDF over the
    network on every single call. Same real path-safety guard as
    `cache_datasheet` -- duplicated, not shared, since raising before
    ever touching the filesystem here (an existence check) is a
    genuinely different real code path from raising mid-fetch there."""
    if not part_number or "/" in part_number or "\\" in part_number or ".." in part_number:
        raise DatasheetFetchError(f"'{part_number}' is not a safe part_number for a cache filename.")
    path = datasheet_cache_path(part_number)
    if os.path.exists(path):
        return path
    return cache_datasheet(part_number, datasheet_url)


def content_hash_of_file(path: str) -> str:
    """A real sha256 of a real file's own bytes -- CTX-205.3's own
    citation-provenance need (SPEC-205 §3: "store... a content hash
    alongside the citation"). No hashing precedent existed anywhere in
    this module before this context; a plain, standard, real
    implementation, not a new convention invented for its own sake."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


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


# --- Chat threads (CTX-206.3, SPEC-206 §2.2) -----------------------------
# Threads, not one conversation per project -- scope + scope_id identify
# a thread. "project" threads are per-area (overview/schematic/pcb/
# enclosure -- "components" is Part-scoped, not project-scoped, per the
# table below); "part" threads are global, because a Part is a global
# SPEC-304 object (SPEC-318 §2.1 carries the reasoning; PRODUCT-PLAN.md
# §2.1's own amendment records the same decision). Supersedes
# `_conversation_path` above, which SPEC-206 §2.2 names as a real,
# already-shipped bug: it hardcodes `<storage_root>/projects/<name>/`
# and therefore never follows `CTX-312.1`'s directory link, so a linked
# project's history doesn't travel with its folder. The legacy
# functions above are untouched -- still real, still used by today's
# Overview chat -- and superseded only once `SPEC-318` replaces that
# chat's own wiring, not by this context.
_PROJECT_CHAT_AREAS = ("overview", "schematic", "pcb", "enclosure")


def _project_thread_path(project_name: str, area: str) -> str:
    if area not in _PROJECT_CHAT_AREAS:
        raise SchemaValidationError(
            f"'{area}' is not a real project-scoped chat area ({', '.join(_PROJECT_CHAT_AREAS)})."
        )
    pointer_path = _project_pointer_path(project_name)
    pointer = _read_json(pointer_path) if os.path.isfile(pointer_path) else {}
    directory = pointer.get("directory")
    if directory:
        return os.path.join(directory, _PROJECT_STATE_SUBDIR, "chats", f"{area}.jsonl")
    return os.path.join(_project_dir(project_name), "chats", f"{area}.jsonl")


def _part_thread_path(part_id: str) -> str:
    return os.path.join(_ensure_dir("library", "chats", "parts"), f"{part_id}.jsonl")


def _thread_path(scope: str, scope_id: str) -> str:
    if scope == "project":
        project_name, _, area = scope_id.partition(":")
        if not area:
            raise SchemaValidationError(
                f"A project-scoped chat scope_id must be '<project_name>:<area>', got '{scope_id}'."
            )
        return _project_thread_path(project_name, area)
    if scope == "part":
        return _part_thread_path(scope_id)
    raise SchemaValidationError(f"'{scope}' is not a real chat scope ('project' or 'part').")


def _read_thread_turns(path: str) -> list:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write_thread_turns(path: str, turns: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for turn in turns:
            f.write(json.dumps(turn, sort_keys=True) + "\n")


def _upconvert_legacy_turn(legacy: dict) -> dict:
    """A pre-CTX-206.3 `ConversationTurn` (`role`, `content`, an optional
    client-stamped `timestamp`) upconverted into the real, richer turn
    shape SPEC-206 §2.2 defines. `timestamp` is preserved as whatever the
    legacy record carried (even `None`) -- never re-stamped with the
    current time, which would fabricate an ordering fact this function
    has no way to know (matching the spec's own explicit instruction).
    `general_practice` is `True` for an upconverted assistant turn -- it
    genuinely was never grounded in a cited record; the old Overview
    chat had no source-citation mechanism at all."""
    role = legacy.get("role")
    return {
        "turn_id": str(uuid.uuid4()),
        "role": role,
        "content": legacy.get("content", ""),
        "timestamp": legacy.get("timestamp"),
        "agent": None,
        "sources": [],
        "sources_dropped": 0,
        "general_practice": role == "assistant",
        "tool_calls": [],
        "provenance": None,
        "promoted_note_id": None,
    }


def _migrate_legacy_conversation(project_name: str, new_path: str) -> list:
    """SPEC-206 §2.2: on first read of a project's `overview` thread, if
    no `chats/overview.jsonl` exists yet but a legacy `conversation.jsonl`
    does, its turns are upconverted and written to the new path. The
    legacy file is left in place, never deleted -- this repo's own
    non-destructive read-time-backfill convention, and cheap insurance
    against a migration bug. A `migrated_from` key lands on the *first*
    new record only, not every record, matching the spec's own exact
    wording."""
    legacy_path = _conversation_path(project_name)
    if not os.path.isfile(legacy_path):
        return []
    upconverted = [_upconvert_legacy_turn(t) for t in load_conversation(project_name)]
    if upconverted:
        upconverted[0]["migrated_from"] = legacy_path
    _write_thread_turns(new_path, upconverted)
    return upconverted


def load_thread(scope: str, scope_id: str) -> list:
    path = _thread_path(scope, scope_id)
    if scope == "project":
        project_name, _, area = scope_id.partition(":")
        if area == "overview" and not os.path.isfile(path):
            return _migrate_legacy_conversation(project_name, path)
    return _read_thread_turns(path)


def list_threads(project_name: str) -> list:
    """SPEC-206 §2.2: which of this project's areas have any real chat
    history -- a Part's own thread is never listed here (part threads
    are global, discovered by opening that Part, not by scanning a
    project). Includes an as-yet-unmigrated legacy `overview` thread, so
    a caller sees it exists before `load_thread`'s own lazy migration
    ever runs."""
    areas = []
    for area in _PROJECT_CHAT_AREAS:
        path = _project_thread_path(project_name, area)
        if os.path.isfile(path):
            areas.append(area)
        elif area == "overview" and os.path.isfile(_conversation_path(project_name)):
            areas.append(area)
    return areas

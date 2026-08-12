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
        datasheets/<part_id>.pdf          (not managed by this module yet)
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


class SchemaValidationError(Exception):
    """Raised when a record fails a required-field or provenance check --
    SPEC-300 §2.2's "must reject," never merely document, requirement.
    A record that fails this is never written to disk."""


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

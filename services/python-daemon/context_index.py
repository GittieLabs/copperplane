"""
SPEC-206 §2.6: the real, rebuildable retrieval index `PRODUCT-PLAN.md`
§4 describes -- `<storage_root>/.index/context.sqlite3`, never
authoritative (every real fact still lives in its own Part/Project/
thread JSON record; this is a derived, disposable search index over the
same content, safe to delete at any time -- deleting it is a supported
recovery action, not a special-cased one: `needs_rebuild()` already
returns `True` when the file is simply missing).

Deliberately its own module (SPEC-206 §3: `library_store.py` is already
49 KB and growing; the index and the agent layer belong in their own
modules, not folded into the existing store).

Why FTS5 and no vector store in v1 (decided with the user, not assumed
-- see SPEC-206 §2.6's own full reasoning): most retrieval here is
structured lookup, not fuzzy search; FTS5 ships inside stdlib
`sqlite3`, nothing new to install/freeze/sign/notarize; the real
alternatives (`sqlite-vec`, LanceDB, a static-embedding model,
AgentFlow's own `VectorMemory`) were each checked and rejected for a
real, specific reason. Add a vector tier behind `Retriever` only when a
real, observed retrieval failure justifies it.
"""
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Protocol

import library_store

_INDEX_SCHEMA_VERSION = 1


def _index_path() -> str:
    """Deliberately never under a project directory (SPEC-206 §3's own
    explicit constraint): a rebuildable cache copied to another machine
    alongside a linked project folder would arrive stale and pointing
    at paths that don't exist there."""
    return os.path.join(library_store._ensure_dir(".index"), "context.sqlite3")


def fts5_available() -> bool:
    """SPEC-206 §3's own explicit instruction: probe with a real
    `CREATE VIRTUAL TABLE ... USING fts5(...)` against an in-memory
    database, never sniff `sqlite3.sqlite_version` -- FTS5 is a
    compile-time SQLite option that can differ between the dev venv and
    the frozen PyInstaller sidecar (`daemon.spec` today declares no
    `binaries`/`datas`/`hiddenimports`), and only a real attempt proves
    it either way. Cross-platform live verification is `SPEC-403`'s own
    named, separate backlog item -- this function's job is only to fail
    closed to `LikeScanRetriever` when FTS5 genuinely isn't there, on
    any platform."""
    try:
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE VIRTUAL TABLE probe USING fts5(body)")
        finally:
            conn.close()
        return True
    except sqlite3.OperationalError:
        return False


def _connect() -> sqlite3.Connection:
    """A fresh connection per operation, never stashed on a module
    global -- SPEC-206 §3's own explicit constraint: SPEC-105's async
    jobs run off the main thread, and a sqlite3 connection is not
    shareable across threads by default."""
    conn = sqlite3.connect(_index_path())
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection, fts5: bool) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY, scope TEXT NOT NULL, scope_id TEXT NOT NULL,
            kind TEXT NOT NULL, part_id TEXT, project_name TEXT, category TEXT,
            body TEXT NOT NULL, source_ref TEXT NOT NULL, source_mtime REAL
        )
    """)
    if fts5:
        # A plain, standalone FTS5 table (not `content=`-linked to
        # `chunks`) -- a full rebuild always repopulates both tables
        # from scratch together, so there is no incremental-sync
        # trigger machinery to maintain, matching PRODUCT-PLAN.md §4's
        # own "rebuild must be cheap" framing (a full rebuild, not an
        # incremental update, is the normal path here).
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED, body)")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()


# --- Chunk extraction (SPEC-206 §2.6's named real sources) ---------------


def _guidance_chunks(part: dict):
    """Real, per-item quotes (resolvable as a real `guidance_item`
    SourceRef -- the quote really is one of `categories[category]`'s
    own items, so `_resolve_guidance_item` in `chat_agents.py` will
    confirm it). A category's own generated `category_summaries` text
    is real, useful, searchable content too, but is *not* itself a
    literal quoted excerpt -- citing it as `guidance_item` would produce
    a SourceRef that can never resolve. Cited instead as `part_field`
    (`field: "design_guidance"`), honestly reflecting "this came from
    the part's own design_guidance field" without falsely implying an
    exact quote."""
    guidance = part.get("design_guidance")
    if not guidance:
        return
    part_id = part["part_id"]
    content_hash = guidance.get("content_hash")
    for category, items in guidance.get("categories", {}).items():
        for item in items:
            quote = item.get("quote", "")
            if not quote:
                continue
            yield {
                "scope": "part", "scope_id": part_id, "kind": "guidance_item",
                "part_id": part_id, "project_name": None, "category": category, "body": quote,
                "source_ref": {
                    "kind": "guidance_item", "part_id": part_id, "category": category,
                    "quote": quote, "content_hash": content_hash,
                },
            }
        summary = guidance.get("category_summaries", {}).get(category)
        if summary:
            yield {
                "scope": "part", "scope_id": part_id, "kind": "part_field",
                "part_id": part_id, "project_name": None, "category": category, "body": summary,
                "source_ref": {"kind": "part_field", "part_id": part_id, "field": "design_guidance"},
            }


def _connection_guidance_chunks(part: dict):
    """Per-pin entries map cleanly to the real `connection_guidance`
    kind (a real `pin_number` `_resolve_connection_guidance` can
    confirm). `general_notes` isn't tied to one pin, so it's cited as
    `part_field` instead, the same honest reasoning as guidance
    summaries above."""
    guidance = part.get("connection_guidance")
    if not guidance:
        return
    part_id = part["part_id"]
    for entry in guidance.get("pin_guidance", []):
        pin_number = entry.get("pin_number")
        text = entry.get("guidance", "")
        if not pin_number or not text:
            continue
        yield {
            "scope": "part", "scope_id": part_id, "kind": "connection_guidance",
            "part_id": part_id, "project_name": None, "category": None, "body": text,
            "source_ref": {"kind": "connection_guidance", "part_id": part_id, "pin_number": str(pin_number)},
        }
    notes = guidance.get("general_notes")
    if notes:
        yield {
            "scope": "part", "scope_id": part_id, "kind": "part_field",
            "part_id": part_id, "project_name": None, "category": None, "body": notes,
            "source_ref": {"kind": "part_field", "part_id": part_id, "field": "connection_guidance"},
        }


def _part_identity_chunks(part: dict):
    """Part fields worth matching (SPEC-206 §2.6's own named source) --
    each cited as `part_field`, a real, always-resolvable top-level key
    on the part. Pin names aren't top-level keys themselves, but the
    real `pins` list they live in is -- cited as `field: "pins"`,
    honestly pointing at the real list a pin name was found in rather
    than a field name that doesn't exist."""
    part_id = part["part_id"]
    for field in ("manufacturer", "package"):
        value = part.get(field)
        if value:
            yield {
                "scope": "part", "scope_id": part_id, "kind": "part_field",
                "part_id": part_id, "project_name": None, "category": None, "body": str(value),
                "source_ref": {"kind": "part_field", "part_id": part_id, "field": field},
            }
    for pin in part.get("pins", []):
        name = pin.get("name")
        if name:
            yield {
                "scope": "part", "scope_id": part_id, "kind": "part_field",
                "part_id": part_id, "project_name": None, "category": None, "body": name,
                "source_ref": {"kind": "part_field", "part_id": part_id, "field": "pins"},
            }


def _part_note_chunks(part: dict):
    """SPEC-206 §2.7 (`chat.promote_turn`) hasn't shipped yet -- Parts
    have no real `notes` field today, so `part.get("notes")` is always
    `None`/absent and this yields nothing. Wired now, inert until that
    context lands, the same "safe until it activates" pattern
    `chat_agents.py`'s own deferred `note`/`check_finding` resolvers
    already use."""
    part_id = part["part_id"]
    for note in part.get("notes") or []:
        note_id = note.get("note_id")
        text = note.get("text", "")
        if not note_id or not text:
            continue
        yield {
            "scope": "part", "scope_id": part_id, "kind": "note",
            "part_id": part_id, "project_name": None, "category": None, "body": text,
            "source_ref": {"kind": "note", "scope": "part", "scope_id": part_id, "note_id": note_id},
        }


def _extract_part_chunks(part: dict):
    yield from _guidance_chunks(part)
    yield from _connection_guidance_chunks(part)
    yield from _part_identity_chunks(part)
    yield from _part_note_chunks(part)


def _extract_project_chunks(project: dict):
    """Project intent (a real, resolvable `project_intent` SourceRef)
    and promoted notes (inert until SPEC-206 §2.7 ships -- same reasoning
    as `_part_note_chunks` above). `last_results`/`export_history`
    entries are deliberately NOT indexed here: SPEC-206 §2.3's SourceRef
    union has no kind that covers them, and indexing content with no
    real citable form would either produce an uncitable chunk or a
    SourceRef that can never resolve -- named as a real, honest gap in
    this context's own Plan Drift, not silently worked around."""
    project_name = project["name"]
    intent = project.get("intent")
    if intent:
        yield {
            "scope": "project", "scope_id": project_name, "kind": "project_intent",
            "part_id": None, "project_name": project_name, "category": None, "body": intent,
            "source_ref": {"kind": "project_intent", "project_name": project_name},
        }
    for note in project.get("notes") or []:
        note_id = note.get("note_id")
        text = note.get("text", "")
        if not note_id or not text:
            continue
        yield {
            "scope": "project", "scope_id": project_name, "kind": "note",
            "part_id": None, "project_name": project_name, "category": None, "body": text,
            "source_ref": {"kind": "note", "scope": "project", "scope_id": project_name, "note_id": note_id},
        }


def _extract_all_chunks():
    for part_id in library_store.list_parts():
        try:
            part = library_store.load_part(part_id)
        except OSError:
            continue
        yield from _extract_part_chunks(part)
    for project_name in library_store.list_projects():
        try:
            project = library_store.load_project(project_name)
        except (OSError, library_store.ProjectDirectoryMissingError):
            continue
        yield from _extract_project_chunks(project)


# --- Rebuild + staleness ---------------------------------------------------


def _newest_real_mtime() -> float:
    """PRODUCT-PLAN.md §4's own staleness check: the newest mtime under
    `library/`/`projects/` in the storage root. Real, honest gap named
    in this context's own Plan Drift: a *linked* project's own content
    lives under its real external directory, not under `projects/` in
    the storage root, so an edit to a linked project's own part/chat
    data doesn't bump anything this function scans -- only the small
    pointer record does, and only when `save_project` is actually
    called. `context.rebuild_index()`'s own manual trigger, and the
    fact that the index is always cheap to fully rebuild, are the real
    backstop for that gap, not a claim this heuristic is perfectly
    precise for every real storage layout."""
    root = library_store.current_storage_root()
    newest = 0.0
    for subdir in ("library", "projects"):
        base = os.path.join(root, subdir)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, filenames in os.walk(base):
            for name in filenames:
                try:
                    newest = max(newest, os.path.getmtime(os.path.join(dirpath, name)))
                except OSError:
                    continue
    return newest


def needs_rebuild() -> bool:
    path = _index_path()
    if not os.path.isfile(path):
        return True
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'last_indexed'").fetchone()
    except sqlite3.OperationalError:
        # A missing/partial `meta` table -- an interrupted previous
        # rebuild, or a pre-schema file. Same real recovery path as a
        # fully-missing file: rebuild.
        return True
    finally:
        conn.close()
    if row is None:
        return True
    return _newest_real_mtime() > float(row["value"])


def rebuild_index() -> dict:
    """`context.rebuild_index` (SPEC-206 §2.5/§2.8): a full rebuild,
    always -- drops and recreates both tables, matching `PRODUCT-PLAN.md`
    §4's own "rebuild must be cheap" framing (a corpus of a few thousand
    short strings, not a reason to build incremental-sync machinery)."""
    fts5 = fts5_available()
    conn = _connect()
    try:
        conn.execute("DROP TABLE IF EXISTS chunks")
        conn.execute("DROP TABLE IF EXISTS chunks_fts")
        _ensure_schema(conn, fts5)
        chunk_count = 0
        for chunk in _extract_all_chunks():
            chunk_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO chunks (chunk_id, scope, scope_id, kind, part_id, project_name, category, body, "
                "source_ref, source_mtime) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    chunk_id, chunk["scope"], chunk["scope_id"], chunk["kind"], chunk.get("part_id"),
                    chunk.get("project_name"), chunk.get("category"), chunk["body"],
                    json.dumps(chunk["source_ref"], sort_keys=True), time.time(),
                ),
            )
            if fts5:
                conn.execute("INSERT INTO chunks_fts (chunk_id, body) VALUES (?, ?)", (chunk_id, chunk["body"]))
            chunk_count += 1
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_indexed', ?)", (str(time.time()),))
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)", (str(_INDEX_SCHEMA_VERSION),)
        )
        conn.commit()
    finally:
        conn.close()
    return {"chunk_count": chunk_count, "fts5": fts5}


def ensure_fresh_index() -> None:
    if needs_rebuild():
        rebuild_index()


# --- Retrieval --------------------------------------------------------------


@dataclass
class Chunk:
    body: str
    source_ref: dict
    kind: str
    score: float


class Retriever(Protocol):
    def search(self, query: str, *, scopes: list, limit: int = 8) -> list:
        ...


def _scope_where(scopes: list) -> tuple:
    if not scopes:
        return "", []
    clauses = []
    params = []
    for scope, scope_id in scopes:
        clauses.append("(c.scope = ? AND c.scope_id = ?)")
        params.extend([scope, scope_id])
    return " AND (" + " OR ".join(clauses) + ")", params


def _fts5_query(query: str) -> str:
    """Every token individually double-quoted (FTS5 phrase syntax) and
    implicitly ANDed (FTS5's own default for space-separated terms) --
    treats arbitrary user text as literal tokens to match rather than
    parsing it as an FTS5 boolean expression, so a query containing a
    stray quote or a reserved word (AND/OR/NOT) can never raise a real
    `sqlite3.OperationalError` from malformed MATCH syntax."""
    tokens = query.split()
    if not tokens:
        return '""'
    return " ".join('"' + t.replace('"', '""') + '"' for t in tokens)


def _row_to_chunk(row: sqlite3.Row, score: float) -> Chunk:
    return Chunk(body=row["body"], kind=row["kind"], source_ref=json.loads(row["source_ref"]), score=score)


class Fts5Retriever:
    """Real FTS5 MATCH query, ranked by `bm25()` (more negative = more
    relevant in FTS5's own convention -- negated here so `Chunk.score`
    reads as "higher is more relevant," a friendlier convention for any
    future caller)."""

    def search(self, query: str, *, scopes: list = None, limit: int = 8) -> list:
        scope_clause, scope_params = _scope_where(scopes)
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT c.body, c.kind, c.source_ref, bm25(chunks_fts) AS rank "
                "FROM chunks_fts f JOIN chunks c ON c.chunk_id = f.chunk_id "
                "WHERE chunks_fts MATCH ?" + scope_clause + " ORDER BY rank LIMIT ?",
                [_fts5_query(query), *scope_params, limit],
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_chunk(r, -r["rank"]) for r in rows]


class LikeScanRetriever:
    """The correct-but-slower fallback when FTS5 isn't compiled into
    this build's `sqlite3` (SPEC-206 §2.6's own explicit fallback
    requirement) -- a plain substring scan, real and correct, just
    without ranked relevance (every match scores the same)."""

    def search(self, query: str, *, scopes: list = None, limit: int = 8) -> list:
        scope_clause, scope_params = _scope_where(scopes)
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT body, kind, source_ref FROM chunks c WHERE body LIKE ?" + scope_clause + " LIMIT ?",
                [f"%{query}%", *scope_params, limit],
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_chunk(r, 1.0) for r in rows]


def search(query: str, scopes: list = None, limit: int = 8) -> list:
    """The real `Retriever` entry point (SPEC-206 §2.6): ensures the
    index is fresh, picks whichever real implementation this build's
    `sqlite3` actually supports, and returns real `Chunk`s. Never
    assumes FTS5 -- re-probed on every call rather than cached, since
    the probe itself is a cheap in-memory `CREATE VIRTUAL TABLE` and
    correctness (never risking a stale "FTS5 works" assumption across
    a schema/build change) is worth more than the sub-millisecond it
    saves."""
    ensure_fresh_index()
    retriever = Fts5Retriever() if fts5_available() else LikeScanRetriever()
    return retriever.search(query, scopes=scopes or [], limit=limit)

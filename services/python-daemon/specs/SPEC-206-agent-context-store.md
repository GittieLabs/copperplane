---
id: SPEC-206
title: "Agent Context Store, Retrieval & Conversation Persistence"
status: Completed
type: Module
created: 2026-08-21
last_updated: 2026-08-24
target_version: v0.3.0
location: "services/python-daemon/specs/SPEC-206-agent-context-store.md"
parent_spec: "../../../apps/tauri-ui/specs/SPEC-318-in-context-agent-chat-and-review.md"
child_specs: []
user_facing: false
---

# SPEC-206: Agent Context Store, Retrieval & Conversation Persistence

## 1. Executive Summary & Goals

*   **High-Level Goal:** Build the daemon-side layer `SPEC-318`'s per-area agents stand on: a durable
    conversation store the app fully owns, a source-reference model that makes every answer traceable
    to a real record, a rebuildable retrieval index over everything this app already knows about a
    part and a project, a promotion path that turns a resolved conversation into a durable cited
    note, and the AgentFlow wiring that dispatches an area key to an agent with **no model involved
    in that dispatch**. It also closes a prerequisite gap: `SPEC-308`'s connection guidance is
    generated and then discarded, and must be persisted before any agent can be grounded in it.
*   **Business / Technical Value:** The premise of `SPEC-318` is that an agent already has access to
    what the app produced for a part. Half of that is true today -- `SPEC-205`'s `design_guidance`
    lives on the Part record -- and half is not. More broadly, this app has spent forty specs
    producing high-quality, cited artifacts and has no way to *retrieve* any of it: every list
    operation is an O(n) directory scan, and `PRODUCT-PLAN.md` §4's `.index/` SQLite cache was
    specified in `SPEC-304` §2 ("index rebuild is cheap and runs on startup when stale") and left
    unbuilt by `CTX-304.1`. That index is the missing piece, and building it for agent retrieval also
    finally delivers the cross-project query performance `SPEC-304` named as its own honest cost.
*   **Non-Goals:**
    *   **A vector database or any embedding model.** Deliberate, and confirmed with the user rather
        than assumed -- see §2.6 for the reasoning and the interface that keeps the door open.
    *   **Making the index authoritative.** `PRODUCT-PLAN.md` §4 is unambiguous: files are truth, the
        index is a rebuildable cache deletable at any time. Nothing may read from the index that
        cannot be answered from the files, and no write may land only in the index.
    *   **Adopting AgentFlow's memory or session layers.** `SessionManager`, `Scratchpad`,
        `ArtifactStore`, `MemoryManager`, `FileMemory` and `MultiUserHistory` were all read in the
        installed source; §3 records why none fits. `VectorMemory`/`VectorBackend` are real and are
        the seam we would use *if* §2.6's deferral is ever revisited.
    *   **A conversational agent that picks its own tools across areas.** Each agent's tool
        allow-list is declared in its own `.prompt.md` and enforced by `AgentConfig.tools`.
    *   **Schema migration machinery.** This repo has an established convention -- read-time
        `setdefault` backfill, `schema_version` stays the literal `1` -- and every new field here
        follows it.

## 2. System Architecture & Design Choices

### 2.1 Project intent

One new optional key on the Project record, following the existing convention exactly (plain dict,
no dataclass, `schema_version` unchanged, backfilled at read time):

```python
project["intent"]  # str | None   -- None means never set; "" means deliberately cleared
```

`None` and `""` must stay distinguishable, for the same reason `CTX-205.3` made `design_guidance`
backfill as `None` rather than `{}`: "never asked" and "asked, answered nothing" are different states
the UI reads differently.

Route: `project.set_intent(project_name: str, intent: str) -> dict`, synchronous, round-tripping
through `save_project`/`load_project`. No special handling is needed to keep `intent` out of the
storage-root pointer record -- `save_project`'s pointer branch hard-codes exactly
`{name, directory, schema_version}`, so a linked project's intent lands in the manifest at
`<directory>/.hardware-agent-studio/project.json` and travels with the folder automatically.

### 2.2 Conversation store

**Threads, not one conversation per project.** A thread is identified by a scope and a scope id:

| Scope | Scope id | File |
| :--- | :--- | :--- |
| `project` | `<project_name>:<area>` | linked: `<directory>/.hardware-agent-studio/chats/<area>.jsonl`<br>unlinked: `<storage_root>/projects/<name>/chats/<area>.jsonl` |
| `part` | `<part_id>` | `<storage_root>/library/chats/parts/<part_id>.jsonl` |

The project split mirrors `save_project`'s existing pointer/manifest branch precisely; use
`project_directory(name)` rather than reinventing the resolution. Part threads are always global
under `library/`, because a Part is a global `SPEC-304` object -- `SPEC-318` §2.1 carries the
reasoning and records the `PRODUCT-PLAN.md` §2.1 amendment this implies.

**This is a real change to today's behaviour and must be called out in the implementing context:**
`_conversation_path()` currently hardcodes `<storage_root>/projects/<name>/conversation.jsonl` and
therefore does **not** follow `CTX-312.1`'s directory link. A project handed to another machine today
arrives with its history stripped. Fixing that is part of this spec.

**Migration.** On first read of a project's `overview` thread, if no `chats/overview.jsonl` exists but
a legacy `conversation.jsonl` does, its turns are read, upconverted and written to the new path. The
legacy file is **left in place**, not deleted -- consistent with this repo's non-destructive
read-time-backfill convention, and cheap insurance. A `migrated_from` key in the new thread's first
record notes where it came from.

**Turn record.** The existing `ConversationTurn` (`role`, `content`, optional client-stamped
`timestamp`) is insufficient: it cannot carry sources, and it cannot carry tool calls -- which matters
because AgentFlow's `AgentExecutor` discards them (§3). The stored shape:

```python
{
  "turn_id": str,                 # uuid4
  "role": "user" | "assistant",
  "content": str,
  "timestamp": str,               # ISO-8601 UTC, SERVER-stamped -- see note below
  "agent": str | None,            # which area agent produced an assistant turn
  "sources": [SourceRef],         # [] on user turns; see 2.3
  "sources_dropped": int,         # count of refs that failed to resolve and were dropped
  "general_practice": bool,       # assistant turn not grounded in a cited record
  "tool_calls": [                 # audit trail; [] when none
      {"name": str, "input": dict, "result_digest": str}
  ],
  "provenance": {"provider": str, "model": str} | None,
  "promoted_note_id": str | None,
}
```

Two deliberate choices. `timestamp` is **server-stamped**, unlike `CTX-313.1`'s client-stamped turns
-- the daemon is writing the record anyway and a client clock is the wrong authority for ordering an
audit trail; the migration upconverter preserves whatever client timestamp a legacy turn carries and
leaves `None` ones unknown rather than inventing a time. And `tool_calls[].result_digest` is a
truncated summary, not the full result: a `datasheet.read_pages` result can be tens of kilobytes, it
is re-derivable from the same call, and a JSONL transcript is not an artifact store.

Routes: `chat.load_thread(scope, scope_id) -> list` and `chat.list_threads(project_name) -> list`,
both synchronous; `chat.send(...)` is async (§2.5).

### 2.3 The source reference model

Every assistant turn carries validated `SourceRef` objects. The union, with the resolver each kind
needs:

```python
{"kind": "datasheet_page",       "part_id": str, "page": int, "content_hash": str}
{"kind": "guidance_item",        "part_id": str, "category": str, "quote": str, "content_hash": str}
{"kind": "connection_guidance",  "part_id": str, "pin_number": str}
{"kind": "part_field",           "part_id": str, "field": str}
{"kind": "check_finding",        "project_name": str, "area": str, "finding_id": str}
{"kind": "note",                 "scope": str, "scope_id": str, "note_id": str}
{"kind": "chat_turn",            "scope": str, "scope_id": str, "turn_id": str}
{"kind": "project_intent",       "project_name": str}
```

**Contract, inherited from `SPEC-205` and non-negotiable: a reference that does not resolve is
dropped, never repaired.** `_make_validate_handler` in `datasheet_guidance.py` already implements
exactly this discipline for guidance items and is the model to follow. Two additions specific to chat:

*   **Dropped references are counted, not hidden.** `sources_dropped` records how many failed. An
    answer that arrives claiming datasheet support and ends with `sources: []` and
    `sources_dropped: 3` is a materially different thing from one that never claimed any, and the UI
    must be able to say so. Silently rendering nothing is the dishonest option.
*   **`content_hash` is carried, not assumed.** `design_guidance.content_hash` is a real sha256 of
    the exact cached PDF bytes (`content_hash_of_file`). A `datasheet_page` or `guidance_item`
    reference records the hash it was made against, so that when guidance is regenerated from a newer
    datasheet the old chip is marked stale rather than opening a page that has moved.
    `document_revision` is **always `None`** today -- no extractor exists -- so the hash is the only
    real version signal available.

`general_practice: true` is the chat equivalent of `SPEC-205`'s Class C: content offered from general
engineering knowledge, never attributed to the datasheet, visually segregated by the UI. A known v1
limitation to record rather than paper over: the flag is **per turn**, so an answer mixing cited fact
and general practice must mark the whole turn. Per-claim marking needs a structured answer format and
is deferred.

### 2.4 Persisting connection guidance -- the prerequisite

`kicad.generate_connection_guidance` loads a Part, calls
`component_pipeline.generate_connection_guidance(...)` and **returns the result without saving it**;
`PartDetail.tsx` holds it in `useState` and loses it on unmount. Nothing about `SPEC-318` works until
this is a record. New key on the Part, backfilled to `None`:

```python
part["connection_guidance"] = {
    "generated_at": str,
    "pins_hash": str,        # sha256 over the canonical JSON of part["pins"]
    "pin_guidance": [{"pin_number": str, "guidance": str}],
    "general_notes": str,
    "provenance": {"provider": str, "model": str},
}
```

`pins_hash` exists so the record can be marked stale if the Part's pins are later re-extracted -- the
same invalidation role `content_hash` plays for `design_guidance`. Validation stays where it already
is: `_validate_connection_guidance` is **fail-closed** (raises `ComponentValidationError` on a
`pin_number` not present on the part), unlike guidance extraction's drop-silently, and that difference
is correct and must not be harmonised -- a pin number that does not exist is a broken result, not a
weak one.

### 2.5 Agent dispatch

The `services/python-daemon/agentflow/` tree already exists (`agents/`, `workflows/`) and is what
`ConfigLoader` expects. New files:

*   `agentflow/router.prompt.md` -- a `RouterConfig` whose `routing_rules` match on the caller-supplied
    `area` key, with **`llm_fallback` explicitly false** (it defaults to true). There are exactly five
    known area values and the rules cover all of them; a sixth must be a hard error, not an LLM guess.
    This is what keeps `PRODUCT-PLAN.md` §3.2 intact.
*   `agentflow/agents/chat_{overview,components,schematic,pcb,enclosure}.prompt.md` -- one
    `AgentConfig` each, declaring `tools` (the allow-list `AgentExecutor` enforces), `max_tool_rounds`
    and `temperature`. **`SPEC-318` §2.3's table is the authority on which tools each agent holds**,
    and the two documents must be kept in agreement.

Dispatch is `await RouterEngine.route("", context={"area": area})` -- note it is a coroutine, while
`daemon.py`'s route handlers are synchronous -- yielding a target name, then the matching
`AgentConfig`, then an `AgentExecutor` constructed with the app's own transcript as `history`. No
model call happens before the agent is chosen.

**Tools the agents need.** `agent.dispatch_tool` rejects anything not present in **both**
`tool_registry.TOOL_DEFINITIONS` **and** `ROUTES`, so each row below needs both, and the two new
routes need `_build_routes()` entries as well:

| Tool | Route exists today? | `TOOL_DEFINITIONS` today? | Gated |
| :--- | :--- | :--- | :--- |
| `context.search` | **no -- new** | no -- add | no |
| `datasheet.read_pages` | **no -- new** | no -- add | no |
| `library.load_part` | yes | no -- add | no |
| `library.list_parts` | yes | no -- add | no |
| `kicad.check_schematic` | yes | no -- add | no |
| `kicad.check_board` | yes | no -- add | no |
| `kicad.get_component_heights` | yes | no -- add | no |
| `component.search` | yes | yes | no |
| `library.save_confirmed_part` | yes | no -- add | **yes** |

`library.save_confirmed_part` must also be added to `CONFIRMATION_REQUIRED_TOOLS`, which today holds
only `kicad.inject_component`. AgentFlow has no confirmation mechanism of any kind (§3), so the gate
is entirely `agent.dispatch_tool`'s existing `confirmed` flag -- an unconfirmed call returns a pending
result with zero side effects, exactly as `CTX-204.1` built it.

`datasheet.read_pages(part_id, pages)` is new and thin: `datasheet_structure.extract_pages(pdf_path)`
extracts the **whole** document and takes no page selector, so this route filters the requested pages
out of its full result. It must reuse `ensure_datasheet_cached` rather than re-fetching.

New route `chat.send(scope, scope_id, area, message, project_name=None)`, **async** -- it is an LLM
call, so it belongs in `ASYNC_ROUTES` with real `cancel_event` support like every other LLM route. It
appends the user turn, assembles context, runs the agent, validates every returned `SourceRef`,
appends the assistant turn, and returns it.

### 2.6 Retrieval: `.index/`, FTS5, and why no vector store

Finally builds `PRODUCT-PLAN.md` §4's `.index/`.

```
<storage_root>/.index/context.sqlite3     # rebuildable, never authoritative, never in a project dir
```

Tables: a `chunks` table (`chunk_id`, `scope`, `scope_id`, `kind`, `part_id`, `project_name`,
`category`, `body`, `source_ref` as JSON, `source_mtime`), an FTS5 virtual table over `body`, and a
`meta` table holding the index schema version and the last indexed timestamp. Chunk sources: guidance
items and their `category_summaries`, connection-guidance pins and notes, Part fields worth matching
(`part_id`, `manufacturer`, `package`, pin names), project intent, promoted notes, and chat turns that
have been **explicitly promoted** -- not every chat turn, which would let an unverified answer be
retrieved as though it were a source.

`PRODUCT-PLAN.md` §4 already states the requirement: rebuild must be cheap and must run on startup
when the file tree is newer than the index. Compare the newest mtime under `library/` and `projects/`
against `meta.last_indexed`; a mismatch triggers a rebuild. `context.rebuild_index()` exposes it
manually, and deleting the file must be a supported recovery action.

**The retrieval interface is the point of this section**, because it is what makes the deferral safe:

```python
class Retriever(Protocol):
    def search(self, query: str, *, scopes: list[Scope], limit: int = 8) -> list[Chunk]
```

`Chunk` carries `body`, a `SourceRef`, a `kind` and a score. Two implementations ship: `Fts5Retriever`,
and a `LikeScanRetriever` fallback that is correct and slower.

**Why no vector database, and no embedding model, in v1.** Decided with the user rather than assumed:

*   Most retrieval here is **structured lookup, not search** -- "the power guidance for this part" is
    a key access. The genuinely fuzzy remainder is a small corpus of technical prose dense with
    distinctive tokens (part numbers, "brown-out", "decoupling", "courtyard"), close to the best case
    for lexical search and the worst case for justifying an ANN index.
*   FTS5 ships **inside stdlib `sqlite3`** -- nothing new to install, freeze, sign or notarize.
    `SPEC-402` shipped real signed macOS builds and real pre-release Windows/Linux builds, and
    `CTX-402.4` records how expensive one badly-behaved native wheel already was: a `cryptography`
    pin forced by a real failed x86_64 macOS CI leg, because 49.0.0 dropped macOS x86_64 wheels and
    the build-from-source fallback produced an arm64-only `.so` that PyInstaller's own arch check
    caught. Adding a native dependency to that pipeline needs a stronger reason than a corpus of a
    few thousand short strings.
*   The alternatives were checked, not dismissed. `sqlite-vec` (MIT/Apache-2.0) requires
    `enable_load_extension`, which is **disabled in macOS system Python** and varies per build -- a
    property of whichever interpreter PyInstaller freezes against, on three platforms. LanceDB drags
    `pyarrow`. `numpy` is already frozen in (via `trimesh`), so brute-force cosine over a few thousand
    vectors would be exact and sub-millisecond -- but it still needs an embedding model, and the only
    fully-local option avoiding torch/onnxruntime is a static-embedding model (`model2vec`, MIT,
    numpy-only inference, roughly 8-30 MB depending on variant) added to the bundle. Provider
    embedding APIs are not an option: Anthropic has none, and calling one would put the user's design
    data on the network, against the local-first promise.
*   AgentFlow's `VectorMemory` / `VectorBackend` protocol is real (Qdrant, LanceDB and Chroma backends
    all ship), but the library provides **no embedding function at all** and none of the three
    backends is installed under the current `[anthropic,openai,google]` pin. It is plumbing, not a
    feature.

So: add a vector tier behind `Retriever` when a **real, observed** retrieval failure justifies it, and
record that failure in the context file that adds it. That is the same standard `SPEC-203`'s
retirement and `CTX-204.1`'s corrected AgentFlow assumptions were held to.

### 2.7 Promotion: the actual answer to answer consistency

The stated goal is not re-resolving the same problem and not giving inconsistent answers. A retrieval
index does not deliver that -- the same question over the same retrieved context still samples
different prose. What delivers it is moving a settled conclusion out of a transcript and into a record
later conversations retrieve as fact.

`chat.promote_turn(scope, scope_id, turn_id, target_scope, target_id) -> dict` copies an assistant
turn's content and its **already-validated** sources into a durable note on a Part or a Project:

```python
part["notes"] = [{
    "note_id": str, "text": str, "sources": [SourceRef],
    "created_at": str, "origin": {"scope": str, "scope_id": str, "turn_id": str},
    "provenance": {"provider": str, "model": str},
}]      # backfilled to None
```

Notes are indexed as chunks and are therefore retrieved by every later conversation in scope.

**Promotion is always user-initiated.** Never automatic. An agent that writes to the library on its
own judgement is precisely the "apply a change the user didn't see first" that `PRODUCT-PLAN.md`
§3.3 puts in the right-hand column, and it would let an unverified answer harden into a retrievable
fact without anyone reading it. The user promotes; the record then carries its own provenance and
origin turn so it stays traceable back to the conversation that produced it.

### 2.8 Cross-Module Impacts

*   `services/python-daemon/library_store.py` -- thread read/write and migration; `intent`,
    `connection_guidance` and `notes` fields with their backfills and validators; the chunk extractors.
*   `services/python-daemon/context_index.py` (new) -- the SQLite index, `Retriever` implementations,
    staleness check and rebuild.
*   `services/python-daemon/chat_agents.py` (new) -- router config load, agent construction, transcript
    assembly, `SourceRef` validation.
*   `services/python-daemon/daemon.py` -- new routes in `_build_routes()` (including
    `context.search` and `datasheet.read_pages`); `chat.send` and `context.rebuild_index` added to
    `ASYNC_ROUTES`; `daemon.get_capabilities` gains an FTS5 flag (§3).
*   `services/python-daemon/tool_registry.py` -- the `TOOL_DEFINITIONS` additions in §2.5;
    `library.save_confirmed_part` added to `CONFIRMATION_REQUIRED_TOOLS`.
*   `services/python-daemon/agentflow/` -- `router.prompt.md` and five agent `.prompt.md` files.

## 3. Known Constraints & Risks

*   **FTS5 must be verified in the frozen sidecar on all three platforms, not in the dev venv.** It is
    a compile-time SQLite option, and the daemon ships as a PyInstaller freeze whose `_sqlite3` comes
    from whichever interpreter built it -- `daemon.spec` currently declares no `binaries`, no `datas`
    and no `hiddenimports`. Probe it at index-open time with a real `CREATE VIRTUAL TABLE ... USING
    fts5(...)` against an in-memory database rather than sniffing `sqlite3.sqlite_version`, fall back
    to `LikeScanRetriever` when it throws, and surface the result through `daemon.get_capabilities` so
    `SPEC-303`'s "Copy Diagnostics" reports it. Cross-platform live verification is on the backlog as
    `SPEC-403` (`ROADMAP.md` §3.4) precisely because Windows and Linux paths have never been
    exercised; do not let this land as another untested claim.
*   **Three real AgentFlow 0.9.0 behaviours, read from the installed source.** `RuleEvaluator`'s
    condition parser is regex-based and accepts **single quotes only** -- `area == "schematic"` does
    not fail loudly, it silently evaluates false and falls through to the fallback target. `mode:
    async` is accepted by the workflow schema and behaves identically to `sync`; only `parallel` is
    actually branched on. And a node that raises does **not** abort its workflow -- the failure is
    swallowed into a `NodeOutput` with `metadata={"error": True}`, so any handler must check for it
    rather than assuming an exception would have propagated.
*   **AgentFlow's session and memory layers do not fit, and adopting them would be a mistake.**
    `MultiUserHistory` is in-memory, keyed by `user_id` with no thread concept, and its
    `append(user_id, role, content)` signature cannot store tool calls; `HistoryPersistence` is a
    `Protocol` with zero implementations. `StorageBackend` is `str`-only (no bytes), so `ArtifactStore`
    cannot hold a PDF or a mesh. `MemoryManager`'s `MemoryConfig.retention`/`max_entries` are declared
    and **never read** -- the advertised TTL and pruning are not implemented. `FileMemory.search()` is
    naive case-insensitive substring matching with a hard-coded score of `1.0`. This app writes its
    own store; that is the finding, not a preference.
*   **No streaming exists in 0.9.0.** Verified by grep across the package: no `yield`, no
    `AsyncIterator`/`AsyncGenerator`, no `stream=True`. Progress must come from `SPEC-105`'s job
    protocol and AgentFlow's `EventBus` events; `SPEC-318` §3 records the UX consequence.
*   **The `stdout` rule applies to every line of this work.** The daemon's `stdout` carries JSON-RPC
    frames only; a stray `print()` corrupts the stream and produces a request that hangs forever with
    no error. Any `EventBus` subscriber added here logs through `SPEC-107`'s logger to `stderr`,
    never to `stdout`.
*   **SQLite across threads.** `SPEC-105`'s async jobs run off the main thread, and a `sqlite3`
    connection is not shareable across threads by default (`check_same_thread`). Use a connection per
    operation or an explicit lock; do not stash one on a module global and hope.
*   **The index must never enter a portable project directory.** It lives under
    `<storage_root>/.index/` only. A rebuildable cache copied to another machine alongside a linked
    project folder would arrive stale and pointing at paths that do not exist there.
*   **`library_store.py` is already 49 KB and growing.** Threads, three new record fields, chunk
    extraction and migration will not fit comfortably. Splitting the store is not this spec's job, but
    the implementing context should put the index and the agent layer in their own modules (§2.8) and
    say so rather than defaulting to the existing file.
*   **Convention deviation, named rather than silent:** every other 2xx spec (`SPEC-201`-`SPEC-205`)
    declares `parent_spec: "../../../specs/SPEC-000-architecture-overview.md"` and appears in
    `SPEC-000`'s `child_specs`. This spec parents to a 3xx product spec instead, because it exists
    solely to serve `SPEC-318` and has no independent architectural meaning. The validator is
    satisfied either way, but an agent following `ROADMAP.md` §5.3's "read `SPEC-000` first, then
    follow the links" reaches this spec only through the UI tree. Chosen deliberately; revisit if the
    context store ever grows a second consumer.

## 4. Module Map & Reference Links

```text
[Root Spec](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-300](../../../apps/tauri-ui/specs/SPEC-300-product-ia-interaction-model.md)
          └── [SPEC-318](../../../apps/tauri-ui/specs/SPEC-318-in-context-agent-chat-and-review.md)
                 └── [This Spec](SPEC-206-agent-context-store.md)
                        ├── depends on [SPEC-205](SPEC-205-datasheet-design-guidance.md) (guidance records + the citation contract this extends)
                        ├── depends on [SPEC-204](SPEC-204-agent-tool-registry.md) (ToolRegistry + the confirmation gate)
                        ├── depends on [SPEC-304](../../../apps/tauri-ui/specs/SPEC-304-project-library-storage.md) (the storage layout and the unbuilt `.index/`)
                        ├── depends on [SPEC-105](../../../specs/SPEC-105-daemon-async-job-progress-protocol.md) (async job + cancellation)
                        └── depends on [SPEC-201](SPEC-201-llm-provider-abstraction.md) (provider selection)
```

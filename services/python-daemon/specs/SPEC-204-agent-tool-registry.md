---
id: SPEC-204
title: "Agent Tool Registry"
status: Draft
type: Module
created: 2026-08-14
last_updated: 2026-08-14
target_version: v0.1.0
location: "services/python-daemon/specs/SPEC-204-agent-tool-registry.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
user_facing: false
---

# SPEC-204: Agent Tool Registry

## 1. Executive Summary & Goals
*   **High-Level Goal:** Replace `daemon.py`'s hand-rolled `ROUTES: dict[str, Callable]` dispatch
    (`SPEC-102`) with AgentFlow's real `ToolRegistry`/`LocalToolDispatcher` (already an installed
    dependency since `SPEC-201`, currently used only for raw provider chat completions — its
    tool-calling machinery is entirely unused today), and define the confirmation-gating policy
    that decides which registered tools execute immediately versus require explicit user approval
    before running. This is what lets a natural-language request like "put a BME280 near the ESP32
    and give me an enclosure that fits" decompose into a model-driven plan across the KiCad and
    FreeCAD bridges, instead of the pure string-matching `parseCommand` recognizer
    (`apps/tauri-ui/src/lib/commands.ts`) `SPEC-302` currently ships and explicitly disclaimed
    ("not agentic tool-calling... SPEC-204... is what would let a model autonomously decide which
    route to call").
*   **Business / Technical Value:** `kicad_inject_component`'s own docstring already names this
    spec as the sole reason it's safe to call at all today: *"Mutates the board the instant it's
    called — the caller (eventually SPEC-204's confirmation gate) is solely responsible for only
    invoking this after approval."* Right now nothing enforces that — `SPEC-302`'s chat surface
    calls it unconditionally the instant the string `"inject"` is recognized, with no review step.
    `PRODUCT-PLAN.md` §5.2 also names this spec's gating policy as "load-bearing" and something
    that "should be written before, not after, injection gets a real UI" (the re-scoped `SPEC-108`),
    and `SPEC-308` (Footprints & Schematic Advisor) needs a real tool-calling loop to exist before
    "find or create a footprint, then guide me through connecting it" can be anything more than
    another hand-written string match.
*   **Non-Goals:**
    *   **Not a new chat UI.** `SPEC-302`'s surface (re-scoped in `PRODUCT-PLAN.md` §5.2 to "Project
        Conversation") is where any resulting tool-call transcript gets rendered. This spec is the
        daemon-side registry, dispatch, and gating policy only.
    *   **Not `HTTPToolDispatcher`.** Every route this spec registers already runs in-process inside
        the same daemon (`kicad_bridge`, `freecad_bridge`) — there is no out-of-process tool target
        today. `LocalToolDispatcher` covers 100% of the real surface; `HTTPToolDispatcher` is named
        here only so a future out-of-process tool doesn't have to re-litigate which dispatcher to
        use.
    *   **Not redesigning `SPEC-102`'s route handlers themselves.** Their business logic
        (`kicad_inject_component`, `freecad_generate_enclosure`, etc.) is reused as-is; this spec
        only changes what dispatches to them and what gates that dispatch.
    *   **Not every route becoming a model-callable tool on day one.** Local project/library CRUD
        (`project.save`, `library.load_part`, etc.) has no clear agentic use case yet — registering
        only the routes an agent plan would plausibly call (the KiCad/FreeCAD bridges, component
        search/generation) keeps the tool surface reviewable instead of dumping all ~20 routes in
        at once.

## 2. System Architecture & Design Choices
*   **Design Rationale — registry as a thin adapter, not a rewrite:** `ToolRegistry.add_dispatcher`
    takes a `set[str]` of tool names plus a `ToolDispatcher`; `LocalToolDispatcher.register(name,
    handler, description, input_schema)` requires `handler` to be `async def` and to return a plain
    `str` (confirmed from `agentflow/src/agentflow/tools/local_dispatcher.py` — not an assumed API).
    Existing `ROUTES` handlers return structured JSON-RPC results, not strings, so each tool
    registration needs a small async wrapper per route: call the existing handler, then serialize
    its structured result to a JSON string for the model to read back. This preserves `SPEC-102`'s
    handlers unchanged and keeps the adapter layer the only new code path.
*   **Confirmation-gating policy — the actual job of this spec.** Of every route in `daemon.py`'s
    `ROUTES`, exactly one mutates a live, already-open board: `kicad.inject_component`. Everything
    else (`freecad.generate_enclosure`, `kicad.generate_component`, `component.search`, `llm.chat`,
    and all `project.*`/`library.*` local-storage routes) reads, or writes only to this app's own
    local storage, never to a document the user has open elsewhere. The gating rule: **a tool tagged
    `writes_board: true` in its registration never executes on its first model-proposed call** — the
    registry returns a `pending_confirmation` result instead of dispatching, the daemon surfaces it
    up the existing job-progress channel (`SPEC-105`) for the UI to render as an explicit approval
    step, and only a second, explicit "confirmed" call actually dispatches to the real handler. No
    other tool needs this — full auto-execution is correct for anything that can't touch a document
    the user didn't ask this app to open.
*   **Data Flow / Interactions:** model requests a tool call → `ToolRegistry.dispatch(name, input)`
    → if `writes_board`, short-circuit to a `pending_confirmation` string result without calling the
    real handler → UI renders the proposed call and awaits user approval → UI's approval re-invokes
    the same tool with a `confirmed: true` flag the registry checks before calling through to the
    real handler. This two-phase shape needs a real sequence diagram once the exact confirmation
    payload shape is decided — left as an open question below rather than invented here.
*   **Cross-Module Impacts:**
    *   `services/python-daemon`: a new adapter module registering `ToolRegistry`/
        `LocalToolDispatcher` tools that wrap a subset of `daemon.py`'s existing `ROUTES` handlers;
        no change to the handlers themselves.
    *   `apps/tauri-ui`: consumes the new `pending_confirmation` result shape once `SPEC-302`'s
        surface (or its `PRODUCT-PLAN.md`-scoped successor) is updated to render it — that UI work
        is explicitly out of this spec's scope, but the shape this spec emits is a real contract
        that surface will depend on.
    *   Upstream: `SPEC-102` (the `ROUTES` dict being wrapped), `SPEC-201` (AgentFlow already a real
        dependency; this is the first spec in the repo to actually use its tool-calling machinery
        rather than only its provider abstraction).

## 3. Known Constraints & Risks
*   **`LocalToolDispatcher` handlers return plain strings only** (confirmed from real source, not
    assumed) — `kicad.generate_component`'s structured schema, `freecad.generate_enclosure`'s
    `.glb` mesh reference, and any other non-trivial payload must round-trip through JSON-encoded
    strings for the model to read, and the UI needs its own path to the real structured data (most
    routes already return enough for the UI to re-fetch or already receive it via the existing
    direct JSON-RPC call outside the tool-call loop — this needs to be worked out per-route, not
    assumed uniform).
*   **`LocalToolDispatcher.dispatch` swallows handler exceptions into `"Tool error: {exc}"` strings
    instead of raising** (confirmed from real source) — a board-write handler that fails mid-mutation
    surfaces to the model as an ordinary string, not a distinguishable failure signal. The
    confirmation-gate design must not rely on exceptions propagating normally.
*   **Every existing `ROUTES` handler already assumes single-threaded, synchronous dispatch**
    (`SPEC-102`'s own known constraint). Wrapping them in `async def` tool handlers for
    `LocalToolDispatcher` must not silently invite concurrent dispatch the daemon was never designed
    for — the wrapper is a signature adapter, not a concurrency change.
*   **Open question, not yet resolved:** the exact `pending_confirmation` → user-approval →
    re-dispatch round trip shape (is confirmation a second tool call with the same input plus a
    flag, a distinct `tool.confirm` route, or something SPEC-105's job-progress protocol already has
    a shape for?) needs a decision before implementation, not invented here per this repo's own
    scaffolding norm.

## 4. Module Map & Reference Links
```text
[Root Spec](../../../specs/SPEC-000-architecture-overview.md)
   └── [This Spec](SPEC-204-agent-tool-registry.md)
          └── [Context 204.1](../context/CTX-204.1-subfeature.md)
```
*   [SPEC-102](SPEC-102-daemon-rpc-router.md) — the `ROUTES` dict this spec wraps, not replaces.
*   [SPEC-105](../../../specs/SPEC-105-daemon-async-job-progress-protocol.md) — the likely channel
    for surfacing a `pending_confirmation` result to the UI.
*   [SPEC-201](SPEC-201-llm-provider-abstraction.md) — AgentFlow already a real dependency; this
    spec is the first to use its `ToolRegistry`/dispatcher machinery.
*   [SPEC-302](../../../apps/tauri-ui/specs/SPEC-302-chat-command-surface.md) — the chat surface
    this spec's tool-calling loop would eventually replace `parseCommand`'s string matching for
    (UI work explicitly out of this spec's own scope).

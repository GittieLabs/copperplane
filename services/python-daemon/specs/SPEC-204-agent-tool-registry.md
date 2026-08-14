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
    *   **Explicitly NOT a non-goal: changing AgentFlow itself.** AgentFlow (`~/repos/agentflow`,
        `gittielabs-agentflow`) is Keith's own library, not a fixed third-party dependency. Where
        §2/§3 below identify a real gap in `ToolRegistry`/`LocalToolDispatcher` that this spec's
        confirmation-gating and structured-result needs expose, the default is to close that gap
        upstream in AgentFlow itself, not to build a downstream workaround in this daemon.

## 2. System Architecture & Design Choices
*   **Design Rationale — two real AgentFlow gaps, closed upstream, not adapted around.** Reading
    `agentflow/src/agentflow/tools/` directly (not assumed) surfaces two real limitations in the
    installed `gittielabs-agentflow==0.8.2`, both of which this app is the first real consumer to
    hit:
    1.  `LocalToolDispatcher.register(name, handler, description, input_schema)` requires `handler`
        to return a plain `str` — no structured-result path exists. `kicad.generate_component`'s
        schema and `freecad.generate_enclosure`'s `.glb` mesh reference both need more than a bare
        string.
    2.  `LocalToolDispatcher.dispatch` swallows handler exceptions into `"Tool error: {exc}"`
        strings rather than raising or returning a distinguishable failure — any consumer needing
        to tell a genuine tool failure apart from a normal string result hits this, not just a
        board-write case.
    Since AgentFlow is Keith's own library, the plan is to fix both **in AgentFlow itself**, per the
    project's own established procedure (branch in `~/repos/agentflow`, tests, version bump in both
    `pyproject.toml` and `src/agentflow/__init__.py`, changelog entry, tag-triggered PyPI release,
    then bump the pin in `services/python-daemon/requirements.txt`) — not by JSON-encoding
    structured payloads into strings or string-matching `"Tool error:"` downstream in this daemon.
    The concrete shape of the AgentFlow-side change (a new structured-result type on
    `ToolDispatcher`'s protocol; likely additive, not breaking, since existing string-returning
    tools are still valid strings) is implementation-context work, not invented here.
*   **Confirmation-gating policy — the actual job of this spec, and a real candidate for an
    AgentFlow-level primitive rather than daemon-only logic.** Of every route in `daemon.py`'s
    `ROUTES`, exactly one mutates a live, already-open board: `kicad.inject_component`. Everything
    else (`freecad.generate_enclosure`, `kicad.generate_component`, `component.search`, `llm.chat`,
    and all `project.*`/`library.*` local-storage routes) reads, or writes only to this app's own
    local storage, never to a document the user has open elsewhere. The gating rule this app needs:
    **a tool registered as requiring confirmation never executes on its first model-proposed call**
    — it returns a pending-approval result instead of dispatching, and only a second, explicit
    "confirmed" call actually runs the real handler. "Ask before running a destructive tool" is not
    specific to this app's board-write case — any AgentFlow consumer wiring an LLM to a tool that
    has real-world side effects needs the same two-phase shape. The implementation-context work
    should evaluate adding this as a first-class `ToolRegistry`/`LocalToolDispatcher` primitive
    upstream (e.g. a `requires_confirmation` flag at registration time, with the generic
    pending/confirm protocol implemented once in AgentFlow) before defaulting to a bespoke
    `pending_confirmation` shape hand-rolled only in this daemon.
*   **Data Flow / Interactions:** model requests a tool call → registry dispatch → if the tool
    requires confirmation, short-circuit to a pending-approval result without calling the real
    handler → UI renders the proposed call and awaits user approval → UI's approval re-invokes the
    same tool as confirmed, which now calls through to the real handler. The exact payload shape
    (an AgentFlow-level primitive vs. a daemon-only convention, per the open question above) needs a
    real sequence diagram once that's decided — left as an open question below rather than invented
    here.
*   **Cross-Module Impacts:**
    *   `~/repos/agentflow` (`gittielabs-agentflow`): the structured-result and confirmation-gating
        primitives above, added upstream first, following [[agentflow-fix-upstream]]'s release
        procedure — real, in-scope work for this spec, not a dependency this spec merely consumes
        as fixed.
    *   `services/python-daemon`: a new adapter module registering `ToolRegistry`/
        `LocalToolDispatcher` tools that wrap a subset of `daemon.py`'s existing `ROUTES` handlers,
        built against the upgraded AgentFlow pin; no change to the handlers' own business logic.
    *   `apps/tauri-ui`: consumes the new pending-confirmation result shape once `SPEC-302`'s
        surface (or its `PRODUCT-PLAN.md`-scoped successor) is updated to render it — that UI work
        is explicitly out of this spec's scope, but the shape this spec emits is a real contract
        that surface will depend on.
    *   Upstream: `SPEC-102` (the `ROUTES` dict being wrapped), `SPEC-201` (AgentFlow already a real
        dependency; this is the first spec in the repo to actually use its tool-calling machinery
        rather than only its provider abstraction).

## 3. Known Constraints & Risks
*   **Two real gaps in `gittielabs-agentflow==0.8.2`, confirmed from its own source, both slated for
    an upstream fix rather than a downstream workaround** (see §2, [[agentflow-fix-upstream]]):
    `LocalToolDispatcher` handlers return plain strings only, with no structured-result path; and
    `LocalToolDispatcher.dispatch` swallows handler exceptions into `"Tool error: {exc}"` strings
    instead of raising or returning a distinguishable failure. Implementation must not default to
    JSON-encoding payloads into strings or string-matching `"Tool error:"` as the permanent design —
    that's the exact pattern this repo's own norms rule out for a library Keith owns outright. A
    downstream shim is only acceptable as a short-lived stopgap while the AgentFlow-side PR is in
    flight, and must be removed once the upgraded pin lands.
*   **This spec's confirmation-gating need may be generically useful enough to belong in AgentFlow
    itself**, not just this daemon — real design work for the implementation context to resolve
    before defaulting to a daemon-only convention (see §2).
*   **Every existing `ROUTES` handler already assumes single-threaded, synchronous dispatch**
    (`SPEC-102`'s own known constraint). Wrapping them in `async def` tool handlers for
    `LocalToolDispatcher` must not silently invite concurrent dispatch the daemon was never designed
    for — the wrapper is a signature adapter, not a concurrency change.
*   **Open question, not yet resolved:** the exact pending-confirmation → user-approval →
    re-dispatch round trip shape (a second tool call with the same input plus a flag, a distinct
    `tool.confirm` route, an AgentFlow-level primitive per §2, or something `SPEC-105`'s job-progress
    protocol already has a shape for?) needs a decision before implementation, not invented here per
    this repo's own scaffolding norm.

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

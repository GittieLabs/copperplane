---
id: SPEC-204
title: "Agent Tool Registry"
status: Completed
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
    (`SPEC-102`) with AgentFlow's real `ToolRegistry` (already an installed dependency since
    `SPEC-201`, currently used only for raw provider chat completions — its tool-calling machinery
    is entirely unused today), registering tools via its `add_tool()` inline path rather than
    `LocalToolDispatcher` (see §2/§3 for why), and define the confirmation-gating policy
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
    *   **Not an AgentFlow change.** An earlier draft of this spec planned upstream AgentFlow work
        for two apparent gaps; both turned out, on real verification (see §2), to already be solved
        by the library's existing API surface via a different registration/ContextVar choice. This
        spec's own real work is entirely inside `services/python-daemon`. The general rule that
        AgentFlow is Keith's own library and fair game to change when a *real* gap is found still
        stands — it just doesn't apply here.

## 2. System Architecture & Design Choices
*   **Corrected 2026-08-14, by running real code against the installed library, not just reading
    signatures: neither AgentFlow gap this section originally claimed actually exists.** An earlier
    draft of this spec asserted `LocalToolDispatcher` had no structured-result path and swallowed
    exceptions in a way no other AgentFlow API avoided, and planned to fix both upstream. Two real
    scripts run against `gittielabs-agentflow==0.8.2` (not the installed daemon — the library
    itself) disproved both:
    1.  **Structured results already work.** `agentflow.tools.http_dispatcher.last_raw_tool_result`
        is a real, already-wired `ContextVar[dict | None]` — a handler sets a real dict on it before
        returning its string, and `AgentExecutor` (`agent/runtime.py`) already reads it back into
        the `TOOL_RESULT` event's `raw_result` field, consumable via `EventBus.on(TOOL_RESULT, ...)`.
        Verified directly: a handler set `{'schema': {'pins': 8}, 'confidence': 0.9}` on the
        ContextVar and it came back out through the dispatch call intact.
    2.  **Exception propagation already works too — via a different, also-existing registration
        path.** `ToolRegistry.add_tool()` (inline registration) has no exception handling of its own
        and lets a handler's exception propagate straight through `ToolRegistry.dispatch()` to
        `AgentExecutor`, which correctly sets `is_error: true` and emits an `ERROR` event.
        `LocalToolDispatcher.register()` is the one path that swallows exceptions into
        `"Tool error: {exc}"` strings — that behavior is real, but it's an artifact of choosing that
        registration path, not a library-wide gap. Verified directly: the same failing handler
        registered inline propagated its real `ValueError`; registered via `LocalToolDispatcher` it
        was swallowed into a string, exactly as originally observed.
    **No AgentFlow code change is needed for either.** This app's own registration choice —
    `ToolRegistry.add_tool()` for every route this spec registers, plus setting
    `last_raw_tool_result` in handlers that have a structured payload worth surfacing — gets both
    properties for free from the already-released library.
*   **Confirmation-gating policy — the actual job of this spec, and genuinely daemon-side, not an
    AgentFlow primitive.** Of every route in `daemon.py`'s `ROUTES`, exactly one mutates a live,
    already-open board: `kicad.inject_component`. Everything else (`freecad.generate_enclosure`,
    `kicad.generate_component`, `component.search`, `llm.chat`, and all `project.*`/`library.*`
    local-storage routes) reads, or writes only to this app's own local storage, never to a document
    the user has open elsewhere. The gating rule: **the inline handler wrapping
    `kicad.inject_component` checks its own `tool_input` for a `confirmed` flag** — absent or false,
    it returns a pending-approval string (and, via `last_raw_tool_result`, a structured
    `{"status": "pending_confirmation", ...}` payload) without calling the real `ROUTES` handler;
    only `confirmed: true` calls through. This needs no interception point in `ToolRegistry` itself
    — it's ordinary control flow inside one handler function, decided in this app because nothing
    about it is generic enough across AgentFlow's other real consumers to justify a library-level
    primitive (unlike the two items above, which really were library gaps once verified as real).
*   **Data Flow / Interactions:** model requests a tool call → `ToolRegistry.dispatch(name, input)`
    (inline handler) → if `name == "kicad.inject_component"` and `input.get("confirmed")` is not
    true, return a pending-approval result → UI renders the proposed call and awaits user approval →
    UI's approval re-invokes the same tool with `confirmed: true`, which now calls through to the
    real `ROUTES["kicad.inject_component"]` handler.
*   **Cross-Module Impacts:**
    *   `services/python-daemon`: a new module registering `ToolRegistry.add_tool()` tools that wrap
        a subset of `daemon.py`'s existing `ROUTES` handlers; no change to the handlers' own business
        logic, and no AgentFlow version bump required.
    *   `apps/tauri-ui`: consumes the new pending-confirmation result shape once `SPEC-302`'s
        surface (or its `PRODUCT-PLAN.md`-scoped successor) is updated to render it — that UI work
        is explicitly out of this spec's scope, but the shape this spec emits is a real contract
        that surface will depend on.
    *   Upstream: `SPEC-102` (the `ROUTES` dict being wrapped), `SPEC-201` (AgentFlow already a real
        dependency; this is the first spec in the repo to actually use its tool-calling machinery
        rather than only its provider abstraction).

## 3. Known Constraints & Risks
*   **Use `ToolRegistry.add_tool()`, not `LocalToolDispatcher.register()`, for every tool this spec
    registers.** The two behave differently in `gittielabs-agentflow==0.8.2` — verified directly,
    not assumed (see §2): `add_tool`'s inline handlers propagate real exceptions up to
    `AgentExecutor`'s own `is_error`/`ERROR`-event handling, while `LocalToolDispatcher` swallows
    them into `"Tool error: {exc}"` strings. Reaching for `LocalToolDispatcher` here — the more
    obviously-named class for "local tools" — would silently reintroduce the exact failure-signaling
    gap this spec originally (and wrongly) thought was a library-wide limitation.
*   **Every existing `ROUTES` handler already assumes single-threaded, synchronous dispatch**
    (`SPEC-102`'s own known constraint). Wrapping them in `async def` tool handlers must not silently
    invite concurrent dispatch the daemon was never designed for — the wrapper is a signature
    adapter, not a concurrency change.
*   **Resolved 2026-08-14:** the pending-confirmation round trip is a `confirmed` flag on
    `kicad.inject_component`'s own `tool_input`, checked inside its inline handler (see §2) — not an
    AgentFlow primitive, not a distinct route. Implementation should still confirm this composes
    cleanly with `SPEC-105`'s job-progress protocol for surfacing the pending state to the UI, since
    that part is genuinely open.

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

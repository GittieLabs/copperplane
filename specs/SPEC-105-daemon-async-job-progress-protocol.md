---
id: SPEC-105
title: "Daemon Async Job & Progress Protocol"
status: Draft
type: Feature
created: 2026-08-08
last_updated: 2026-08-08
target_version: v0.1.0
location: "specs/SPEC-105-daemon-async-job-progress-protocol.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs: []
---

# SPEC-105: Daemon Async Job & Progress Protocol

## 1. Executive Summary & Goals
*   **High-Level Goal:** Give the daemon a way to run a long operation (a multi-second `freecadcmd`
    cold boot, a 30-second LLM call) without freezing the UI or breaking the JSON-RPC `stdin`/`stdout`
    contract. Concretely: a job-submission response returned immediately (`{"job_id": ...}`),
    JSON-RPC *notifications* for progress and streamed tokens, and cancellation — all without
    threatening the "one response per line, `stdout` is sacred" invariant `CLAUDE.md` and SPEC-000
    both depend on.
*   **Business / Technical Value:** Today the daemon is strictly serial and the frontend enforces a
    hard single-in-flight guard (CTX-101.1) — any slow call locks the entire app with zero feedback.
    That's tolerable for a `kicad.get_version` round-trip; it's not tolerable for the AI-driven
    flows SPEC-201/202/204 are about to add, several of which are inherently multi-second. This spec
    is the platform primitive everything past it needs: SPEC-108, SPEC-109, SPEC-201, and
    SPEC-301/302 all list it as a dependency.
*   **Non-Goals:**
    *   Not building the actual AI pipeline that would emit progress (SPEC-201/202/204) — this spec
        defines the transport those layers will use, not their content.
    *   Not deciding how AgentFlow's `EventBus` events (`NODE_STARTED`, `LLM_CALL_STARTED`, etc.)
        map onto this protocol's notifications. That translation is real work, but it's this spec's
        own call to make once AgentFlow is actually wired in (SPEC-201+), not a decision to pre-make
        here against a system that isn't integrated yet.
    *   Not the frontend's job-tracking UI itself (progress bars, cancel buttons) — that's
        `CTX-105.2`'s frontend slice; this spec covers the wire protocol and daemon-side execution
        model both slices share.
    *   Not a general job *queue* with prioritization/scheduling — one job at a time per client
        session is the assumed model unless a real need for concurrent jobs shows up.

## 2. System Architecture & Design Choices
*   **Design Rationale:**
    *   **Job submission returns immediately.** A request for a long-running method (e.g.
        `freecad.generate_enclosure`) responds right away with `{"job_id": "<uuid>"}` instead of
        blocking the read loop until the work finishes. The actual result arrives later as a
        notification keyed by that `job_id`.
    *   **Progress and completion travel as JSON-RPC notifications** (no `id` field, per the JSON-RPC
        2.0 spec) — `stdout` stays a stream of independently-parseable, one-per-line JSON objects
        whether they're request responses or job events. No new framing format.
    *   **Work happens off the read loop, `stdout` writes stay atomic per line.** Whatever
        concurrency primitive is chosen (a worker thread pool, `asyncio` tasks, subprocess
        supervision) must serialize writes to `stdout` — two workers mid-write on the same line
        corrupts the frame for every consumer. This is the hard constraint the design must satisfy,
        not a detail to leave to the implementation.
    *   **Per-route parameter validation rides along.** Today `ROUTES[method](**params)` turns a
        typo'd parameter into a `TypeError` reported as an opaque `-32000`. This spec is the natural
        place to add real parameter-shape validation ahead of dispatch, returning the JSON-RPC
        standard `-32602 Invalid params` instead.
*   **Data Flow / Interactions:**

    ```text
    Frontend                Rust Supervisor           Python Daemon
       │  submit long job         │                        │
       │─────────────────────────>│──── stdin (request) ──>│
       │                          │                        │  dispatch to worker,
       │                          │                        │  return job_id immediately
       │<──────────────────────── │<── stdout (response,───│  {"result": {"job_id": "..."}}
       │  render "in progress"    │     id matches request)│
       │                          │                        │
       │                          │                        │  worker runs off the
       │                          │                        │  read loop; writes
       │                          │                        │  progress atomically
       │<──────────────────────── │<── stdout (notif, ─────│  {"method": "job.progress",
       │  update progress UI      │     no id) ────────────│   "params": {"job_id":...}}
       │                          │                        │
       │<──────────────────────── │<── stdout (notif) ─────│  {"method": "job.completed", ...}
       │  render final result     │                        │
    ```

*   **Cross-Module Impacts:**
    *   `services/python-daemon`: new worker-dispatch model for methods flagged as async; a
        notification-emitting helper that serializes `stdout` writes; the parameter-validation layer.
    *   `core/tauri-rust`: the daemon's `stdout` reader must forward *both* responses and
        notifications to the frontend, not just request/response pairs — likely a change to how
        `dispatch_to_daemon`'s event emission is keyed (by `id` for responses, by `method` for
        notifications).
    *   `apps/tauri-ui`: replaces CTX-101.1's hard single-in-flight guard with per-job state tracking
        (deferred to `CTX-105.2`).
    *   No impact on `kicad_bridge.py`/`freecad_bridge.py`'s internals — this wraps *how* their
        existing calls are dispatched and reported, not what they do.

## 3. Known Constraints & Risks
*   **Known Issues / Technical Debt:**
    *   The existing single-in-flight guard (CTX-101.1) is a real, working safety net against
        overlapping requests corrupting daemon state. Whatever replaces it needs to preserve that
        guarantee per-job, not just remove the guard and hope.
*   **Gotchas & Hazards:**
    *   **`stdout` write atomicity is the whole risk surface.** Any concurrency model that lets two
        workers interleave partial writes to the same stream corrupts every frame downstream, not
        just the offending job's. This needs direct test coverage under real concurrent load, not
        just a single-worker happy path.
    *   **Don't invent a second event system.** AgentFlow's `EventBus` already emits the event
        vocabulary (`NODE_STARTED`/`COMPLETED`, `LLM_CALL_STARTED`/`COMPLETED`, `TOOL_CALLED`/
        `RESULT`, `ERROR`) this protocol's notifications will eventually carry, once SPEC-201/202/204
        land. Building a parallel progress-event taxonomy now risks a rename/migration later.
    *   **Cancellation semantics need to be real, not decorative.** A cancel request that doesn't
        actually stop the underlying `freecadcmd` subprocess or LLM call (only stops *reporting* on
        it) is worse than no cancellation — the user believes it stopped while it's still running.
    *   **Job lifecycle after a daemon restart is undefined until this spec defines it.** If the
        daemon crashes mid-job, does the frontend's job state ever resolve, or hang forever? Needs an
        explicit answer (e.g. a "daemon restarted" notification that fails all outstanding jobs).

## 4. Module Map & Reference Links

*   [ROADMAP.md](../ROADMAP.md) §3.1 — the gap this spec closes, and the two likely context slices
    (`CTX-105.1` job protocol + daemon worker, `CTX-105.2` frontend job/progress client).
*   [SPEC-101](../apps/tauri-ui/specs/SPEC-101-ui-ipc-bridge.md) — the single-in-flight guard this
    spec's frontend slice replaces.
*   [SPEC-102](../services/python-daemon/specs/SPEC-102-daemon-rpc-router.md) — the JSON-RPC
    read loop and `ROUTES` registry this spec extends with async dispatch and param validation.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-105] Daemon Async Job & Progress Protocol
          ├── [Context 105.1] (not yet written) — job protocol + daemon worker
          └── [Context 105.2] (not yet written) — frontend job/progress client
```

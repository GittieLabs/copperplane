---
id: SPEC-107
title: "Structured Logging, Startup Handshake & Diagnostics"
status: Draft
type: Feature
created: 2026-08-09
last_updated: 2026-08-09
target_version: v0.1.0
location: "specs/SPEC-107-structured-logging-diagnostics.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs: []
user_facing: false
---

# SPEC-107: Structured Logging, Startup Handshake & Diagnostics

## 1. Executive Summary & Goals

*   **High-Level Goal:** Give every daemon failure a path to reach a human. Today, if `import kipy`
    fails, `daemon.py` dies before its read loop starts, Rust sees a child that exited instantly, and
    the UI simply never responds — there is no error, no log, nothing. This spec defines `stderr` as
    the log channel (never `stdout`, which is reserved for JSON-RPC frames), a rotating log file, a
    `daemon.ready` startup handshake reporting detected capabilities (KiCad present? FreeCAD present?
    which LLM providers reachable?), and the Python-side heartbeat `SPEC-101` called for but deferred
    (`CTX-101.1` Deviation 1) — the piece still missing from macOS's crash coverage.
*   **Business / Technical Value:** Every other spec's error handling assumes a human eventually
    sees *something* when things go wrong. Right now that assumption is false for the single most
    common failure mode (a missing/broken dependency at daemon startup) and for macOS's only-partial
    "No Dangling Processes" claim (`ROADMAP.md` §1.2). This spec is infrastructure every other spec
    quietly depends on being right.
*   **Non-Goals:**
    *   Not a UI diagnostics panel — `SPEC-303`'s Settings UI is where a human actually *sees*
        "is KiCad reachable, is FreeCAD reachable, is the daemon healthy." This spec defines the
        `daemon.ready` handshake and the log file that panel will read from; it doesn't build the
        panel itself.
    *   Not log *aggregation*, remote log shipping, or telemetry. A local rotating file a human (or
        this spec's own future diagnostics panel) can open is the entire scope.
    *   Not retrying a failed capability detection. `daemon.ready` reports what's true *at startup*;
        if KiCad launches five minutes later, that's `SPEC-103`'s existing lazy-connect behavior, not
        a re-detection this spec needs to trigger.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **`stderr` is the log channel, unconditionally.** `CLAUDE.md`'s "stdout is sacred" norm
        already forbids `print()`; this spec makes that enforceable rather than just stated —
        Python's `logging` module configured to write to `stderr` (inherited by Rust today per
        `daemon.rs`'s `Stdio::inherit()`) plus a rotating file handler under the app's own data
        directory. Any import-time exception before the read loop starts must still reach the log
        file — logging setup happens as literally the first thing `daemon.py` does, before any
        bridge module import that could fail.
    *   **`daemon.ready` is a notification, not a response — reusing `SPEC-105`'s wire protocol.**
        Once the read loop is genuinely ready (all imports succeeded, capability probes ran), the
        daemon emits one `daemon.ready` notification (no `id`, same shape as a `job.*` notification)
        reporting `{"kicad_available": bool, "freecad_available": bool, "llm_providers": [...]}`.
        Rust's `stdout` reader already forwards every line verbatim — no transport change needed,
        matching `SPEC-101`'s own non-goal of never parsing payload contents.
    *   **Startup failure gets a path too, not just startup success.** If an import fails before
        logging is even configured, that's a genuine "nothing can be done" case — but once logging
        is set up (step one), every subsequent failure through capability detection gets caught and
        logged, and the daemon still emits `daemon.ready` with the failed capability marked
        unavailable rather than crashing outright. A daemon that can't reach KiCad should still serve
        FreeCAD requests.
    *   **The macOS heartbeat closes `CTX-101.1`'s Deviation 1.** The daemon emits a periodic
        `daemon.heartbeat` notification (a Python-side timer, independent of the request read loop
        so a `freecadcmd` subprocess call in flight doesn't block it). Rust's macOS `RunEvent::Exit`
        path only catches a graceful quit; pairing it with "no heartbeat for N seconds" gives Rust an
        actual signal a hard-crashed (not just gracefully-exited) daemon needs cleanup, closing the
        one platform where `ROADMAP.md` §1.2 says "No Dangling Processes" is still only partially
        true.
*   **Data Flow / Interactions:**

    ```text
    daemon.py starts
       │
       ▼
    Configure logging to stderr + rotating file (step one, before any
    other import that could fail)
       │
       ▼
    Import kicad_bridge, freecad_bridge (each failure logged, not fatal
    to the whole daemon -- captured as "capability unavailable")
       │
       ▼
    Probe capabilities: is KiCad's IPC socket reachable? is freecadcmd
    found? (cheap checks, not full connections -- SPEC-103/104 already
    connect lazily on first real use)
       │
       ▼
    Emit "daemon.ready" notification with detected capabilities
       │
       ▼
    Enter the normal stdin read loop (SPEC-102), plus a background timer
    thread emitting "daemon.heartbeat" every N seconds
       │
       ▼
    Rust: on macOS, if no heartbeat arrives for >N*2 seconds, treat the
    daemon as hard-crashed and run the same cleanup RunEvent::Exit would
    have -- the missing half of CTX-101.1's crash shield
    ```

*   **Cross-Module Impacts:**
    *   `services/python-daemon`: logging configuration at the top of `daemon.py`; a capability-probe
        step before the read loop starts; a background heartbeat timer thread (must not corrupt
        `stdout` — reuses `SPEC-105`'s `emit()`/atomic-write path, not a new one).
    *   `core/tauri-rust`: the daemon's `stdout` reader already forwards every line; new logic
        specifically on macOS to track the last-seen heartbeat timestamp and treat a stale one as a
        crash signal, invoking the same cleanup path `DaemonHandle::shutdown` already provides.
    *   No wire-format change — `daemon.ready`/`daemon.heartbeat` are ordinary notifications through
        the protocol `SPEC-105` already established.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   None yet — this closes a real, previously-unowned gap (`ROADMAP.md`'s risk register: "macOS
        crash shield never gets its heartbeat... needs a home in SPEC-107's handshake work") rather
        than fixing existing broken behavior.
*   **Gotchas & Hazards:**
    *   **Logging setup itself must never write to `stdout`.** Getting this wrong would be exactly
        the bug this spec exists to prevent, just introduced by the fix instead of by a stray
        library `print()`.
    *   **The heartbeat timer must not be blocked by in-flight work.** If it's just a `time.sleep`
        loop on the same thread as anything else, a long `freecadcmd` call would starve it and
        produce a false "crashed" signal. It needs its own thread, independent of request handling.
    *   **Capability probes must be cheap and non-blocking.** `SPEC-103`/`104` already establish
        that KiCad/FreeCAD connect lazily; a `daemon.ready` probe that itself does a slow handshake
        would delay every startup by however long that handshake takes, on every launch, even when
        nothing ever uses that bridge.
    *   **A false-positive "crashed" heartbeat signal on Windows/Linux (not just macOS) would be
        worse than no heartbeat at all** — those platforms already have working OS-level crash
        shields (`prctl`/Job Objects); layering a heartbeat-based cleanup on top there risks double
        -triggering cleanup or racing the OS-level shield. The heartbeat-driven cleanup path is
        macOS-only by design, not an oversight.

## 4. Module Map & Reference Links

*   [ROADMAP.md](../ROADMAP.md) §1.2, §3.1, §6 — the README-vs-reality gap this closes, and the risk
    register entry naming this spec as the heartbeat's home.
*   [CTX-101.1](../apps/tauri-ui/context/CTX-101.1-ui-ipc-bridge.md) Deviation 1 — the deferred
    Python-side heartbeat this spec finally implements.
*   [SPEC-105](specs/SPEC-105-daemon-async-job-progress-protocol.md) — the notification wire format
    (`emit()`, atomic `stdout` writes) `daemon.ready`/`daemon.heartbeat` reuse rather than duplicate.
*   [SPEC-303](#) (not yet written) — the Settings/diagnostics UI that will eventually surface what
    `daemon.ready` reports to a human.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-107] Structured Logging, Startup Handshake & Diagnostics
          └── [Context 107.1] (not yet written)
```

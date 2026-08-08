---
id: SPEC-102
title: "Python JSON-RPC Daemon & Route Registry"
status: Approved
type: Module
created: 2026-08-07
last_updated: 2026-08-07
target_version: v0.1.0
location: "services/python-daemon/specs/SPEC-102-daemon-rpc-router.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs:
  - "SPEC-103-kicad-ipc.md"
  - "SPEC-104-freecad-headless.md"
---

# SPEC-102: Python JSON-RPC Daemon & Route Registry

> **Retroactive spec.** SPEC-000 and SPEC-101 both linked to this document from day one, but it
> was never written — `CTX-102.1` was implemented against SPEC-000 directly. This spec documents
> the daemon **as built** (commit `421361f`) and records the constraints that the routes hanging
> off it (SPEC-103, SPEC-104, and everything in the 2xx intelligence layer) must respect.

## 1. Executive Summary & Goals

*   **High-Level Goal:** Provide the single long-lived Python process that receives JSON-RPC 2.0
    requests from the Rust supervisor over `stdin`, dispatches them to a registry of route
    handlers, and writes responses back over `stdout`. It is the spine every CAD and AI capability
    plugs into.
*   **Business / Technical Value:** Heavy Python imports (`kipy`, `trimesh`, and later LLM
    clients) are paid once at process start rather than per command. The route registry gives every
    subsequent module — KiCad, FreeCAD, supplier APIs, the LLM layer — one uniform way to expose
    itself to the UI without touching Rust or the transport.
*   **Non-Goals:** The daemon does not own CAD or AI logic itself; each capability lives in its own
    module (`kicad_bridge.py`, `freecad_bridge.py`, ...) and is only *registered* here. The daemon
    does not open sockets, and it does not manage its own lifecycle — the Rust supervisor
    (SPEC-101) spawns it and guarantees its death.

## 2. System Architecture & Design Choices

### Transport contract with Rust (SPEC-101)
*   **Framing is newline-delimited JSON.** One request per line in, one response per line out.
    Rust writes exactly one `\n` per request; the daemon iterates `for line in sys.stdin`.
*   **`stdout` is a reserved channel.** It carries JSON-RPC frames and nothing else. Any `print()`
    or library banner written to `stdout` corrupts the stream and will be silently dropped by the
    frontend's `JSON.parse` guard, producing a request that hangs forever. **All logging,
    warnings, and tracebacks go to `stderr`** (formalised in SPEC-107).
*   **`sys.stdout.flush()` after every write** is mandatory — without it Python's block buffering
    holds responses until the buffer fills, which reads as a frozen UI.
*   Rust treats payloads as opaque strings and does not parse them (SPEC-101 §1, Non-Goals).

### Route registry
*   `ROUTES: dict[str, Callable]` maps a dotted method name to a Python callable.
*   Namespacing convention: `<subsystem>.<verb_noun>` — e.g. `kicad.get_version`,
    `freecad.generate_enclosure`. New subsystems claim a new prefix.
*   Dispatch unpacks `params` as keyword arguments (`ROUTES[method](**params)`) when `params` is an
    object, and calls with no arguments otherwise.

### Error mapping
| Condition | JSON-RPC code | Notes |
| :--- | :--- | :--- |
| Body is not valid JSON | `-32700` Parse error | `id` is `null`; the frontend drops unmatched ids |
| `method` key absent | `-32600` Invalid Request | |
| `method` not in `ROUTES` | `-32601` Method not found | |
| Handler raised any exception | `-32000` Server error | Message is `str(e)` |

A handler raising is never fatal: the loop catches, responds, and keeps listening. This is the
property SPEC-103's "State Desync" and SPEC-104's timeout handling both depend on.

## 3. Known Constraints & Risks

*   **Single-threaded, strictly serial.** The daemon processes one line to completion before
    reading the next. A 3-second `freecadcmd` cold boot or a 30-second LLM call blocks every other
    request behind it. The frontend compensates today with a hard single-in-flight guard
    (`ipc.ts`), which means the UI is fully blocked for the duration. **This is the single largest
    architectural constraint on the product** and is the subject of SPEC-105 (async job & progress
    protocol).
*   **No progress or partial output.** The one-request/one-response shape has no room for streaming
    tokens or percentage updates. Also addressed by SPEC-105.
*   **Unvalidated kwargs.** `ROUTES[method](**params)` passes caller-supplied keys straight into
    handler signatures. A misspelled key raises `TypeError` and surfaces as an opaque
    `-32000 Server error` rather than a useful `-32602 Invalid params`. Not a security boundary
    today (the only caller is the local Rust supervisor), but it makes handler contracts
    undiscoverable. Introducing per-route parameter models is tracked in the SPEC-105 work.
*   **Import-time failure is unrecoverable and silent.** `daemon.py` imports every bridge module at
    the top level, so a missing dependency kills the process before the read loop starts. Rust sees
    a child that exited immediately; there is no structured error for the UI to show. A startup
    handshake (`daemon.ready` / capability report) is required — SPEC-107.
*   **`time.sleep(1.5)` mock still in the registry.** `kicad.generate_component` returns fabricated
    filenames and is wired to the primary UI button. It must not survive into any build shown
    outside the dev machine; SPEC-202 replaces it with the real pipeline.

## 4. Module Map & Reference Links

*   [Root Architecture: SPEC-000](../../../specs/SPEC-000-architecture-overview.md)
*   [Tauri UI & Rust Process Supervisor: SPEC-101](../../../apps/tauri-ui/specs/SPEC-101-ui-ipc-bridge.md)
*   [KiCad IPC Bridge: SPEC-103](SPEC-103-kicad-ipc.md)
*   [FreeCAD Headless Bridge: SPEC-104](SPEC-104-freecad-headless.md)
*   [Implementation Context: CTX-102.1](../context/CTX-102.1-json-rpc-daemon.md)
*   [Project roadmap](../../../ROADMAP.md)

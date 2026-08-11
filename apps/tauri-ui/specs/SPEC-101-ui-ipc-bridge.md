---
id: SPEC-101
title: "Tauri UI & Rust Process Supervisor"
status: Draft
type: Module
created: 2026-08-07
last_updated: 2026-08-07
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-101-ui-ipc-bridge.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
user_facing: false
---

# SPEC-101: Tauri UI & Rust Process Supervisor

## 1. Executive Summary & Goals
*   **High-Level Goal:** Manage the frontend UI rendering (React/TypeScript) and the OS-level lifecycle of the Python sidecar (Rust).
*   **Business / Technical Value:** Provides a snappy, native-feeling desktop experience. The Rust core acts as a safety supervisor, ensuring that the Python daemon is spawned securely and terminated forcefully if the UI crashes, preventing memory leaks and locked TCP ports.
*   **Non-Goals:** Rust will not parse or validate the JSON-RPC payload contents; it acts strictly as a raw string transport layer between React and Python.

## 2. System Architecture & Design Choices
*   **Frontend (React/Three.js):** Maintains application state. Dispatches stringified JSON-RPC requests via Tauri's `invoke` API. Renders returned 3D `.glb` meshes via React Three Fiber.
*   **Rust Transport Layer:** 
    *   Exposes a single `#[tauri::command]` called `dispatch_to_daemon`.
    *   Holds an `Arc<Mutex<ChildStdin>>` to allow async writing to the Python process.
*   **Process Supervisor (The "Crash Shield"):**
    *   **Windows:** Rust binds the Python `Child` process to a Windows Job Object configured with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
    *   **Linux:** Rust uses `libc::prctl(PR_SET_PDEATHSIG, SIGKILL)` before execution.
    *   **macOS:** Tauri's `RunEvent::Exit` lifecycle hook combined with a Python-side heartbeat ping.

## 3. Known Constraints & Risks
*   **Concurrency Constraints:** React must handle long-running generations asynchronously. A loading state must prevent the user from spamming the `stdin` buffer with conflicting commands.
*   **Security Hazard:** Never execute raw `eval()` on data returned from standard output. Always parse via `JSON.parse()`.

## 4. Module Map & Reference Links
*   [Root Architecture: SPEC-000](../../../specs/SPEC-000-architecture-overview.md)
*   [Python Daemon: SPEC-102](../../../services/python-daemon/specs/SPEC-102-daemon-rpc-router.md)
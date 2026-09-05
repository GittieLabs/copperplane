---
id: SPEC-000
title: "Root Architecture: Copperplane"
status: Approved
type: System
created: 2026-08-07
last_updated: 2026-08-07
target_version: v0.1.0
location: "specs/SPEC-000-architecture-overview.md"
parent_spec: null
child_specs:
  - "../apps/tauri-ui/specs/SPEC-101-ui-ipc-bridge.md"
  - "../services/python-daemon/specs/SPEC-102-daemon-rpc-router.md"
  - "../services/python-daemon/specs/SPEC-103-kicad-ipc.md"
  - "../services/python-daemon/specs/SPEC-104-freecad-headless.md"
  - "../specs/SPEC-105-daemon-async-job-progress-protocol.md"
  - "../specs/SPEC-106-configuration-secrets-store.md"
  - "../specs/SPEC-107-structured-logging-diagnostics.md"
  - "../apps/tauri-ui/specs/SPEC-301-3d-viewer.md"
  - "../services/python-daemon/specs/SPEC-201-llm-provider-abstraction.md"
  - "../services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md"
  - "../services/python-daemon/specs/SPEC-108-kicad-write-path-footprint-symbol-injection.md"
  - "../apps/tauri-ui/specs/SPEC-302-chat-command-surface.md"
  - "../apps/tauri-ui/specs/SPEC-300-product-ia-interaction-model.md"
  - "../apps/tauri-ui/specs/SPEC-303-settings-ui.md"
  - "../specs/SPEC-110-configurable-storage-root.md"
  - "../services/python-daemon/specs/SPEC-109-parametric-enclosure-generator.md"
  - "../specs/SPEC-401-python-sidecar-packaging.md"
  - "../services/python-daemon/specs/SPEC-204-agent-tool-registry.md"
  - "../services/python-daemon/specs/SPEC-203-supplier-api-integration.md"
  - "../specs/SPEC-403-cross-platform-verification.md"
  - "../specs/SPEC-402-release-signing-and-auto-update.md"
  - "../services/python-daemon/specs/SPEC-205-datasheet-design-guidance.md"
  - "../specs/SPEC-404-managed-hosted-access.md"
  - "../specs/SPEC-405-product-rename-copperplane.md"
  - "SPEC-408-messaging-for-the-maker-who-is-leveling-up.md"
user_facing: false
---

# SPEC-000: Root Architecture: Copperplane

## 1. Executive Summary & Goals
*   **High-Level Goal:** Build a unified, local-first AI assistant that bridges the gap between PCB design (KiCad) and Mechanical CAD (FreeCAD). The application acts as a master orchestrator, manipulating active CAD canvases via background processes and IPC APIs.
*   **Business / Technical Value:** Hardware engineers currently waste hours context-switching, manually copying dimensions, and parsing datasheets. By wrapping an extensible Python AI backend in a lightweight, cross-platform Tauri UI, we can automate component generation, schematic routing, and 3D enclosure generation without writing rigid native C++ plugins for each tool.
*   **Non-Goals:** We are *not* replacing the KiCad or FreeCAD GUIs. We are *not* building a web-based CAD tool. We are *not* using the MCP (Model Context Protocol) standard, as we require custom binary streaming (e.g., `.glb` meshes) and bespoke UI rendering that MCP does not optimally support.

## 2. System Architecture & Design Choices

The application uses a three-tier architecture to separate the UI, the AI/Logic, and the underlying CAD engines.

### Design Rationale: The JSON-RPC `stdin/stdout` Sidecar
Instead of running a local HTTP server (FastAPI) which risks leaving dangling TCP ports and zombie processes on crash, the Python logic runs as a direct child CLI process of the Tauri app. 
*   **Transport:** Tauri streams JSON strings to Python via `stdin`. Python responds via `stdout` and flushes the buffer.
*   **Format:** Standardized JSON-RPC 2.0.
*   **Performance:** Python's heavy AI libraries are loaded *once* at startup. The process stays alive in a listening loop, reducing per-command latency to sub-milliseconds.

### System Data Flow
1. **Frontend (Tauri/React):** User types "Generate a footprint for BME280". React sends a command to Rust.
2. **Supervisor (Tauri/Rust):** Rust formats a JSON-RPC payload and writes it to the Python daemon's `stdin`.
3. **Logic (Python Daemon):** Python reads the JSON, calls out to a Supplier API (e.g., Octopart) to get pinouts, and uses an AI model to structure the data.
4. **Execution (KiCad/FreeCAD):** 
    * *For KiCad:* Python uses the `kicad-python` protobuf socket to inject the generated `.kicad_mod` directly into the open KiCad canvas.
    * *For FreeCAD:* Python sends dimensions to a headless FreeCAD process to parametrically render a `.glb` mesh, exporting it to a temp folder.
5. **Response:** Python writes the success status and file paths to `stdout`. Tauri reads it and updates the React UI (loading the `.glb` into Three.js).

## 3. Known Constraints & Risks

*   **Dangling Process Hazards:** If the Tauri UI crashes, the OS might leave the Python daemon and headless FreeCAD running in the background. 
    *   *Mitigation:* The Rust supervisor must implement Windows Job Objects (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) and Linux `prctl` (`PR_SET_PDEATHSIG`) to guarantee the OS annihilates all child processes upon a hard crash.
*   **KiCad Version Constraint:** The KiCad IPC API is only stable in KiCad 9, 10, and 11. The Python daemon must verify the installed KiCad version on startup and gracefully warn the user if it is too old.
*   **Python Boot Latency:** Heavy imports (e.g., `torch`, `langchain`) can block standard output for 2-4 seconds during initial app launch. The Tauri UI must show a "Waking up AI Core..." loading state during this phase.

## 4. Module Map & Reference Links

See [ROADMAP.md](../ROADMAP.md) for the full spec backlog, milestone sequencing, and the
Claude Code spec-to-context workflow.

```text
[SPEC-000] (Root - You are here)
   |-- [SPEC-101] Tauri UI & Rust Process Supervisor      (Implemented - CTX-101.1)
   |-- [SPEC-102] Python JSON-RPC Daemon & Route Registry (Implemented - CTX-102.1)
   |-- [SPEC-103] KiCad IPC Bridge                        (Bridge implemented - CTX-103.1)
   `-- [SPEC-104] FreeCAD Headless Bridge                 (Pipeline implemented - CTX-104.1)
```

*   [SPEC-101: Tauri UI & Rust Process Supervisor](../apps/tauri-ui/specs/SPEC-101-ui-ipc-bridge.md)
*   [SPEC-102: Python JSON-RPC Daemon & Route Registry](../services/python-daemon/specs/SPEC-102-daemon-rpc-router.md)
*   [SPEC-103: KiCad IPC Bridge](../services/python-daemon/specs/SPEC-103-kicad-ipc.md)
*   [SPEC-104: FreeCAD Headless Bridge](../services/python-daemon/specs/SPEC-104-freecad-headless.md)

---
id: SPEC-104
title: "FreeCAD Headless Bridge"
status: Draft
type: Module
created: 2026-08-07
last_updated: 2026-08-07
target_version: v0.1.0
location: "services/python-daemon/specs/SPEC-104-freecad-headless.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
---

# SPEC-104: FreeCAD Headless Bridge

## 1. Executive Summary & Goals
*   **High-Level Goal:** Generate 3D printable enclosures and hardware models parametrically without launching the FreeCAD GUI.
*   **Business / Technical Value:** Mechanical modeling requires complex boolean operations and fillet calculations that are too difficult to write from scratch. By using FreeCAD as a headless geometry kernel (OpenCASCADE), we can reliably generate STEP and GLB files for the React UI to display.
*   **Non-Goals:** We are not building a live 3D editor. FreeCAD is treated strictly as an asynchronous build pipeline: Input constraints (dimensions/holes) -> Output file (`.glb`).

## 2. System Architecture & Design Choices
*   **Execution Strategy:** Due to FreeCAD's C++ memory constraints and global states, importing the `FreeCAD` python module directly into our long-running `daemon.py` can cause memory leaks and segmentation faults over time.
*   **Subprocess Handoff:** 
    1. `daemon.py` receives a request (e.g., `generate_enclosure(width=50, height=20)`).
    2. It writes a temporary Python script (`temp_build.py`) containing the specific geometry commands.
    3. It spawns FreeCAD via CLI: `freecadcmd -c temp_build.py`.
    4. FreeCAD executes, saves a `.glb` to the system's temporary directory, and exits cleanly.
    5. `daemon.py` reads the exit code and returns the `.glb` file path to Tauri.

## 3. Known Constraints & Risks
*   **Cold Boot Time:** `freecadcmd` can take 1-3 seconds to spin up and load the OpenCASCADE kernel. The UI must account for this latency.
*   **Path Resolution:** Finding the FreeCAD executable on a user's machine is non-trivial. The Python daemon must check standard paths (e.g., `C:\Program Files\FreeCAD 0.21\bin\freecadcmd.exe`) and provide a settings UI if the path needs manual configuration.

## 4. Module Map & Reference Links
*   [Root Architecture: SPEC-000](../../../specs/SPEC-000-architecture-overview.md)
# 🛠️ Hardware Agent Studio

**Hardware Agent Studio** is an open-source, local-first AI assistant that bridges the gap between PCB design (KiCad) and Mechanical CAD (FreeCAD). 

Instead of writing separate, fragmented plugins for different CAD tools, this app acts as a unified master orchestrator. It uses **Tauri** for a fast, cross-platform UI, and a long-running **Python IPC Daemon** to drive KiCad and FreeCAD via their native APIs.

## 🚀 Features
*   **The KiCad Bridge:** Leverages the new `kicad-python` Protocol Buffer IPC API (KiCad 9+) to interact with live PCB designs without freezing the GUI.
*   **The FreeCAD Bridge:** Spawns a background headless instance of FreeCAD to parametrically generate 3D enclosures based on your PCB mounting holes.
*   **Local AI (Privacy First):** Uses standard JSON-RPC to let you plug in local Ollama models or remote LLMs to generate standard symbols and footprints from datasheets.
*   **No Dangling Processes:** Built on Tauri’s Rust backend, featuring OS-level process ownership (Windows Job Objects / Linux `prctl`) to guarantee background Python/CAD engines die gracefully when the app closes.

## 🏗️ Architecture
*   `apps/tauri-ui/` - React/Tailwind frontend (3D web viewers, chat interface).
*   `core/tauri-rust/` - Rust process manager and OS-level lifecycle supervisor.
*   `services/python-daemon/` - The CLI sidecar that communicates with Tauri over `stdin/stdout` and executes CAD tasks.

## 🤝 Contributing
We need:
1.  **React/Three.js Developers:** To build out the `.glb` 3D viewer for the FreeCAD exports.
2.  **Hardware Engineers:** To refine the `kicad-python` IPC logic for auto-routing logic.
3.  **Python Devs:** To integrate supplier APIs (DigiKey, Octopart) for automatic footprint generation.
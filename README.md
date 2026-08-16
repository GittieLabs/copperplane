# 🛠️ Hardware Agent Studio

**Hardware Agent Studio** is an open-source, local-first AI assistant for hardware engineers — one
workspace that bridges PCB design (**KiCad**) and mechanical CAD (**FreeCAD**), instead of a pile of
disconnected plugins.

It's a **Tauri** desktop app (Rust + React) driving a long-running **Python daemon** that talks to
KiCad over its native IPC API and to FreeCAD headlessly, orchestrated by an LLM you choose —
Anthropic, OpenAI, Google, Perplexity, or a fully local Ollama model. Everything it touches stays on
your machine: your parts library, your API keys, your board files.

> **Status: early, under active daily development.** The backend is real and genuinely useful today
> (see below) — a real project/library workspace, real KiCad/FreeCAD bridges, real confirmation
> gating before anything touches your board. It is not yet a polished, install-and-go product. If
> you want to help shape it before it is, this is a good time to jump in — see
> [Contributing](#-contributing).

---

## ✨ What it does today

*   **A real project & parts library, not a chat transcript.** Projects, Parts, Symbols, and
    Footprints are real objects — persisted as readable JSON files plus a rebuildable SQLite index,
    not thrown away the moment you generate a second component. Every field records **where it came
    from** (a datasheet, a supplier API, a model inference) so you can tell a verified value from an
    LLM's guess.
*   **Component discovery with real disambiguation.** Search a part number, get ranked candidates
    with sources and confidence — never a silent substitution. Confirm one, and it's saved to your
    library for reuse across every future project.
*   **A live KiCad bridge.** Talks to a running KiCad 9+ instance over its own Protocol Buffer IPC
    API — no GUI freezing, no file-format hacking. Component injection is real, transactional
    (commit-or-rollback), and **gated behind an explicit confirmation step** before anything writes
    to your open board.
*   **Footprint search across every library you have.** Searches your installed KiCad libraries —
    including the ~150 that ship built into KiCad itself — *and* the footprints you've already saved
    in this app, merged into one ranked result set.
*   **A headless FreeCAD bridge.** Generates a parametric 3D enclosure straight from your board's
    real outline and mounting holes, viewable in-app via an interactive 3D viewer.
*   **Bring your own model.** Configurable LLM provider and model in Settings, with API keys stored
    in your OS keychain — never in a config file on disk.
*   **No orphaned processes.** The Rust core owns the Python daemon's lifecycle at the OS level
    (Windows Job Objects, `prctl` on Linux) — closing the app cleanly kills every background
    process it spawned, CAD engines included.
*   **Cross-platform CI from day one.** The daemon and frontend test suites run on macOS, Linux, and
    Windows on every PR — including real, live integration tests that skip themselves cleanly when
    the machine running them doesn't have KiCad or FreeCAD installed.

## 🏗️ Architecture

```text
hardware-agent-studio/
├── apps/tauri-ui/        React + TypeScript frontend — project shell, component discovery,
│                          part detail, settings, 3D viewer.        → apps/tauri-ui/README.md
├── core/tauri-rust/       Rust process supervisor — spawns and owns the Python daemon,
│                          OS keychain access, crash-shield lifecycle management.
│                                                                     → core/tauri-rust/README.md
└── services/python-daemon/ The JSON-RPC sidecar — KiCad/FreeCAD bridges, the LLM provider
                            layer, the project/library store.        → services/python-daemon/README.md
```

The three layers talk over a real, versioned contract: Tauri's own IPC between Rust and the
frontend, and a line-delimited JSON-RPC protocol over `stdin`/`stdout` between Rust and the Python
daemon. See [`specs/SPEC-000-architecture-overview.md`](specs/SPEC-000-architecture-overview.md)
for the full architecture record, and [`ROADMAP.md`](ROADMAP.md) for how every piece of this got
built — each real feature has a `SPEC-*.md` design doc and a `CTX-*.md` implementation log with real
commit hashes, test results, and honestly-recorded mistakes.

## 🚀 Getting Started

You'll need [Rust](https://rustup.rs/), [Node.js](https://nodejs.org/) 18+, and
[uv](https://github.com/astral-sh/uv) for the Python daemon.

```bash
# 1. Python daemon dependencies
cd services/python-daemon
uv venv && uv pip install -r requirements.txt
cd ../..

# 2. Frontend dependencies
cd apps/tauri-ui
npm install
cd ..

# 3. Run the app in dev mode (spawns the frontend dev server and the daemon for you)
cd core/tauri-rust
npx @tauri-apps/cli@2 dev
```

KiCad and FreeCAD are optional for exploring the UI, but real live verification (and most of the
interesting features) needs a real, running **KiCad 9+** install; FreeCAD 0.20+ is needed for
enclosure generation. See [`services/python-daemon/README.md`](services/python-daemon/README.md)
for daemon-only setup and test details.

## 🗺️ Where this is heading

The near-term product model (see [`PRODUCT-PLAN.md`](PRODUCT-PLAN.md) for the full reasoning) is a
straightforward one: real **Projects**, each holding real **Parts** with symbols and footprints
pulled from a shared, reusable **Library** — with every AI-assisted step confirmable, never silent.

*   ✅ **M1 — Capability proof.** Live KiCad/FreeCAD bridges, LLM-driven component extraction,
    parametric enclosures. Done — this is the backend the rest of the product stands on.
*   ✅ **M2 — Shell, Projects, Components.** A real project/library workspace replacing the original
    single-text-box demo: search, disambiguate, save to library, reuse across projects. Done.
*   ✅ **M3 — Schematic stage.** Footprints as first-class, searchable, reusable objects: search
    across installed and saved libraries, generate from datasheet dimensions, export to a real
    `.pretty` library, plus per-pin connection guidance (decoupling, protection, power) via a real
    LLM call. Done.
*   ✅ **M4 — Advisors.** Real ERC/DRC via `kicad-cli`, explained in plain language with suggested
    fixes via a real LLM call. DRC auto-targets whatever board is open in KiCad; ERC takes an
    explicit, user-picked file (schematic documents have no live-resolution path — a real,
    confirmed KiCad IPC limitation, not a shortcut). Done.
*   ✅ **M5 — Enclosure from geometry, then ambition.** Import a real `.kicad_pcb` file, no live
    KiCad connection required, and generate a starter enclosure body from its actual outline and
    mounting holes via `kicad-cli`'s own DXF/drill export. Auto-layout and assisted routing stay
    explicitly out of scope. Done.

Distribution work — code signing, auto-update, verified Windows/Linux builds — is tracked
separately and is real but intentionally *after* the product model, not before it. A macOS
`.app` build already exists (`SPEC-401`); it's just not the current priority.

## 🤝 Contributing

This repo runs on a **spec → context → implement → verify** workflow: every real feature has a
`SPEC-*.md` explaining what and why, and a `CTX-*.md` recording exactly how it was built, tested,
and what went wrong along the way — including the honest mistakes, not just the wins. Read
[`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a PR; it's short, and CI enforces it.

**Where help is genuinely useful right now:**
1.  **Hardware engineers** to pressure-test the KiCad/FreeCAD bridges against real boards and real
    footprint libraries — the fastest way to find where a "should work" assumption doesn't.
2.  **Windows and Linux users** — the daemon and frontend both run cross-platform in CI, but the
    live CAD-integration paths have only ever been verified end-to-end on macOS. `SPEC-403` tracks
    turning that from a hope into a checked fact.
3.  **React/Three.js developers** to keep building out the project shell and 3D viewer as the
    product model in `PRODUCT-PLAN.md` fills in.
4.  **Python developers** interested in the LLM tool-calling layer (`SPEC-204`) or supplier-API
    integration (`SPEC-203`, not yet started).

Run [`/spec-status`](CONTRIBUTING.md) (or read `ROADMAP.md` directly) to see exactly what's
specced, what's mid-implementation, and what's still an open idea before picking something up.

## 📄 License

Apache License 2.0 — see [`LICENSE`](LICENSE).

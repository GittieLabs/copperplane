# 🐍 Hardware Agent Studio — Python Daemon

The local AI and CAD orchestration backend. It runs as a real child process of the Tauri app (see
[the root README](../../README.md) for how the three layers fit together), speaking a
line-delimited JSON-RPC protocol over `stdin`/`stdout` — `stdout` is that protocol's wire, so
nothing in this daemon ever prints to it; diagnostics go to `stderr`/logging only.

## What's here

*   `daemon.py` — the JSON-RPC router: request parsing, the route table, and the async job protocol
    for anything that can't finish inside a single request/response.
*   `kicad_bridge.py` / `kicad_write.py` — the live KiCad IPC bridge (board reads, transactional
    component injection) and the pad/footprint geometry it writes.
*   `freecad_bridge.py` — spawns headless FreeCAD to generate parametric enclosures from a real
    board's outline and mounting holes.
*   `fp_lib_table.py` — real, filesystem-based KiCad footprint-library search (installed libraries,
    including KiCad's own built-in set) — kipy's own IPC connection has no search capability at all,
    so this reads KiCad's config directly instead.
*   `component_pipeline.py` / `llm_providers.py` — the LLM-driven datasheet extraction pipeline and
    the multi-provider abstraction underneath it (Anthropic, OpenAI, Google, Perplexity, Ollama).
*   `library_store.py` — the real Project/Part/Symbol/Footprint persistence layer: readable JSON on
    disk, a rebuildable SQLite index for search.
*   `tool_registry.py` — wraps a subset of the routes above as real, confirmation-gated tools for
    LLM tool-calling (`kicad.inject_component` is the one route that mutates a live board, and it's
    the one gated behind an explicit confirm step).

Every module above has a real `SPEC-*.md`/`CTX-*.md` pair under `specs/`/`context/` (or the repo
root, for cross-cutting work like the sidecar-packaging story) — read those for the real design
reasoning and what's been verified against a live KiCad/FreeCAD install versus only mocked.

## Local Development Setup

We use [uv](https://github.com/astral-sh/uv) for Python environment and dependency management —
fast, and deterministic across platforms.

**1. Install uv**
(Follow official docs, or run `curl -LsSf https://astral.sh/uv/install.sh | sh`)

**2. Create the Virtual Environment**
Run this from inside the `services/python-daemon` directory:
```bash
uv venv
```

**3. Activate the Environment**
* Mac/Linux: `source .venv/bin/activate`
* Windows: `.venv\Scripts\activate`

**4. Install Dependencies & Run Tests**
```bash
uv pip install -r requirements.txt
python -m unittest discover tests/
```

Tests that need a real, running KiCad or FreeCAD skip themselves cleanly when neither is installed
— on a real dev machine with either tool open, those same tests run for real instead, per this
repo's own "verify against the real thing" norm. CI runs this exact suite on macOS, Linux, and
Windows on every PR (see `.github/workflows/python-ci.yml`).

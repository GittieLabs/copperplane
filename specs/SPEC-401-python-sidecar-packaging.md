---
id: SPEC-401
title: "Python Sidecar Packaging"
status: Completed
type: Module
created: 2026-08-13
last_updated: 2026-08-13
target_version: v0.1.0
location: "specs/SPEC-401-python-sidecar-packaging.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs: []
user_facing: false
---

# SPEC-401: Python Sidecar Packaging

## 1. Executive Summary & Goals

*   **High-Level Goal:** Freeze `services/python-daemon` into a real, per-platform binary
    (PyInstaller or equivalent) and ship it via Tauri's `externalBin`/sidecar mechanism, resolved
    from the app's own resource directory at runtime -- replacing the two concrete, already-real
    blockers in the code today: `core/tauri-rust/src/lib.rs`'s `daemon_script_path()` bakes
    `env!("CARGO_MANIFEST_DIR")` (a developer's own checkout path) into the compiled binary, and
    `core/tauri-rust/src/daemon.rs`'s `spawn_daemon` calls `Command::new("python3")`, assuming a
    system Python with `kicad-python`, `pynng`, `trimesh`, and `gittielabs-agentflow` all already
    importable. `SPEC-101`'s crash shield must keep working unchanged across the swap -- it operates
    on the spawned `Child` handle regardless of what's inside it.
*   **Business / Technical Value:** `ROADMAP.md` itself already names this "the highest-risk
    unsolved problem in the project," and correctly so: every prior spec's own live-verification
    testing (`CTX-103.1` against KiCad, `CTX-104.1` against FreeCAD, every real `freecadcmd`/`kicad_
    bridge` round trip this project has run) has only ever proven the app works on one developer's
    own machine, with one developer's own Python environment. Nothing today distinguishes "works in
    this checkout" from "installable by a real user" -- this spec is that distinction.
*   **Non-Goals:**
    *   **Not bundling KiCad or FreeCAD themselves.** `README.md`'s own stated non-goal already
        rules this out -- both stay separately-installed applications this app connects to
        (`kicad_bridge`'s IPC socket) or shells out to (`freecad_bridge`'s `freecadcmd` subprocess),
        never frozen into this app's own binary.
    *   **Not code signing, notarization, or auto-update.** `SPEC-402`'s job, and it explicitly
        depends on this spec landing first.
    *   **Not verifying the frozen binary on Windows or Linux CI.** `SPEC-403`'s job (depends on
        `SPEC-903`). This spec's own scope is a working macOS sidecar -- the one platform with a
        real, live-verified CAD toolchain today, per every prior `CTX-*.md`'s own Testing
        Requirements Matrix. Freezing for Windows/Linux is real, necessary follow-up work, named
        here explicitly rather than assumed to work by symmetry with macOS.
    *   **Not changing `cargo tauri dev`'s behavior.** Dev mode keeps spawning `python3 daemon.py`
        exactly as it does today -- the frozen sidecar is a *build-mode* concern only. Conflating the
        two would break the fast dev-mode iteration loop every prior `CTX-*.md` in this project has
        relied on for live verification against real KiCad/FreeCAD.

## 2. System Architecture & Design Choices

*   **Freezing tool:** PyInstaller (or an equivalent, e.g. Nuitka) producing one binary per Tauri
    target triple, matching Tauri's own per-platform build matrix.
*   **The real dependency surface to freeze** (`services/python-daemon/requirements.txt`, read
    directly rather than assumed):
    ```
    kicad-python==0.7.1
    pynng==0.9.0
    trimesh==5.0.0
    pyyaml==6.0.3
    certifi==2026.4.22
    gittielabs-agentflow[anthropic,openai,google]==0.8.2
    ```
    **A real correction to this repo's own `ROADMAP.md`, found by reading `requirements.txt`
    directly instead of trusting the roadmap's prose:** `ROADMAP.md`'s own SPEC-401 backlog entry
    describes AgentFlow's dependencies (`pydantic`, `httpx`, a provider SDK) as something this spec
    still needs to "budget real time for," phrased as a future addition. `gittielabs-agentflow` is
    already a real, installed, in-use dependency -- `SPEC-201` shipped and merged well before this
    spec was written. The freezing surface is larger than the roadmap's own text currently implies:
    `pynng`'s native extension and `trimesh`'s optional dependencies (both already flagged in
    `ROADMAP.md` as "where this kind of work goes wrong"), plus whichever of `anthropic`/`openai`/
    `google-genai` a real user's configured provider(s) actually pull in transitively.
*   **A named, concrete PyInstaller risk beyond generic "native extensions are hard":**
    `llm_providers.py`'s own `_build_provider` imports each provider SDK class *lazily, inside the
    function*, specifically so an unconfigured provider's SDK is never imported at daemon startup
    (the exact latency reasoning `SPEC-107`'s `daemon.ready` handshake already established). This is
    precisely the import pattern PyInstaller's static analysis is known to miss -- a provider module
    only ever reached at runtime, from inside a function, on whatever specific input the user's own
    `CONFIG["llm_provider"]` happens to select. Each of `anthropic`/`openai`/`google.genai` will
    likely need an explicit `--hidden-import` (or the PyInstaller-spec equivalent), not just "freeze
    what static analysis finds."
*   **Tauri wiring:** `tauri.conf.json`'s `bundle` section gains a real `externalBin` entry (verified
    directly: not present today) naming the per-target-triple frozen binary Tauri copies into the
    app bundle. `core/tauri-rust/src/daemon.rs`'s `spawn_daemon` swaps `Command::new("python3")` for
    Tauri's sidecar-spawn mechanism (`tauri_plugin_shell`'s `Command::sidecar`, already a real
    dependency per `CTX-306.1`), and `core/tauri-rust/src/lib.rs`'s `daemon_script_path()` resolves
    the sidecar from the app's real resource directory (`app.path().resource_dir()`) instead of
    `env!("CARGO_MANIFEST_DIR")`.
*   **Cross-Module Impacts:** `core/tauri-rust` (the two named blocker call sites, `tauri.conf.json`),
    `services/python-daemon` (a real PyInstaller spec file, build tooling, CI wiring for the freeze
    step itself). `SPEC-101`'s supervisor/crash-shield code is explicitly **not** expected to change
    -- it owns the spawned `Child` handle generically, regardless of what binary is inside it.

## 3. Known Constraints & Risks

*   **`pynng`'s native extension and `trimesh`'s optional dependencies are the two risks
    `ROADMAP.md` itself already flags as "where this kind of work goes wrong."** Budget real time for
    both; do not treat either as a footnote to a mostly-mechanical PyInstaller invocation.
*   **The lazy-provider-import hidden-imports risk** named above in §2 -- a real, specific,
    already-identified gap in naive PyInstaller static analysis, not a generic warning.
*   **Binary size.** Freezing `kipy` + `pynng` + `trimesh` + three LLM provider SDKs into one binary
    is very likely to produce a large artifact (real precedent from similar PyInstaller freezes:
    tens to a few hundred MB) -- a real distribution-size cost worth naming here, not something this
    spec needs to solve, but something `SPEC-402`'s release tooling will need to account for.
*   **PyInstaller output is not cross-compilable.** Freezing for Windows or Linux requires actually
    running PyInstaller on that OS (or a matching CI runner) -- there is no way to produce a working
    Windows/Linux sidecar from this macOS-only development environment. This spec's own scope
    produces a working macOS sidecar only; Windows/Linux freezing is real, unverified follow-up,
    named explicitly rather than silently assumed to work by symmetry (`SPEC-403`'s own job, and it
    depends on `SPEC-903` for the CI runners that would make it possible).
*   **`cargo tauri dev` must keep working unchanged.** The frozen sidecar swap must be additive to
    the build/bundle path, not a replacement for the dev-mode `python3 daemon.py` spawn every prior
    `CTX-*.md`'s live verification against real KiCad/FreeCAD has relied on.

## 4. Module Map & Reference Links

*   [Root Architecture: SPEC-000](SPEC-000-architecture-overview.md)
*   [SPEC-101](../apps/tauri-ui/specs/SPEC-101-ui-ipc-bridge.md) -- the crash shield / supervisor
    this spec's swap must not disturb.
*   [SPEC-107](SPEC-107-structured-logging-diagnostics.md) -- the `daemon.ready` handshake-latency
    reasoning behind `llm_providers.py`'s lazy provider imports, the source of this spec's named
    hidden-imports risk.
*   [SPEC-201](../services/python-daemon/specs/SPEC-201-llm-provider-abstraction.md) -- AgentFlow's
    real, already-shipped adoption; this spec's own §2 corrects `ROADMAP.md`'s stale framing of it as
    a future dependency addition.
*   [SPEC-402](../ROADMAP.md) -- Release, Signing & Auto-Update; depends on this spec (not yet
    written).
*   [SPEC-403](../ROADMAP.md) -- Cross-Platform Verification Matrix; depends on `SPEC-903` and
    exercises the Windows/Linux freezing this spec explicitly defers.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-401] Python Sidecar Packaging
          └── [Context 401.1] (not yet written)
```

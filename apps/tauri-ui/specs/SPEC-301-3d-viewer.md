---
id: SPEC-301
title: "3D Viewer"
status: Draft
type: Feature
created: 2026-08-09
last_updated: 2026-08-09
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-301-3d-viewer.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
---

# SPEC-301: 3D Viewer

## 1. Executive Summary & Goals

*   **High-Level Goal:** Render the `.glb` mesh `freecad.generate_enclosure` already produces.
    `SPEC-101` names React Three Fiber as the intended stack, but nothing renders today — the path
    comes back from the daemon and the UI simply never opens it. This spec adds an R3F canvas, sane
    camera/lighting defaults, loading/error states, and disposal on unmount, plus the loading
    mechanism itself: the WebView cannot load an arbitrary absolute filesystem path, and the mesh
    currently lands in the shared OS temp directory, not anywhere the frontend has permission to
    reach.
*   **Business / Technical Value:** This is the single piece standing between "the daemon can
    generate a mesh" and "a human can see it" — the last step of the `v0.1.0` "It's real" vertical
    slice (`ROADMAP.md` §4, M1). Every other piece of that milestone (async job submission, progress,
    cancellation) already exists (`SPEC-105`); this is what makes the result of a job visible.
*   **Non-Goals:**
    *   Not mounting-hole geometry, PCB-aware sizing, or anything connecting the KiCad bridge to the
        FreeCAD bridge — that's `SPEC-108`/`109`. This spec renders whatever `.glb`
        `freecad.generate_enclosure` hands it today, unchanged.
    *   Not a general-purpose asset pipeline for arbitrary future file types. Scoped to the one
        `.glb` output path that exists right now.
    *   Not texture/material authoring — FreeCAD's parametric box has no material data; a flat,
        legible default material is enough to prove the pipeline.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **Decided: a Tauri-scoped asset protocol, not a Rust-mediated byte read.** This was
        `SPEC-301`'s own explicit gotcha, raised rather than pre-decided: *"the WebView cannot load
        an arbitrary absolute path from disk. Either scope the asset protocol to the daemon's output
        directory, or have Rust read the bytes and hand them to the frontend as a blob."* Resolved in
        favor of the scoped asset protocol — `@tauri-apps/api/core`'s `convertFileSrc()` hands the
        R3F `GLTFLoader` a URL it can fetch directly, with no extra IPC round-trip and no risk of a
        multi-megabyte mesh becoming an inefficiently-serialized JSON number array (the failure mode
        the blob-read alternative would need deliberate binary-safe IPC to avoid).
    *   **The `.glb` output location moves out of the shared OS temp directory.**
        `freecad_bridge.generate_enclosure` currently writes under `tempfile.gettempdir()` — fine for
        a bridge with no frontend consumer, wrong once the WebView needs scoped access to it, since
        scoping `assetProtocol` to the *entire* system temp directory would expose everything else
        already living there. `generate_enclosure` instead writes under a dedicated,
        app-owned output directory (Tauri's `app_data_dir()`-relative `generated/` subfolder), and
        `tauri.conf.json`'s `assetProtocol.scope` is narrowed to exactly that directory.
    *   **R3F owns rendering; nothing upstream changes.** `freecad.generate_enclosure`'s JSON-RPC
        contract (params, `job_id`, the eventual `job.completed` result) is untouched — this spec is
        purely what the frontend does with the path it already receives via `SPEC-105`'s
        `submitJob`.
*   **Data Flow / Interactions:**

    ```text
    EnclosurePanel (CTX-105.2, already built) submits freecad.generate_enclosure
       │
       ▼
    Daemon writes the .glb under its app-owned output directory (not
    the shared OS temp dir) and reports the path via job.completed
       │
       ▼
    Viewer component: convertFileSrc(glbPath) -> an asset:// URL Tauri's
    scoped assetProtocol is allowed to serve
       │
       ▼
    R3F <Canvas> + GLTFLoader fetches that URL directly (no extra Rust
    round-trip), renders the mesh with default camera/lighting
       │
       ▼
    On unmount or on the next job's result replacing it: dispose of the
    previous mesh's GPU buffers (geometry/material/texture .dispose())
    ```

*   **Cross-Module Impacts:**
    *   `services/python-daemon`: `freecad_bridge.generate_enclosure`'s output path moves from
        `tempfile.gettempdir()` to an app-owned `generated/` directory the daemon is told about (or
        resolves itself, per-OS, matching the app's own data directory convention) — the exact
        mechanism (env var from Rust vs. Python resolving the same per-OS convention independently)
        is this context's call, informed by `CTX-106.1`'s existing env-injection precedent.
    *   `core/tauri-rust`: `tauri.conf.json` gains `app.security.assetProtocol` (`enable: true`,
        `scope` narrowed to the app's `generated/` directory); `capabilities/default.json` gains
        whatever permission enabling the asset protocol requires.
    *   `apps/tauri-ui`: new dependencies (`three`, `@react-three/fiber`, and `@react-three/drei` for
        the loader/camera-controls convenience it provides); a new `Viewer` component consuming
        `EnclosurePanel`'s job result.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   `generate_enclosure`'s `finally` block currently cleans up its temp script and intermediate
        `.stl`, but never deletes the returned `.glb` — a `CTX-104.1`-era decision (the frontend
        didn't exist to consume it yet) that becomes a real, growing disk-space leak once every
        generated enclosure lands in a persistent app directory instead of a self-cleaning OS temp
        dir. This context should decide whether cleanup happens on next-generation, on app quit, or
        is deferred with the leak explicitly documented as known debt — not silently left unowned.
*   **Gotchas & Hazards:**
    *   **Narrow the `assetProtocol` scope precisely.** A scope wider than the app's own output
        directory (e.g. the whole `app_data_dir()`, if other data ever lives there) re-opens the
        same exposure problem this spec exists to close, just one level up.
    *   **GPU resource disposal is the standard Three.js failure mode, and it's silent.** Loading a
        second enclosure without disposing of the first's geometry/material leaks GPU memory that
        never shows up as a JS heap problem — only as the app slowly degrading over a session. Needs
        explicit `dispose()` calls on unmount and before loading a replacement mesh, with real test
        coverage (mock the loader, assert `dispose` was called), not just "it looks fine once."
    *   **A `.glb` isn't guaranteed valid just because the path exists.** `CTX-104.1`'s own tests
        already verify the file is a genuine glTF binary (magic-byte check) at the daemon layer: the
        frontend still needs a loading-failure UI state for the case where `GLTFLoader` itself
        rejects the file (corrupt data, a version R3F's loader doesn't support) — silently doing
        nothing is not an acceptable failure mode for a feature whose entire point is visibility.

## 4. Module Map & Reference Links

*   [ROADMAP.md](../../../ROADMAP.md) §3.3, §4 — this spec's backlog entry and the M1 vertical slice
    it completes.
*   [SPEC-104](../../../services/python-daemon/specs/SPEC-104-freecad-headless.md) — the `.glb`
    producer this spec's viewer consumes, and the temp-directory decision this spec revisits.
*   [SPEC-105](../../../specs/SPEC-105-daemon-async-job-progress-protocol.md) / [CTX-105.2](../context/CTX-105.2-frontend-job-progress-client.md) —
    the `submitJob`/`EnclosurePanel` machinery this spec's viewer plugs into; no protocol changes.
*   [SPEC-106](../../../specs/SPEC-106-configuration-secrets-store.md) — the existing Rust-injects-
    at-spawn precedent this spec's output-directory decision may reuse.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-301] 3D Viewer
          └── [Context 301.1] (not yet written)
```

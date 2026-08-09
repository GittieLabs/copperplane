---
id: SPEC-106
title: "Configuration & Secrets Store"
status: Draft
type: Feature
created: 2026-08-09
last_updated: 2026-08-09
target_version: v0.1.0
location: "specs/SPEC-106-configuration-secrets-store.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs: []
---

# SPEC-106: Configuration & Secrets Store

## 1. Executive Summary & Goals

*   **High-Level Goal:** One place for every setting the app currently has no home for: a
    `freecadcmd` path override (`CTX-104.1` Plan Drift explicitly asked for this), KiCad IPC
    connection settings, the selected LLM provider and model, and supplier API keys — with secrets
    stored in the OS keychain, never a plaintext file, and never passed to the daemon as a
    command-line argument, where they'd be visible to any user via `ps`.
*   **Business / Technical Value:** Every one of `SPEC-103`/`SPEC-104`'s hard-coded assumptions
    (search `PATH` and a handful of standard install locations; connect to whatever KiCad happens
    to be running) works for exactly one dev machine. `SPEC-201`'s LLM provider selection and
    `SPEC-203`'s supplier API keys can't be built at all without a place to put credentials that
    isn't `git`-tracked. This spec is the platform primitive that unblocks a real Settings UI
    (`SPEC-303`) and the intelligence layer (`SPEC-201`/`202`/`203`).
*   **Non-Goals:**
    *   Not the Settings UI itself (`SPEC-303`) — this spec defines the storage format and the
        injection mechanism; a human-facing form to edit these values is a separate, later spec.
    *   Not live config reload without an app restart. Decided explicitly (see §2): Rust owns
        config and secrets, and injects them into the daemon once, at spawn. A changed setting
        takes effect on the daemon's next restart — already a cheap, already-supported operation
        (`SPEC-101`'s supervisor spawns a fresh daemon on every app launch). Trading that off against
        keeping secrets out of Python's memory for as short a window as possible is this spec's
        deliberate choice, not an oversight.
    *   Not a general key-value settings system for arbitrary future features. Scoped to the four
        concrete needs named above; extending the schema later is cheap, but this spec doesn't
        pre-build unused generality.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **Decided: Rust owns config and secrets, and injects them into the daemon at spawn — the
        daemon never reads a config file or touches the OS keychain itself.** This was `SPEC-106`'s
        own open question (raised, not pre-decided, when this spec was first drafted); resolved in
        favor of Rust ownership because it keeps secrets out of Python's memory until the moment
        they're actually needed, and matches `SPEC-101`'s existing pattern where Rust already owns
        the daemon's entire process lifecycle. The cost — a setting change needs a daemon restart,
        not a hot reload — is accepted; `CTX-101.1` already established that restarting the daemon is
        cheap and unremarkable.
    *   **Two different injection channels for two different sensitivity levels.** Non-secret
        settings (a `freecadcmd` path override, KiCad connection settings, the selected LLM
        provider/model name) carry no confidentiality requirement beyond what any other app config
        has — these can ride as environment variables on the daemon's `Command`, which are visible
        only to the same OS user (via `/proc/<pid>/environ` on Linux, or process inspection tools
        elsewhere), a materially smaller exposure than `ps`'s argv, which is world-readable by
        default. Actual secrets (API keys) get a strictly tighter channel: Rust writes them as the
        *first* line on the daemon's `stdin` — the same private pipe `SPEC-101` already built and
        that no other process can observe — as a `daemon.configure` JSON-RPC request, before any
        other request is sent. This reuses the existing wire protocol instead of inventing a new
        channel, and keeps secrets off both argv and the environment table entirely.
    *   **Config storage:** non-secret settings persist as a small JSON file in Tauri's own
        `app_config_dir()`. Secrets persist in the OS keychain (macOS Keychain, Windows Credential
        Manager, Linux Secret Service) via a Rust keychain-access crate — never written to that
        JSON file, never logged, never included in any error message that could reach `stderr` or a
        crash report.
*   **Data Flow / Interactions:**

    ```text
    App launch
       │
       ▼
    Rust: read app_config_dir()/config.json (non-secret settings)
       │
       ▼
    Rust: read secrets from OS keychain (supplier/LLM API keys)
       │
       ▼
    Rust: spawn daemon.py with non-secret settings as env vars
       │
       ▼
    Rust: write a "daemon.configure" JSON-RPC request (secrets in params)
          as the FIRST line on the daemon's stdin, before any other request
       │
       ▼
    Python daemon: read+apply this one configure call before entering its
                   normal read loop; every route that needs a setting
                   (find_freecadcmd's override, an LLM provider's API key)
                   reads it from this in-memory config, never from disk
                   or the environment directly
    ```

*   **Cross-Module Impacts:**
    *   `core/tauri-rust`: new config-loading module (`app_config_dir()` JSON read), new keychain
        integration, `daemon.rs`'s `spawn_daemon` gains env vars and the `daemon.configure`
        handshake write.
    *   `services/python-daemon`: `daemon.py` gains a `daemon.configure` route (or an explicit
        first-message check before the normal loop starts) that stores the received config/secrets
        in memory; `freecad_bridge.find_freecadcmd()` checks the override path first;
        `kicad_bridge.py` reads connection settings from the same in-memory store instead of only
        ever using IPC defaults.
    *   No impact on `apps/tauri-ui` for this spec — the Settings UI to actually edit these values
        is `SPEC-303`, out of scope here.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   None yet — this spec has no existing broken behavior to fix, only a genuine gap (nowhere to
        put a `freecadcmd` override or an API key) that currently forces every downstream spec
        needing credentials to invent its own ad-hoc answer.
*   **Gotchas & Hazards:**
    *   **Secrets must never reach `ps`, environment dumps, logs, or crash reports.** The whole
        point of this spec is closing that gap; any implementation that logs the `daemon.configure`
        request verbatim (e.g. a naive debug `stderr` dump of every JSON-RPC line) reopens it.
    *   **The `daemon.configure` handshake must land before any other request**, including the
        first real user action. If the daemon's read loop can process an ordinary request before
        configure has been applied, routes needing a setting (an LLM API key, a path override) will
        silently run with defaults/None instead of failing loudly or waiting.
    *   **OS keychain access itself can fail** (no keychain daemon running, permission denied,
        headless CI environment with no Secret Service) — this needs a clean, specific error
        distinguishing "no keychain available" from "no secret stored yet," since the latter is a
        completely normal first-run state (no API key configured yet) and the former is an
        environment problem.
    *   **CI has no OS keychain at all** on a typical GitHub Actions runner. Any test touching real
        keychain access needs the same "verify for real, skip cleanly when unavailable" pattern
        `CTX-103.1`/`CTX-104.1` already established for KiCad/FreeCAD.

## 4. Module Map & Reference Links

*   [ROADMAP.md](../ROADMAP.md) §3.1 — this spec's backlog entry and its original open question.
*   [CTX-104.1](../services/python-daemon/context/CTX-104.1-freecad-headless-bridge.md) Plan Drift
    — the `freecadcmd` path-override need this spec closes.
*   [SPEC-101](../apps/tauri-ui/specs/SPEC-101-ui-ipc-bridge.md) — the daemon spawn lifecycle and
    `stdin`/`stdout` transport this spec's injection mechanism reuses rather than replacing.
*   [SPEC-303](#) (not yet written) — the Settings UI that will eventually let a human edit what
    this spec stores.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-106] Configuration & Secrets Store
          └── [Context 106.1] (not yet written)
```

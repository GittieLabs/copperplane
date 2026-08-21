---
id: SPEC-303
title: "Settings UI"
status: Completed
type: Feature
created: 2026-08-11
last_updated: 2026-08-11
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-303-settings-ui.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
user_facing: true
---

# SPEC-303: Settings UI

## 1. Executive Summary & Goals

*   **High-Level Goal:** Give a human a real UI for everything `SPEC-106`/`SPEC-107` already made
    configurable or detectable but never exposed: which LLM provider/model/API key is active, whether
    KiCad and FreeCAD are actually reachable, path overrides for both, and a one-click diagnostics
    bundle for bug reports. Today none of this is reachable except by hand-running
    `security add-generic-password` and hand-editing `config.json` — this spec is the only thing that
    turns that into something a person other than whoever's holding this repo's terminal can do.
*   **Business / Technical Value:** Directly caused, not hypothetical: `CTX-302.1`'s Plan Drift
    Deviation 3 records a real, live failure — `"No LLM provider configured"` — on a fresh install
    with zero settings surface, because `llm_provider` had never been set anywhere and no UI existed
    to set it. `ROADMAP.md` §3.3's original framing of this spec still holds: it is "the single
    highest-leverage thing for reducing 'it doesn't work' issues from contributors." Every provider
    key, every KiCad/FreeCAD path override `SPEC-106` defined has sat unreachable since the day it
    shipped.
*   **Non-Goals:**
    *   **Not a redesign of `SPEC-106`'s storage mechanism.** `config.json` for non-secrets, OS
        keychain for secrets, injected at daemon spawn — unchanged. This spec adds the write path
        and the UI on top of that, not a new storage model.
    *   **Not supplier API keys.** `SPEC-203` (Supplier API Integration) was explored and retired
        2026-08-18 — see its tombstone; no distributor integration is planned, so there is no key
        name to manage. If `SPEC-203` §2.3's one surviving option (a TME-only integration) is ever
        revived, it adds its own key here under the same bring-your-own-key model this spec already
        establishes.
    *   **Not Ollama's endpoint, FreeCAD's build timeout, or the heartbeat/crash-detection
        intervals.** All three are currently hardcoded constants with no live pain point driving
        exposing them — deferred, not forgotten (see §3).
    *   **Not the shell chrome itself.** `SPEC-300` §2 (updated 2026-08-11) anchors a Settings item
        at the bottom of the rail, beside Library — a persistent, non-project-scoped destination
        that swaps the main content area with no area-tab row. This spec builds the screen that
        lives behind that entry point; it does not re-decide where the entry point is.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **Three real prerequisites, not just a screen.** Scoping this found that the write path
        doesn't exist yet at any layer below the UI:
        1.  `core/tauri-rust/src/secrets.rs`'s `set_secret`/`delete_secret` exist but are **not
            registered as `#[tauri::command]`s** — dead code today. This spec registers them and
            exposes them to the frontend.
        2.  **No `config.json` *writer* exists.** `core/tauri-rust/src/config.rs`'s `load_config`
            only reads. This spec adds the write side for non-secret settings (provider/model
            selection, KiCad/FreeCAD path overrides).
        3.  `daemon.py`'s `daemon.ready` handshake hardcodes `llm_providers: []` — never populated,
            even though `llm_providers.py` fully exists. This spec's diagnostics tier (§2, Tiers
            below) depends on fixing this so "which providers are configured" is something the
            daemon can actually answer.
    *   **Three tiers, ordered by what's actually blocking real usage today:**
        *   **Tier 1 — LLM provider & credentials.** Provider + model picker, masked API-key inputs
            per provider (Anthropic/Google/OpenAI/Perplexity), save/update/clear per key. The only
            tier with a real, already-observed failure behind it (`CTX-302.1` Deviation 3).
        *   **Tier 2 — Connectivity status.** Surface `daemon.ready`'s already-computed
            `kicad_available`/`freecad_available` flags (currently emitted to nobody), plus editable
            KiCad IPC socket-path/timeout and `freecadcmd` path overrides (already configurable via
            env var per `CTX-106.1`, just with no UI write path).
        *   **Tier 3 — Copy Diagnostics.** One button bundling capability flags, the daemon's log
            file location, and relevant versions to the clipboard — the exact surface `SPEC-107` was
            built anticipating (`CTX-107.1`) and that nothing has consumed since.
    *   **A saved secret never round-trips back to the renderer.** Once a key is saved, the UI shows
        "configured" (masked), never the value again — matching `SPEC-106`'s existing posture that
        keys never touch `stdout` or appear in `ps`. This spec must not regress that.
*   **Data Flow / Interactions:**

    ```text
    Settings UI
       │  user enters/updates a provider API key
       ▼
    new Tauri command (wraps existing set_secret) ──> OS keychain
       │
       ▼
    daemon.configure (already dispatched through handle_request like any
    other route, per test_006_daemon_configure_merges_secrets_into_config
    — confirmed callable at runtime, not just at spawn) ──> CONFIG["secrets"]
    updated live, no daemon restart needed for secrets specifically
       │
       ▼
    Settings UI re-requests daemon.ready (or a new daemon.diagnostics route)
       │
       ▼
    llm_providers now reflects the real configured set (fixed from
    hardcoded [] as part of this spec) ──> UI shows "Anthropic: configured"

    ---

    Settings UI
       │  user edits a KiCad socket path / freecadcmd override
       ▼
    new Tauri command (wraps the new config.json writer) ──> config.json
       │
       ▼
    read once as an env var at daemon SPAWN time (CTX-106.1) — NOT live-
    updatable the way secrets are ──> UI must show "restart to apply",
    not silently no-op (see §3 Gotchas)
    ```

*   **Cross-Module Impacts:**
    *   `apps/tauri-ui`: new Settings screen/route; the highest-surface-area change, but built on
        top of the other two modules' new plumbing, not standalone.
    *   `core/tauri-rust`: register `set_secret`/`delete_secret` as Tauri commands; add a
        `config.json` writer alongside the existing reader; expose both to the frontend.
    *   `services/python-daemon`: fix `daemon.ready`'s `llm_providers` field to reflect actually
        configured providers instead of the hardcoded `[]`.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   `daemon.ready`'s `llm_providers` list is hardcoded to `[]` today (`daemon.py`) — a
        pre-existing bug independent of this spec, but this spec's Tier 3 (and arguably Tier 1's own
        "which providers are configured" display) depends on it being fixed.
    *   `set_secret`/`delete_secret` are unreachable dead code until this spec registers them as
        Tauri commands.
*   **Gotchas & Hazards:**
    *   **Live-update vs. restart-required is not uniform across settings, and must not be assumed
        uniform.** Secrets update live via `daemon.configure` (confirmed by an existing test).
        Socket paths and `freecadcmd` overrides are read once from an env var at daemon *spawn* time
        (`CTX-106.1`) — changing one in this UI without a restart is a silent no-op unless this spec
        either wires a live-update path for those too, or the UI explicitly says "restart to apply."
        Deciding which, and building the wrong one silently, is the single most likely way this spec
        ships something that looks like it worked and didn't.
    *   **A raw API key value must never appear in a log line, `stdout`, or a value returned to the
        renderer after save.** `SPEC-106`'s existing security posture (`CLAUDE.md`: "`stdout` is
        sacred"; keys never as CLI args, never in `ps`) extends to this spec's own new write path —
        regressing it here would undo the reason `SPEC-106` put keys in the keychain at all.
    *   **Resolved 2026-08-11: the shell entry point.** `SPEC-300` §2 now anchors Settings at the
        bottom of the rail, beside Library — see §1. `PRODUCT-PLAN.md` itself still doesn't mention
        `SPEC-303` (flagged in `ROADMAP.md` §3.3, still open), but that's a plan-document gap, not a
        blocking one now that the IA spec itself has a real answer.
*   **Not building yet, and why:** Ollama's endpoint (hardcoded, nobody has hit a need to change it),
    FreeCAD's build timeout (not even in the config schema today), and the heartbeat/crash-detection
    intervals (internal tuning, not a user-facing setting) — Tier 4, no current pain point.

## 4. Module Map & Reference Links

*   [SPEC-106](../../../specs/SPEC-106-configuration-secrets-store.md) /
    [CTX-106.1](../../../context/CTX-106.1-config-secrets-store.md) — the storage mechanism this
    spec adds a write path and UI on top of, unchanged otherwise.
*   [SPEC-107](../../../specs/SPEC-107-structured-logging-diagnostics.md) /
    [CTX-107.1](../../../context/CTX-107.1-structured-logging-diagnostics.md) — the `daemon.ready`
    handshake and diagnostics capability this spec's Tier 2/3 surface for the first time.
*   [SPEC-201](../../../services/python-daemon/specs/SPEC-201-llm-provider-abstraction.md) — the
    provider list (`llm_providers.py`) this spec's Tier 1 picker enumerates.
*   [ROADMAP.md](../../../ROADMAP.md) §3.3 — this spec's backlog entry; also records that
    `PRODUCT-PLAN.md` doesn't address `SPEC-303` at all — a plan-document gap, not a blocking one
    (see §3).
*   [SPEC-300](SPEC-300-product-ia-interaction-model.md) — §2, updated 2026-08-11, anchors this
    spec's entry point at the bottom of the rail, beside Library.
*   [CTX-302.1](../context/CTX-302.1-chat-command-surface.md) Plan Drift Deviation 3 — the real,
    live failure ("No LLM provider configured") this spec exists to make unreachable.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-303] Settings UI
          └── [Context 303.1] (not yet written)
```

## 5. User & Interaction

*   **Product Stage:** App-level, outside any project — alongside the Library, this is one of the
    few surfaces that isn't scoped to a single project. Anchored at the bottom of the rail per
    `SPEC-300` §2.
*   **What the user is trying to accomplish:** Get the app talking to an LLM provider and to their
    installed KiCad/FreeCAD without hand-editing a config file or running a keychain command from a
    terminal; confirm the app can actually reach its dependencies before trying a feature that needs
    them; produce a diagnostics bundle for a bug report without hunting for a log file.
*   **What the user sees and does:** A settings screen with three groups — a provider picker, model
    field, and masked per-provider API-key inputs with save/clear; a KiCad/FreeCAD status panel
    showing reachable/not-reachable plus editable path overrides (with a clear "restart to apply" cue
    where that's genuinely required, per §3); and a single "Copy Diagnostics" button.

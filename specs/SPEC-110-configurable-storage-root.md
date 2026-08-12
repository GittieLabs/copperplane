---
id: SPEC-110
title: "Configurable Storage Root"
status: Draft
type: Feature
created: 2026-08-12
last_updated: 2026-08-12
target_version: v0.1.0
location: "specs/SPEC-110-configurable-storage-root.md"
parent_spec: "SPEC-000-architecture-overview.md"
child_specs: []
user_facing: true
---

# SPEC-110: Configurable Storage Root

## 1. Executive Summary & Goals

*   **High-Level Goal:** Let a user choose where `SPEC-304`'s `library/`/`projects/` tree actually
    lives on disk, with a real native folder picker, instead of `storage_root` always resolving to a
    fixed, buried path under the OS's own application-support directory. Every path this spec's own
    `CTX-307.1` verification produced (`.kicad_sym` exports, cached datasheets, saved Parts) is a
    subdirectory of `storage_root`, so this one change relocates all of them together.
*   **Business / Technical Value:** Found by real, hands-on use, not predicted in advance:
    `CTX-307.1`'s own manual verification confirmed the full search → confirm → save → export flow
    works end to end, and the very next thing the user asked was where the exported file actually
    went — `~/Library/Application Support/com.gittielabs.hardware-agent-studio/storage/library/
    symbols/...` on macOS. A real, technically-correct path that essentially no user will find,
    browse to, back up, or point another tool at without being told exactly where to look. `CTX-304.1`
    considered this directly when `storage_root` was first built and deliberately deferred it
    ("a fixed location under the app's own data directory, not a user-chosen picker") — this spec is
    that deferred decision, revisited with real evidence it matters.
*   **Non-Goals:**
    *   **Not migrating existing files to a newly chosen location.** Changing the override only
        changes where *new* writes go from that point forward. Moving anything already written under
        the old default is the user's own responsibility (or a future spec's, if it turns out to
        matter) — silently moving a user's files as a side effect of a settings change is exactly the
        kind of surprising, hard-to-reverse action this repo's own operating norms warn against.
    *   **Not `output_dir` (the `generated/` `.glb` directory `SPEC-301` writes to).**
        `config.rs`'s own doc comment already draws this distinction: `output_dir` is "ephemeral job
        output," `storage_root` is "persistent user data." The user's own complaint was about
        exported symbols and library files (persistent), not enclosure previews (ephemeral) — this
        spec only touches the persistent side.
    *   **Not a full storage-management UI** (browsing library contents, moving/renaming Parts,
        cleaning up orphaned files). Just: where does `storage_root` point, and can the user change
        it via a real folder picker.
    *   **Not re-deciding `SPEC-106`'s override mechanism.** `freecadcmd_path_override`/
        `kicad_socket_path` already establish "an `Option<String>` field on `DaemonConfig`,
        round-tripped through `config.json`, applied at the next daemon spawn" — this spec reuses
        that mechanism for a fourth field, it doesn't invent a new one.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **A new `storage_root_override: Option<String>` field, not a repurposed `storage_root`
        field.** `config.rs`'s existing `storage_root` field has an explicit, load-bearing contract:
        "always Rust-computed and never read from `config.json`," the same guarantee `output_dir`
        gets, so the two can never silently disagree with where the app's real data directory is.
        Overwriting that contract to sometimes-trust-config.json would be exactly the kind of quiet
        semantic change this repo's own norms warn against. A sibling override field, checked first
        and falling back to the existing computed default, changes nothing about the existing
        guarantee for the common (unconfigured) case.
    *   **A real native folder picker (`@tauri-apps/plugin-dialog`'s `open({directory: true})`), not
        a raw text field.** `SPEC-303`'s existing `kicad_socket_path`/`freecadcmd_path_override`
        fields are plain text inputs — appropriate for a specific binary/socket path a user might
        copy from documentation, but a poor fit for "pick a folder," which is exactly the kind of
        interaction a native OS dialog exists for. This is a genuinely new capability, not a reuse of
        the existing Tier 2 text-field pattern.
    *   **Same "restart to apply" contract Tier 2 already established, not a live-reload.**
        `storage_root` is read once at daemon spawn (`spawn_daemon`, `CTX-304.1`) — changing it live
        mid-session would mean the running daemon and the just-saved override disagree about where
        data lives until the next restart regardless of UI cleverness. `SPEC-303` §3's own named risk
        (never letting a restart-required field look like it took effect immediately) applies here
        unchanged.
    *   **Falls back to the existing computed default on a failure to create/use the chosen
        directory** (permissions, a removable volume that's since been unmounted, etc.) rather than
        leaving the daemon unable to start. A real, recoverable failure mode, not a hypothetical one
        — external storage locations are exactly the kind of thing a real user picks and then loses.
*   **Data Flow / Interactions:**

    ```text
    Settings (Tier 2, extended):

      Storage location: ~/Library/Application Support/.../storage   [ Choose folder... ]
      These fields are only read at daemon startup -- restart the app to apply a change.
      [ Save ]

    "Choose folder..." --> @tauri-apps/plugin-dialog open({directory: true}) --> a real,
                            user-picked absolute path, shown in the field (not yet saved)
    "Save"             --> config::save_config_cmd writes storage_root_override to config.json
    Next app start      --> spawn_daemon's resolve_storage_root prefers storage_root_override
                            if set and creatable, else falls back to the existing computed default
    ```

*   **Cross-Module Impacts:**
    *   `core/tauri-rust`: `DaemonConfig` gains `storage_root_override`; `resolve_storage_root`
        gains an override parameter, tried first, falling back to `ensure_storage_root`'s existing
        computation on an empty override or a real failure to create/use it.
    *   `apps/tauri-ui`: Settings' Tier 2 section gains a storage-location field with a real "Choose
        folder..." button; adds `@tauri-apps/plugin-dialog` as a genuinely new dependency (unlike
        `CTX-306.1`'s discovery that `tauri-plugin-shell` was already present but unwired, this one
        needs adding from scratch on both the Rust and npm sides).
    *   `services/python-daemon`: none. `library_store.py` already reads whatever `storage_root` the
        daemon was spawned with; it has no opinion about how that value was chosen.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   **No migration path**, named above as an explicit Non-Goal — worth restating here since it's
        the single most likely point of user confusion ("I changed the location and my parts
        disappeared" is really "your parts are still at the old path, unmoved").
*   **Gotchas & Hazards:**
    *   **A chosen directory that later becomes unwritable or unmounted must fail closed to the
        existing default, not fail the daemon's own startup.** An external drive is a completely
        plausible real choice for a "where do my files live" picker; the daemon must still start
        without it.
    *   **The folder picker must not silently accept a location inside the app's own bundle or a
        read-only system directory** — `plugin-dialog`'s picker doesn't know to prevent this on its
        own; validating the chosen path is writable (a real, attempted directory creation, not just a
        string check) belongs on the save path, not assumed from the dialog alone.
    *   **This inherits `CTX-304.1`'s own already-recorded Plan Drift**, not just `SPEC-304`'s
        original text: the `.index/` SQLite cache and KiCad `.kicad_sym`/`.pretty` import/export were
        both deferred there. Relocating `storage_root` doesn't touch either — it changes *where* the
        existing file tree lives, not what's in it.

## 4. Module Map & Reference Links

*   [SPEC-106](SPEC-106-configuration-secrets-store.md) — the `config.json` override mechanism
    (`freecadcmd_path_override`/`kicad_socket_path`) this spec's `storage_root_override` reuses.
*   [SPEC-304](../apps/tauri-ui/specs/SPEC-304-project-library-storage.md) — the consumer whose
    currently-fixed `storage_root` resolution this spec makes configurable; its own `CTX-304.1` Plan
    Drift explicitly named and deferred this exact decision.
*   [SPEC-303](../apps/tauri-ui/specs/SPEC-303-settings-ui.md) — the Settings screen this spec's
    folder-picker field extends (Tier 2's existing "restart to apply" contract, reused unchanged).
*   [CTX-307.1](../apps/tauri-ui/context/CTX-307.1-part-detail-library-export.md) — the real,
    hands-on verification that surfaced this gap directly (an exported `.kicad_sym`'s real, buried
    path), named in its own Plan Drift as a follow-up rather than fixed inline there.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-110] Configurable Storage Root
          └── [Context 110.1] (not yet written)
```

## 5. User & Interaction

*   **Product Stage:** Settings — app-level configuration, not scoped to any one product stage.
*   **What the user is trying to accomplish:** Know where their parts library and project files
    actually live on disk, and choose a location they can find, back up, or sync themselves, instead
    of a fixed path buried in the OS's own application-support directory.
*   **What the user sees and does:** Settings' existing Tier 2 section (KiCad/FreeCAD paths) gains a
    storage-location field showing the current real path, with a "Choose folder..." button that opens
    a real native folder picker. Saving and restarting the app moves all future library/project
    writes to the chosen location; nothing already written moves automatically.

---
id: SPEC-312
title: "Application Shell, Project Portability & Persistence Model"
status: Completed
type: Feature
created: 2026-08-19
last_updated: 2026-08-19
target_version: v0.2.0
location: "apps/tauri-ui/specs/SPEC-312-application-shell-project-portability-persistence.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs:
  - "SPEC-333-project-save-semantics-and-rename.md"
user_facing: true
---

# SPEC-312: Application Shell, Project Portability & Persistence Model

## 1. Executive Summary & Goals
*   **High-Level Goal:** Three real, connected product questions that `CTX-311.13`'s own narrow
    scope deliberately deferred (`ROADMAP.md` §3.3), resolved here: what "Save Project" actually
    writes and means, distinct from the already-shipped "Export Enclosure" action; moving a
    project's own view-state out of the app's per-machine `$APPDATA` and into the project's own
    directory, so a project genuinely travels with its folder; and building the native
    `File`/`Edit`/`View`/`Help` menu that has never existed in `core/tauri-rust`, in any build mode.
*   **Business / Technical Value:** Today, "save" has no single real meaning in this app --
    `project.json` exists but is largely unused, generated Enclosure previews live in a per-machine
    temp/output directory (`SPEC-301` §2's `output_dir`), and there is no menu-driven way to open a
    project not already in the sidebar, or to Save/Save As/Duplicate one. A user who copies their
    project folder to another machine today loses all of that state silently. This spec makes
    "save" mean one real thing, makes a project's own state travel with its folder, and gives the
    app a real native menu shell instead of none.
*   **Non-Goals:**
    *   The Overview tab's own purpose (a per-project dashboard vs. a cross-project landing page,
        `ROADMAP.md` §3.3 item 4) -- a real, undecided, but *separate* feature decision from
        persistence/portability. Left for its own future spec.
    *   Component library discovery/search against an external service (`ROADMAP.md` §3.3 item 5)
        -- not yet named precisely; needs its own research before it can be scoped at all.
    *   Code signing/auto-update packaging of the resulting `.app` (`SPEC-402`) -- out of scope
        here; this spec only defines what gets saved and where, not how the app itself ships.
    *   A real `.index/` SQLite cache, database, or sync mechanism -- `SPEC-304`'s own "files are
        truth" convention (`library_store.py`'s own module docstring) is unchanged by this spec;
        portability here means real files in a real, user-visible directory, not a new storage
        engine.

## 2. System Architecture & Design Choices
*   **Design Rationale:**
    *   **Save Project + Export, not three actions.** `project.json` becomes a real manifest: real
        file locations (schematic/pcb/library paths already known to the daemon), the most recent
        real generated-result summary per area tab (Enclosure's own `wall_thickness_mm`/etc. and its
        last real `glb_path`/`step_path`, not the files themselves), and a real export history (each
        entry `exportEnclosure` -- `CTX-311.13` -- already produces, since a "keep this" export is
        the one real event worth recording permanently). "Save Project" writes this manifest;
        `CTX-311.13`'s already-shipped "Export Enclosure" stays exactly as it is today, a separate,
        explicit "keep this specific file at a user-chosen location" action -- not folded into Save,
        and not duplicated as a second "Save Enclosure" action. Generate itself remains a cheap,
        repeatable preview step with no save side effect at all, matching `CTX-311.2`'s own
        already-established precedent.
    *   **Project directory, not `$APPDATA`, for a project's own state.** `SPEC-304`'s `Project`/
        `Artifact` records and `SPEC-301`'s `output_dir`-based generated previews currently both
        live under this app's own per-machine `storage_root` (`library_store.py`'s own documented
        `<storage_root>/projects/<name>/` layout), entirely separate from wherever the real KiCad
        project files (`.kicad_pcb`/`.kicad_sch`) actually live on disk. This spec moves what's
        real, user-meaningful state -- the `project.json` manifest above, and view-state like the
        last-picked PCB path or camera position -- into a real subdirectory alongside those KiCad
        files (e.g. a project-root-relative folder, name TBD in context), so copying that folder to
        another machine and reopening it there restores the same state. Purely regenerable build
        output (a Generate preview's transient `.glb`/`.step`, never a "keep this" result) stays in
        a per-machine temp/output location -- portability applies to real state, not to files a
        fresh Generate click reproduces byte-for-byte anyway.
    *   **A real native menu, not a dev-build placeholder.** `tauri::menu` gets a real
        `File`/`Edit`/`View`/`Help` menu wired into `core/tauri-rust`, in every build mode --
        confirmed while scoping `CTX-311.13` that none exists today, anywhere. `File` is the real,
        natural home for Save Project/Save As/Duplicate Project and "Open a project not currently in
        the sidebar" -- all currently-missing capabilities this spec's own portability model needs a
        real entry point for anyway.
*   **Data Flow / Interactions:** A future `CTX-312.x` phase plan defines the real manifest schema,
    the exact project-relative directory name/layout, and the Rust `tauri::menu` wiring -- this
    spec fixes the goal and the three real decisions above, not the file format.
*   **Cross-Module Impacts:**
    *   `apps/tauri-ui` -- Save Project/Save As/Duplicate UI, reading/restoring project-relative
        view-state on open.
    *   `core/tauri-rust` -- the native menu itself (`tauri::menu`), and resolving the project's own
        on-disk directory (already partially known via `SPEC-304`'s storage-root work) to a
        project-relative state path.
    *   `services/python-daemon` -- `library_store.py`'s `save_project`/`load_project` and the
        `project.json` schema (`SPEC-300` §2.1) grow real fields; `freecad_bridge.py`/`kicad_cli.py`'s
        existing `output_dir` convention (`SPEC-301` §2) is unaffected -- transient build output
        stays exactly where it is today.

## 3. Known Constraints & Risks
*   **Known Issues / Technical Debt:** Today's `storage_root`-based `Project`/`Artifact` records
    (`SPEC-304`) predate this spec and are real, shipped, in-use data -- any migration to a
    project-relative layout needs a real, honest compatibility story for projects created before
    this spec ships, not a silent format change that strands them.
*   **Gotchas & Hazards:** A project-relative state directory living inside a user's own KiCad
    project folder needs a real, deliberate `.gitignore`-style convention decision (checked into the
    user's own version control alongside their KiCad files, or explicitly excluded) -- this spec
    does not assume an answer, since it affects what "portable" actually means for a user who
    already version-controls their PCB project.

## 4. Module Map & Reference Links
```text
[Root Spec](../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-300](SPEC-300-product-ia-interaction-model.md)
          └── [This Spec](SPEC-312-application-shell-project-portability-persistence.md)
                 └── [Context 312.1](../context/CTX-312.1-subfeature.md)
```

## 5. User & Interaction
*   **Product Stage:** Cross-cutting -- the app shell itself (the native menu) and every area tab
    that currently generates or exports something (Enclosure today; Schematic/PCB potentially later)
    that a user would expect "Save" to remember.
*   **What the user is trying to accomplish:** Two real, distinct goals. First, know that clicking
    "Save Project" actually keeps something real and meaningful, without having to separately
    remember whether they already used "Export" on whatever they were just looking at. Second, take
    their project folder to another machine (a new laptop, a shared drive, a teammate) and pick up
    exactly where they left off -- not just the KiCad files, but which board was selected, what an
    enclosure's own last-generated parameters were, and where they last exported it.
*   **What the user sees and does:** A real "Save Project" action (menu item and/or a real button,
    design TBD in context) that writes the manifest described in §2. A real native menu bar
    (`File`/`Edit`/`View`/`Help`) with Save/Save As/Duplicate Project and "Open a project not
    currently in the sidebar." Reopening a project on a different machine (or after a reinstall)
    restores its last-known state from files that traveled with the project's own folder, instead of
    starting cold.

---
id: SPEC-304
title: "Project & Library Storage"
status: Draft
type: Module
created: 2026-08-12
last_updated: 2026-08-12
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-304-project-library-storage.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: false
---

# SPEC-304: Project & Library Storage

## 1. Executive Summary & Goals

*   **High-Level Goal:** Give `SPEC-300`'s six persisted objects (Project, Part, Symbol, Footprint,
    Artifact, Conversation) a real, file-based home: a shared `library/` a user can reuse across
    projects, a `projects/<name>/` per project, and a rebuildable SQLite index that exists only to
    make search fast — never the source of truth. Every other `3xx` spec that reads or writes one of
    these objects (`SPEC-305` onward) implements against this schema, not its own.
*   **Business / Technical Value:** Today, nothing persists. `App.tsx`'s `latestSchema` is a single
    React variable — generating a second component silently discards the first, and closing the app
    loses everything. `SPEC-300` names this directly (§1): "objects that don't persist aren't
    objects." This spec is what makes a Part, a Project, or a generated enclosure something the user
    can leave and come back to, reuse across projects, and inspect/diff/commit as plain files —
    matching how KiCad's own project files already work, not inventing a parallel convention.
*   **Non-Goals:**
    *   **Not the UI.** `SPEC-305` (shell/navigation), `SPEC-306` (discovery), `SPEC-307` (part
        detail/library export) render and mutate this storage; this spec defines the schema, the
        directory layout, and the index contract they read/write against — no screens.
    *   **Not board-outline/mounting-hole extraction.** `SPEC-109` reads geometry out of a KiCad
        board; this spec only defines where the resulting `Artifact` gets stored, not how it's
        produced.
    *   **Not supplier API caching.** `SPEC-203` (Supplier API Integration) was explored and retired
        2026-08-18 — see its tombstone; §4's own standing rules forbid persisting any distributor
        API response at all, so there is no "supplier-sourced data cache" to be out-of-scope of in
        the first place. This spec's `datasheets/` cache is for a Part's own datasheet PDF only, not
        a general HTTP response cache.
    *   **Not resolving where the project root lives on disk.** `PRODUCT-PLAN.md` §8's open question
        (user-chosen on first run vs. a fixed default under the app data dir) is named in §3 as an
        open question this spec inherits, not one it decides unilaterally — it affects `SPEC-106`
        too, which already owns one config surface for exactly this kind of choice.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **Files are truth; the index is a cache.** Per `PRODUCT-PLAN.md` §4:
        ```text
        <project-root>/
          library/
            parts/<part-id>.part.json      # references a symbol and a footprint by id
            symbols/                        # exportable as a KiCad .kicad_sym library
            footprints/                     # exportable as a KiCad .pretty library
            datasheets/<part-id>.pdf        # cached alongside its source URL
          projects/
            <project-name>/
              project.json                  # metadata, KiCad project link, component refs
              conversation.jsonl
              artifacts/enclosure_*.glb
          .index/                           # SQLite -- rebuildable, never authoritative
        ```
        Readable JSON a user can inspect, diff, and commit; a shared library folder that's useful
        even outside this app; a SQLite index that exists only to make cross-project search fast and
        can be deleted and rebuilt at any time without losing data. This is a deliberate rejection of
        a single opaque database file — the same tradeoff KiCad itself already makes with its own
        project files.
    *   **The six objects, schema-level, per `SPEC-300` §2.1:**
        *   **Part** (`library/parts/<id>.part.json`): part-number-level — manufacturer, package
            name, pins, datasheet URL + local cache path, and **provenance** (required, not
            optional, per `SPEC-300` §2.2: source, model/version, timestamp, confidence per field).
            References exactly one Symbol and one Footprint by id; the Footprint reference may be
            null — a Part with pins and a datasheet is useful before any Footprint exists
            (`SPEC-300` §2.1).
        *   **Symbol** (`library/symbols/<id>.kicad_sym`-mapped record): mirrors a real KiCad symbol.
            Global — outlives any single Part that currently references it conceptually, though
            today's schema doesn't yet need many-to-one symbol sharing the way footprints do.
        *   **Footprint** (`library/footprints/<id>.kicad_mod`-mapped record): mirrors a real KiCad
            footprint. Global and **shared by many Parts** — SOIC-8 is one Footprint record, not one
            per Part that happens to use it (`SPEC-300` §2.1's explicit cardinality call).
        *   **Project** (`projects/<name>/project.json`): a named workspace holding *references* to
            library Parts (not copies), its own Artifacts, and a link to a KiCad project directory
            on disk.
        *   **Artifact** (`projects/<name>/artifacts/*`): a generated file bound to a project and a
            stage — `.glb`/`.stl`/`.step`/an advisor report. Carries the one real gap found when
            `SPEC-304`'s ID conflict was resolved (`ROADMAP.md` §3.3): **enclosure revisions must be
            trackable alongside the board revision they were generated against** — not in the
            original `PRODUCT-PLAN.md` storage section, carried forward here as a required field
            (e.g. a `board_revision` or content-hash reference on the Artifact record), not dropped.
        *   **Conversation** (`projects/<name>/conversation.jsonl`): per-project chat history,
            append-only.
    *   **Provenance is a required field on Part, not enforced by convention.** `SPEC-300` §2.2/§9
        names the exact failure mode this must avoid: if the schema *allows* an unprovenanced field,
        it will ship that way under time pressure and the trust argument evaporates. The Part JSON
        schema itself must reject a field with no source/confidence, not merely document that it
        should have one.
    *   **Index rebuild is cheap and runs on startup when stale.** `.index/`'s only job is fast
        cross-project search (`PRODUCT-PLAN.md` §4's own named cost); it is never read as the
        authoritative record for anything, and deleting it must be a safe, recoverable operation at
        any time, by rebuilding from the real files.
*   **Data Flow / Interactions:**

    ```text
    Library (parts/symbols/footprints/datasheets)      Project (per name)
       │  read by SPEC-306 (discovery), SPEC-307         │  read/written by SPEC-305 (shell),
       │  (part detail/export), SPEC-308 (footprints)    │  the Conversation by Overview
       ▼                                                  ▼
    Real files on disk, JSON + KiCad-native formats  ──> .index/ (SQLite, rebuildable cache)
                                                            │
                                                            ▼
                                                    Cross-project search / "no context yet"
                                                    -style queries SPEC-305/306 need fast
    ```

*   **Cross-Module Impacts:**
    *   `apps/tauri-ui`: every `3xx` spec from `SPEC-305` onward reads/writes this schema instead of
        inventing its own persistence.
    *   `services/python-daemon`: `SPEC-202`'s component-extraction output becomes a Part record —
        that spec's own re-scope (`PRODUCT-PLAN.md` §5.2) is adding provenance/confidence to match
        this schema, not this spec's job to backfill.
    *   No impact on `core/tauri-rust` process supervision or the daemon's JSON-RPC transport.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   **This spec's own scope was born from an ID collision, not a clean slate.** `ROADMAP.md`
        §3.3 records that `SPEC-304`'s number was originally a different, unwritten backlog entry
        ("Project & Workspace Model" — KiCad-project binding, artifact placement, enclosure-revision
        tracking). That entry was absorbed into this scope rather than renumbered; the enclosure-
        revision-tracking requirement above is the one piece that didn't already exist in
        `PRODUCT-PLAN.md`'s own storage section and must not be silently dropped when this spec is
        implemented.
*   **Gotchas & Hazards:**
    *   **The library schema is the single most-depended-on artifact in this whole plan.**
        `PRODUCT-PLAN.md` §9 names this directly: get it wrong and every stage inherits the mistake.
        Worth versioning the file format from day one (e.g. a `schema_version` field on every
        record) so a future migration has something to branch on, rather than guessing a file's
        vintage from its shape.
    *   **Provenance-as-required is a schema decision, not a UI decision.** If the JSON schema
        itself doesn't reject a Part record missing provenance, every downstream promise in
        `SPEC-300` §2.2 (show the user why, let a correction stick, refuse on low confidence) has
        nothing to enforce it.
    *   **Project root location is inherited as an open question, not resolved here.**
        `PRODUCT-PLAN.md` §8 raises it explicitly and names both `SPEC-304` and `SPEC-106` as
        affected. Implementing this spec's directory layout requires an answer before the first line
        of code, even though deciding it isn't this spec's own job to do alone — coordinate with
        whoever picks up `SPEC-106`'s config surface for it, don't default silently.
    *   **Index staleness detection needs a real, cheap check, not a guess.** "Rebuild on startup
        when the file tree is newer than the index" (`PRODUCT-PLAN.md` §4) implies a real mtime or
        hash comparison across potentially many files — the actual mechanism is this spec's own call
        to make, not assumed to be trivial.

## 4. Module Map & Reference Links

*   [PRODUCT-PLAN.md](../../../PRODUCT-PLAN.md) §4, §5.1, §8, §9 — the storage layout, the spec-plan
    entry this formalizes, the inherited open questions, and the risk this spec is most exposed to.
*   [SPEC-300](SPEC-300-product-ia-interaction-model.md) §2.1/§2.2 — the six objects and the
    provenance requirement this spec turns into a real schema.
*   [ROADMAP.md](../../../ROADMAP.md) §3.3 — this spec's backlog entry, including the ID-collision
    resolution and the enclosure-revision-tracking requirement it carries forward.
*   [SPEC-106](../../../specs/SPEC-106-configuration-secrets-store.md) — the existing config surface
    the inherited project-root-location question also touches.
*   [SPEC-202](../../../services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) —
    the pipeline whose output becomes a Part record once its own provenance re-scope lands.
*   `SPEC-305`-`SPEC-310` *(not yet written — no files to link to)* — every one of them reads or
    writes this schema.

```text
[SPEC-300] Product IA & Interaction Model
   └── [SPEC-304] Project & Library Storage
          └── [Context 304.1] (not yet written)
```

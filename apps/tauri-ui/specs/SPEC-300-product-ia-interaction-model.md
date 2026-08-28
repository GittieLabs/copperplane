---
id: SPEC-300
title: "Product IA & Interaction Model"
status: Draft
type: System
created: 2026-08-11
last_updated: 2026-08-11
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-300-product-ia-interaction-model.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs:
  - "SPEC-304-project-library-storage.md"
  - "SPEC-305-app-shell-navigation.md"
  - "SPEC-306-component-discovery.md"
  - "SPEC-307-part-detail-library-export.md"
  - "SPEC-308-footprints-schematic-advisor.md"
  - "SPEC-309-board-advisor.md"
  - "SPEC-310-enclosure-from-board-profile.md"
  - "SPEC-311-enclosure-refinement-interactive-preview.md"
  - "SPEC-312-application-shell-project-portability-persistence.md"
  - "SPEC-313-overview-tab-project-dashboard.md"
  - "SPEC-314-community-library-discovery.md"
  - "SPEC-315-library-browsing-and-organization.md"
  - "SPEC-316-native-menu-command-surface.md"
  - "SPEC-317-theme-system.md"
  - "SPEC-318-in-context-agent-chat-and-review.md"
  - "SPEC-322-model-role-legibility.md"
  - "SPEC-323-advanced-agent-configuration.md"
  - "SPEC-324-model-identity-verification.md"
user_facing: true
---

# SPEC-300: Product IA & Interaction Model

## 1. Executive Summary & Goals

*   **High-Level Goal:** Replace the per-capability UI (one text box string-matched into
    `generate`/`inject`/chat, a raw JSON dump, nothing persisted) with a real information
    architecture: persistent objects (Project, Part, Symbol, Footprint, Artifact, Conversation), a
    navigable shell (Projects + Library rail, per-project area tabs), a stage machine for how work
    actually flows (Discovery → Detail → Schematic → PCB → Enclosure), and one governing rule for
    what a text input means in any given screen. This spec is the parent for every `3xx` spec that
    follows it — the domain model, the stages, the navigation rule, and the AI boundary all live
    here once, instead of being re-derived per child spec.
*   **Business / Technical Value:** `PRODUCT-PLAN.md` §1 traces three visible failures — the same
    text box doing three unrelated things via string-matching, no persisted objects (`latestSchema`
    is one variable; a second `generate` call discards the first), and unlabeled/unrendered UI — back
    to one root cause: every spec written through `SPEC-302` answers *"can the machine do X,"* none
    answers *"what is the user doing."* `CTX-901.2`'s `## 5. User & Interaction` gate makes that
    question mandatory per spec; this spec is the first real answer at the product-architecture
    level, not just per-surface. Twelve merged PRs proved the backend capabilities are real and
    verified — this spec is the organizing layer above them that was missing, not a rewrite of any
    of it (`PRODUCT-PLAN.md` §7).
*   **Non-Goals:**
    *   **Not a schematic editor or a PCB editor.** The Schematic and PCB stages show a component
        with its pins/errors and explain what to do; they do not replace KiCad's own editors. The
        product is an advisor with hands, not a CAD tool (`PRODUCT-PLAN.md` §2.3).
    *   **Not auto-layout or assisted routing.** Explicitly out of scope until every stage below is
        solid (`PRODUCT-PLAN.md` §9).
    *   **Not a daemon rewrite.** `services/python-daemon`'s routes (`kicad.*`, `freecad.*`,
        `llm.chat`) are re-housed behind this IA, not rebuilt. If implementing a child spec starts
        rewriting daemon internals, it has gone off this spec's plan (`PRODUCT-PLAN.md` §7).
    *   **Not the concrete schemas, storage layout, or shell markup.** Those are `SPEC-304`
        (storage) and `SPEC-305` (shell) — this spec fixes the model and the rules they implement
        against, not their file formats or component trees.
    *   **Not footprint sourcing, board-advisor mechanics, or enclosure-from-geometry.** Those are
        `SPEC-308`/`SPEC-309`/`SPEC-310` respectively — named here only as consumers of the stage
        machine this spec defines.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **Six persisted objects, not one JSON blob.** Project (a named workspace referencing library
        parts, its artifacts, and a KiCad project directory), Part (part-number-level: manufacturer,
        package, pins, datasheet + cached PDF, provenance — outlives any project), Symbol (mirrors a
        KiCad `.kicad_sym`, global), Footprint (mirrors a KiCad `.kicad_mod`, global, **shared by
        many parts** — SOIC-8 is one footprint, not one per part), Artifact (a generated file bound
        to a project and a stage: `.glb`/`.stl`/`.step`/an advisor report), Conversation (per-project
        chat history). Symbols and footprints are kept as separate objects, exactly as KiCad models
        them, rather than inventing a combined "component" — collapsing them would duplicate
        footprint geometry per part, break footprint reuse, and produce an export that doesn't map
        onto KiCad's own two library types. A direct consequence: creating a Part and creating its
        Footprint are separate user actions with separate flows, and the latter can be skipped — a
        Part with pins and a datasheet is useful before any Footprint exists.
    *   **Provenance is a required field, not an optional one.** Every field on a Part records its
        source (datasheet PDF, supplier API, model inference), the model/version that produced it,
        when, and a confidence signal. This is what makes three things possible that the current
        build cannot do: show the user *why* a value is what it is; let a user correction outrank
        the inference and stick; and refuse to proceed when confidence is too low, with a specific
        reason. `PRODUCT-PLAN.md` §9 names the failure mode directly: if provenance is optional, it
        gets skipped under time pressure and the trust argument evaporates — so child specs
        (`SPEC-304`'s schema in particular) must make it a required field, not an enforced-by-review
        convention.
    *   **The stage machine is a DAG, not a wizard.** Every stage (Component Discovery → Component
        Detail → Schematic Advisor → PCB Advisor → Enclosure) is enterable directly, and every stage
        accepts a file import (a part number/datasheet, a `.kicad_sch`, a `.kicad_pcb`) as an
        alternative to inheriting from the previous stage. Stage 2 loops back to stage 1 — adding
        components one at a time, into a shared Library, is the common path, not an edge case — see
        the diagram below.
    *   **The interaction rule that fixes the reported bug:** *a text input inside a stage is a
        parameter to that stage's function; it is never a command line.* In Component Discovery,
        typing is a search query and can only ever produce candidate Parts. In Overview, typing is
        conversation and can only ever produce a reply. The same widget carries two unambiguous
        meanings because the surrounding screen disambiguates, not a parser —
        `apps/tauri-ui/src/lib/commands.ts`'s `parseCommand` is deleted under this model, not
        improved (`PRODUCT-PLAN.md` §3.2, §7).
    *   **A fixed boundary on what the AI is allowed to do**, so every child spec inherits the same
        answer instead of re-deciding it per surface: the AI searches/ranks/extracts/explains/asks
        for clarification/converses on any conversation surface; the AI never decides which screen
        the user is on, never silently corrects input, never writes to a board without explicit
        confirmation, and never returns prose where a typed result is expected outside a conversation
        surface — and a conversation surface itself can only ever produce an answer, never advance a
        stage, mutate a record, dispatch a flow step, or change which screen the user is on. Two
        disciplines follow directly: every AI step inside a deterministic flow returns a typed
        result, not prose; and ambiguity surfaces as a structured choice (a *did you mean* card with
        a datasheet link and a confidence note that the user confirms) rather than a silent
        substitution — the exact failure mode from `PRODUCT-PLAN.md` §1 ("generate atiny85" silently
        producing a correct ATtiny85 by luck, with nothing surfacing that a correction occurred).

        > **Amendment (2026-08-21):** this originally read "converses (in Overview only)" and "never
        > returns prose where a typed result is expected outside Overview." `SPEC-318` gives every
        > area its own scoped conversation surface and argues, at its §2.1, that the load-bearing
        > half of the old rule was never *where* prose lived but *what a conversation surface is
        > permitted to do* — the text above states that replacement invariant directly.
        > `PRODUCT-PLAN.md` §3.3 carries the same amendment.
    *   **Settings gets a fixed home in the rail, resolved 2026-08-11.** `SPEC-303` named this as an
        open question rather than deciding it unilaterally: the rail already has exactly one other
        thing that isn't project-scoped (the Library), so Settings anchors beside it — a persistent
        item at the bottom of the rail, not inside any project's area tabs. Selecting it swaps the
        main content area the same way selecting a project's own tab does, but renders no area-tab
        row, since Settings has no stages under it. See the shell diagram below.
*   **Data Flow / Interactions:**

    ```text
    Stage machine (PRODUCT-PLAN.md §2.3) -- a DAG, not a wizard:

       import part # / datasheet PDF                import .kicad_sch      import .kicad_pcb
                  |                                        |                   |       |
                  v                                        v                   v       v
       [1] Component Discovery ---> [2] Component Detail ---> [3] Schematic ---> [4] PCB ---> [5] Enclosure
            search, rank,               pins, guidance,           Advisor          Advisor      profile -> body
            disambiguate                footprint, export             |                 |
                  ^                          |                        |                 |
                  |                          v                        |                 |
                  +----- repeat per part --  Library  <---------------+-----------------+

    Shell (PRODUCT-PLAN.md §3.1) -- what the user actually navigates:

    +----------------+------------------------------------------+
    |  PROJECTS      |                                          |
    |   > Weather PCB|   [ Overview ] [ Components ] [ Schematic ] [ PCB ] [ Enclosure ]
    |     Doorbell   |                                          |
    |                |   ( the selected area's own surface )    |
    |  LIBRARY       |                                          |
    |   Components   |                                          |
    |   Footprints   |                                          |
    |                |                                          |
    |  [gear] Settings|  ( full main-area swap, no area tabs -- |
    +----------------+     it's app-level, not project-scoped ) +
    ```

    Overview is the project summary plus the freeform Conversation with history — chat as a
    *place*, not a router. The Library sits outside any project, because Parts/Symbols/Footprints
    are reusable across projects by design. **Settings (`SPEC-303`) anchors at the bottom of the
    rail, always visible regardless of which project is selected** — resolves the open question
    `SPEC-303` itself named: it's app-level, so it belongs beside Projects/Library, not inside any
    project's own area tabs. Selecting it swaps the main content area the same way a project's tabs
    do, but with no area-tab row, since Settings has no stages under it. Selecting a project again
    restores that project's previously-selected area.
*   **Cross-Module Impacts:**
    *   `apps/tauri-ui`: this is the spec the whole shell/navigation/stage rendering (`SPEC-305`) and
        every per-stage surface (`SPEC-306`-`SPEC-310`) implement against. `App.tsx`'s current
        single-input/single-button shape does not survive this model unchanged.
    *   `services/python-daemon`: no route rewrite, but `SPEC-202`'s component-extraction output
        becomes the Part object's data — it currently returns a bare schema with no provenance or
        per-field confidence, both required by §2's model. That gap is `SPEC-202`'s own re-scope
        (`PRODUCT-PLAN.md` §5.2), not this spec's, but this spec is what makes the gap load-bearing
        rather than cosmetic.
    *   No impact on `core/tauri-rust` process supervision, the daemon's JSON-RPC transport, or any
        `1xx` platform spec — `PRODUCT-PLAN.md` §5.3 confirms the whole platform layer is unaffected.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   **Two existing `3xx` specs are not yet re-parented under this one.** `SPEC-301` (3D Viewer,
        survives as-is, becomes a component of the Enclosure stage) and `SPEC-302` (Chat & Command
        Surface, re-scoped to Project Conversation) both currently declare `parent_spec: SPEC-000`
        directly, predating this spec. Whether they should be re-parented to `SPEC-300` is a real
        structural decision (it changes `SPEC-000`'s own `child_specs`, not just this spec's) —
        deliberately **not** made here, to keep this spec's own scaffolding from silently rewriting
        two already-shipped specs' link graph. `SPEC-304` and `SPEC-305` (both written 2026-08-12)
        are the first concrete children actually wired into `child_specs` below, since they're new
        rather than pre-existing. `SPEC-306` and `SPEC-307` (both written 2026-08-12) are the third
        and fourth; `SPEC-308`-`SPEC-310` remain unwritten, and listing any of them would be a
        dangling link the validator (`SPEC-902`) would correctly reject.
    *   **`SPEC-304`'s ID conflict is resolved, not renumbered.** `ROADMAP.md` §3.3 used to carry an
        unwritten backlog entry `SPEC-304 Project & Workspace Model`, a different scope than
        `PRODUCT-PLAN.md` §5.1's `SPEC-304 Project & Library Storage` under the same ID. Resolved
        2026-08-11 by absorbing the old entry into the new one (~90% overlap; the plan's
        `project.json`/`artifacts/` layout already covers the old entry's "which KiCad project" and
        "artifacts next to the project" concerns) rather than renumbering either — see `ROADMAP.md`
        §3.3's `SPEC-304` entry for the one real gap (enclosure-revision tracking) carried forward as
        a named requirement for this spec's Artifact schema.
*   **Gotchas & Hazards:**
    *   **This spec can become a design document nobody implements against** if it grows
        screen-by-screen detail that belongs in child specs (`PRODUCT-PLAN.md` §9's stated risk).
        Kept here to: the six objects, the stage DAG, the two interaction rules (text-input-as-
        parameter, AI-boundary), and provenance-as-required. Pin diagrams, footprint search UX,
        ERC/DRC explanation copy, and file-format details all belong to `SPEC-306`-`SPEC-310`.
    *   **Provenance is specified here as a requirement, not enforced by this spec.** Enforcement is
        a schema-validation concern for `SPEC-304`, which names the same requirement explicitly
        (§2, §3) but hasn't implemented a schema yet either. If that implementation ships with
        provenance optional, this spec's §2.2 rationale is defeated silently — worth checking
        explicitly once real code exists, not assumed from either spec's prose.
    *   **Five open questions from `PRODUCT-PLAN.md` §8 were inherited, not answered, by this spec.**
        Two are resolved now: project root location (`SPEC-304`, `CTX-304.1`) and whether `SPEC-307`
        generates a real `.kicad_sym` or defers it (`SPEC-307` resolves: a real, standalone file
        write, not blocked by `kipy`'s KiCad-11-only `Schematic` class since it needs no live IPC
        session). Three remain open, each still belonging to the child spec named, not this one:
        `kicad-cli` binary presence (`SPEC-309`), live IPC vs. reading `.kicad_sch` from disk for the
        Schematic Advisor (`SPEC-309`, reopens a decision `SPEC-103` deliberately closed), and
        footprint source ranking (`SPEC-308`).
    *   **Re-housing risk.** `PRODUCT-PLAN.md` §7 is deliberately conservative about what moves where
        (`App.tsx` becomes the shell; `EnclosurePanel` moves into the Enclosure area with labels;
        `EnclosureViewer` and the job client are kept unchanged). A child spec that starts rewriting
        `EnclosureViewer` or the daemon's job protocol instead of re-housing them has gone off this
        model, not implemented it.

## 4. Module Map & Reference Links

*   [PRODUCT-PLAN.md](../../../PRODUCT-PLAN.md) — the approved plan this spec formalizes. §2 is this
    spec's §2 design rationale; §3 is this spec's navigation/AI-boundary rationale; §8/§9 are this
    spec's inherited open questions and risks.
*   [ROADMAP.md](../../../ROADMAP.md) §3.3 — the backlog entries this spec's children (`SPEC-304`
    onward) fill in. The `SPEC-304` ID conflict noted there is resolved (absorbed, see §3 above).
    `SPEC-303` is now written too, with its own real `## 5. User & Interaction` section — it's still
    unaddressed by `PRODUCT-PLAN.md` itself, which is a plan-document gap, not a blocking one.
*   [SPEC-301](SPEC-301-3d-viewer.md) — survives as-is per `PRODUCT-PLAN.md` §5.2; not yet
    re-parented under this spec (see §3 above).
*   [SPEC-302](SPEC-302-chat-command-surface.md) — re-scoped to Project Conversation per
    `PRODUCT-PLAN.md` §5.2; not yet re-parented under this spec (see §3 above).
*   [SPEC-303](SPEC-303-settings-ui.md) — the one existing `3xx` spec that predates `SPEC-300` and
    is *also* not re-parented under it, same caution as `SPEC-301`/`SPEC-302` above.
*   [SPEC-304](SPEC-304-project-library-storage.md) — the storage schema for this spec's six
    objects; done (`CTX-304.1`) as of 2026-08-12.
*   [SPEC-305](SPEC-305-app-shell-navigation.md) — the shell that renders this spec's model for
    real; the second concrete child wired into `child_specs`.
*   [SPEC-306](SPEC-306-component-discovery.md) — the discovery/disambiguation stage; the third
    concrete child wired into `child_specs`.
*   [SPEC-307](SPEC-307-part-detail-library-export.md) — the part-detail/library-save/symbol-export
    stage; the fourth concrete child wired into `child_specs`.
*   [SPEC-202](../../../services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) —
    its output becomes this spec's Part object once provenance/confidence are added (its own
    re-scope, not this spec's); `SPEC-306` adds a sibling search capability alongside it, and
    `SPEC-307` re-runs it for real pin data.
*   `SPEC-308`-`SPEC-310` *(not yet written — no files to link to)* — the remaining concrete
    children: footprints/schematic advisor, board advisor, enclosure-from-geometry, per
    `PRODUCT-PLAN.md` §5.1.

```text
[SPEC-000] (Root Architecture)
   └── [SPEC-300] Product IA & Interaction Model
          ├── [Context 300.1] (not yet written)
          ├── [SPEC-304] Project & Library Storage -- done (CTX-304.1)
          ├── [SPEC-305] App Shell & Navigation -- done (CTX-305.1)
          ├── [SPEC-306] Component Discovery -- done (CTX-306.1)
          └── [SPEC-307] Part Detail & Library Export -- done (CTX-307.1)
```

## 5. User & Interaction

*   **Product Stage:** All of them — this spec is cross-cutting rather than owning one stage. It
    defines the shell every stage renders inside of (Overview/Components/Schematic/PCB/Enclosure
    tabs, plus the Projects/Library rail) and the rule that governs every stage's own text input.
*   **What the user is trying to accomplish:** Move from typing into one ad-hoc box that might
    generate a part, inject one into a board, or just chat — with no memory of what happened last —
    to working in a real workspace: pick or create a project, build up a library of parts that
    persist and are reusable across projects, and always know what a given screen's input field will
    do before typing into it.
*   **What the user sees and does:** A left rail listing Projects and the cross-project Library
    (Components, Footprints); selecting a project surfaces area tabs (Overview, Components,
    Schematic, PCB, Enclosure) for that project specifically. Overview holds the freeform
    conversation with history. Every other area's text input is a parameter to that area's own
    function — a search box in Components, never a command line — and an ambiguous result (e.g. a
    misspelled part number) always surfaces as a *did you mean* card to confirm, never a silent
    substitution.

---
id: SPEC-305
title: "App Shell & Navigation"
status: Draft
type: Feature
created: 2026-08-12
last_updated: 2026-08-12
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-305-app-shell-navigation.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-305: App Shell & Navigation

## 1. Executive Summary & Goals

*   **High-Level Goal:** Build the real shell `SPEC-300` §2 already designed: a Projects rail with
    real create/select, a Library entry, a Settings anchor at the bottom, and per-project area tabs
    (Overview/Components/Schematic/PCB/Enclosure) — replacing `App.tsx`'s current single-screen
    layout (one chat surface, a manually-toggled Settings button, a floating Enclosure panel) with
    real navigation backed by `SPEC-304`'s real Project storage.
*   **Business / Technical Value:** Every surface built so far is a temporary stopgap bolted onto a
    single-screen `App.tsx`: `CTX-108.3`'s "Inject into Board" button, `CTX-302.1`'s chat box,
    `CTX-303.1`'s Settings toggle. `PRODUCT-PLAN.md` §6 M2 names this spec as the thing that turns
    the app from "a demo" into "a product" — not by adding a new capability, but by giving the
    capabilities that already exist a real home instead of one more button on a list. Without this,
    `SPEC-304`'s Projects have nowhere to be created, selected, or seen.
*   **Non-Goals:**
    *   **Not Component Discovery.** `SPEC-306` builds the actual search/disambiguation flow. The
        Components area exists in this shell as a visible, explicitly-not-built placeholder.
    *   **Not the Schematic or PCB advisors.** `SPEC-308`/`SPEC-309` own those areas' real content.
        Both are visible, explicitly-not-built placeholders here too.
    *   **Not Library browsing.** `SPEC-307` owns the real part-detail/library-export screens. The
        Library rail entry in this spec is a placeholder pointing at real (if currently empty)
        `SPEC-304` data, not a full browsing UI.
    *   **Not choosing a routing library.** Whether view state is a router (e.g. a client-side
        router) or plain component state is an implementation call for this spec's own context, not
        a design decision this spec needs to make.
    *   **Not re-deciding where Settings anchors.** `SPEC-300` §2 already resolved this (bottom of
        the rail, beside Library); this spec builds it, not re-litigates it.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **The shell, exactly as `SPEC-300` §2 already specified it:** a left rail (Projects, then
        Library, then Settings anchored at the bottom) and a main content area showing whichever
        project's area tabs are selected — Settings swaps the main area with no area-tab row, since
        it has no stages under it. This spec is the first to actually render that model; `SPEC-300`
        only described it.
    *   **Visible-but-empty beats hidden (`PRODUCT-PLAN.md` §6).** Components, Schematic, and PCB
        all render as real tabs a user can click, each showing an explicit "not built yet" state
        naming what's coming — never omitted from the tab row and never a dead click. This is a
        deliberate, load-bearing decision: hiding an unbuilt area teaches a user nothing about what
        the product is becoming; showing it, empty, does.
    *   **Overview and Enclosure are not placeholders — they carry real, already-shipped content
        forward.** Overview gets the existing Conversation (per `SPEC-300` §5.2's `SPEC-302`
        re-scope: the chat half of the old single-screen surface, unchanged in substance, re-housed
        here). Enclosure gets the existing `EnclosurePanel`/`EnclosureViewer` moved in unchanged —
        `PRODUCT-PLAN.md` §6 is explicit that this is a re-housing, not a rebuild: "it works; it just
        needs labels and a home." Resolves an apparent tension in `PRODUCT-PLAN.md` §6's own wording
        (which lists Enclosure alongside PCB/Schematic as "present" in the new shell, then says two
        sentences later that its panel "moves in unchanged") by reading Enclosure as populated from
        day one, not a fourth placeholder.
    *   **Projects are real, not mocked.** Creating a project calls `SPEC-304`'s real
        `project.save`; the rail's project list calls `project.list`; selecting one calls
        `project.load`. No project ever exists only in React state the way `latestSchema` used to.
    *   **The Library rail entry is a real destination, not yet a real browsing UI.** It calls
        `SPEC-304`'s `library.list_parts` (genuinely showing however many Parts exist — zero on a
        fresh install, real ones once `SPEC-306`/`307` create them) but doesn't yet support opening
        one; that's `SPEC-307`'s job.
*   **Data Flow / Interactions:**

    ```text
    Shell (SPEC-300 §2, built for real here):

    +----------------+------------------------------------------+
    |  PROJECTS      |                                          |
    |   > Weather PCB|   [ Overview ] [ Components ] [ Schematic ] [ PCB ] [ Enclosure ]
    |     Doorbell   |                                          |
    |     + New...   |   ( the selected project's selected      |
    |                |     area, or a "not built yet" state )   |
    |  LIBRARY       |                                          |
    |   (N parts)    |                                          |
    |                |                                          |
    |  [gear] Settings|                                          |
    +----------------+------------------------------------------+

    Project rail  --project.list-->  real Project records (SPEC-304)
    "+ New..."     --project.save--> a new Project record, then selected
    Overview       --(existing llm.chat flow, re-housed, unchanged)
    Enclosure      --(existing freecad.generate_enclosure flow, re-housed, unchanged)
    Components/Schematic/PCB --> "Not built yet -- coming in SPEC-306/308/309" empty state
    ```

*   **Cross-Module Impacts:**
    *   `apps/tauri-ui`: the largest-surface-area change so far — `App.tsx`'s current
        single-screen layout is replaced by the shell described above. `Settings.tsx` moves behind
        the rail's anchor instead of a temporary toggle button; the existing chat logic and
        `EnclosurePanel` are re-housed into Overview/Enclosure respectively, not rewritten.
    *   `services/python-daemon`: none. This spec is pure frontend structure over routes `SPEC-304`
        (storage) and existing capabilities already provide.
    *   No impact on `core/tauri-rust` or the daemon's JSON-RPC transport.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   **`App.tsx`'s current chat surface conflates three routed functions in one input**, the
        exact bug this entire framework amendment (`CTX-901.2`) exists to catch going forward. This
        spec's Overview area inherits that conversation surface as-is for now — `SPEC-300` §2's
        interaction rule (a text input is a parameter to its stage's function, never a command line)
        still needs `apps/tauri-ui/src/lib/commands.ts`'s `parseCommand` actually deleted, which is
        `PRODUCT-PLAN.md` §7's explicit instruction and not yet done as of this spec.
*   **Gotchas & Hazards:**
    *   **"Re-housing, not a rebuild" is easy to violate by accident.** `PRODUCT-PLAN.md` §9 names
        this directly: a context implementing this spec that starts rewriting `EnclosureViewer` or
        the daemon's job-progress client instead of moving them into a new layout has gone off this
        spec's plan.
    *   **Empty states must say what's coming, not just that something's missing.** A bare "Not
        built yet" with no context repeats `PRODUCT-PLAN.md` §1's own cosmetic complaint (a wall of
        unlabeled UI) in a new shape. Each placeholder should name the spec that owns it.
    *   **Project switching must not leak state between projects.** Overview's conversation history
        and any per-project view state must be scoped to the selected project — switching projects
        and seeing the previous project's conversation would be a real, silent data-integrity bug,
        not a cosmetic one.
    *   **This spec inherits, and must not silently resolve, `SPEC-300` §3's still-open item:**
        whether `SPEC-301`/`SPEC-302`/`SPEC-303` get re-parented under `SPEC-300` now that a real
        shell exists to justify it. Left as a future call, same as `SPEC-300`/`SPEC-304` already
        left it.

## 4. Module Map & Reference Links

*   [SPEC-300](SPEC-300-product-ia-interaction-model.md) §2 — the shell model this spec builds for
    real; not re-decided here.
*   [SPEC-304](SPEC-304-project-library-storage.md) — the real Project/Part storage this spec's
    rail and Library entry read/write against.
*   [PRODUCT-PLAN.md](../../../PRODUCT-PLAN.md) §6 M2, §7, §9 — the milestone this spec is step 3
    of, the re-housing table for exactly what moves where, and the "re-housing turns into a rewrite"
    risk this spec's own §3 names.
*   [SPEC-302](SPEC-302-chat-command-surface.md) — the Conversation surface Overview re-houses
    unchanged; its own `parseCommand` still needs deleting, named here as inherited debt, not this
    spec's job to fix.
*   [SPEC-301](SPEC-301-3d-viewer.md) — the `EnclosureViewer` this spec's Enclosure area re-houses
    unchanged.
*   `SPEC-306`-`SPEC-309` *(not yet written — no files to link to)* — the specs that turn this
    spec's Components/Schematic/PCB placeholders into real areas.

```text
[SPEC-300] Product IA & Interaction Model
   └── [SPEC-305] App Shell & Navigation
          └── [Context 305.1] (not yet written)
```

## 5. User & Interaction

*   **Product Stage:** All of them, structurally — this is the shell every other stage renders
    inside of, the same cross-cutting scope `SPEC-300` itself has.
*   **What the user is trying to accomplish:** Create and switch between real, persistent projects;
    see at a glance which parts of the product exist today and which are coming; reach Settings from
    anywhere without it being a special-cased toggle; keep using the chat and enclosure-generation
    flows they already have, now inside a real workspace instead of a single floating screen.
*   **What the user sees and does:** A left rail listing their real projects (with a way to create a
    new one), a Library entry showing how many parts exist, and a Settings anchor at the bottom.
    Selecting a project surfaces its five area tabs; Overview and Enclosure work exactly as before
    (just re-housed), Components/Schematic/PCB each show a plain, specific "not built yet" state
    instead of being hidden or broken.

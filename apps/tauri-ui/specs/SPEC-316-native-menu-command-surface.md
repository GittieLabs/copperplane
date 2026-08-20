---
id: SPEC-316
title: "Native Menu Command Surface: Library, Design Actions & Settings Access"
status: Draft
type: Feature
created: 2026-08-20
last_updated: 2026-08-20
target_version: v0.2.0
location: "apps/tauri-ui/specs/SPEC-316-native-menu-command-surface.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-316: Native Menu Command Surface

## 1. Executive Summary & Goals
*   **High-Level Goal:** `CTX-312.3` gave `core/tauri-rust` a real but minimal native menu --
    `File`/`Edit`/`View`/`Help`, scoped tightly to `SPEC-312`'s own portability/persistence work
    (Save/Open Project, Quit, standard Edit, About). This spec grows that menu into the app's real
    command surface: opening a library (`SPEC-315`) from the menu bar, and grouped access to the
    per-area actions that `SchematicAdvisor.tsx`/`BoardAdvisor.tsx`/`EnclosurePanel.tsx` already
    expose only as in-view buttons today -- with those three areas' action sets expected to keep
    growing. It also relocates Settings access to the native menu.
*   **Business / Technical Value:** Right now the only way to reach Settings, or to run a
    Schematic/PCB/Enclosure action, is to already be looking at that exact screen. A user who wants
    "check schematic against KiCad" has no menu-driven path to it -- they must first navigate the
    sidebar to the right project and area tab. As each area's own action list grows (more Schematic
    checks, more PCB operations, more Enclosure generation options), that in-view-button-only model
    stops scaling: there is no consistent, discoverable home for "everything you can do," and no
    keyboard-accelerator path to any of it. This spec gives the app one real, growable answer.
*   **Non-Goals:**
    *   Building any *new* Schematic/PCB/Enclosure capability. This spec only gives already-real,
        already-shipped per-area actions (`handleOpenKicad`, `handleCheck`, `handleGenerate`,
        `handleConfirmExport`, etc.) a second, menu-driven entry point via the same frontend
        event-emit pattern `CTX-312.3` already established (`app.emit(...)` -> a `useEffect` listener
        in `App.tsx` calling the area component's existing handler). No new backend routes, no new
        daemon calls.
    *   A context-sensitive menu bar that changes contents based on which area tab is focused.
        macOS supports this, but it's real added complexity (tracking frontend focus state and
        pushing menu rebuilds from Rust) this spec does not need: the three submenus below are
        always present, and their items are simply disabled (not hidden) when their area's action
        isn't currently applicable (no project selected, no board picked, etc.) -- matching how a
        native app's Edit menu already stays present but grays out Cut/Copy when nothing is
        selected.
    *   Renaming or restructuring `File`/`Edit`/`Help`'s own existing items (`CTX-312.3`, already
        shipped) -- untouched here except for removing Quit/About if they move into the new
        App-name menu (see Design Rationale).
    *   A command palette / fuzzy-search launcher (`SPEC-302`'s chat surface already exists as a
        different kind of command entry point) -- this spec is about the *native OS menu bar*
        specifically, not a second in-app command UI.

## 2. System Architecture & Design Choices
*   **Design Rationale:**
    *   **One grouped "Design" menu with three submenus, not three top-level menus.** Considered
        both; chose the grouped form deliberately. `SchematicAdvisor`/`BoardAdvisor`/
        `EnclosurePanel` each already have 3-6 real actions and are expected to keep growing as
        those advisors gain capability -- three separate top-level menus today become four, five,
        six as more domains (e.g. a future Firmware area) get added, with no natural ceiling. A
        single `Design` menu containing `Schematic ▸`, `PCB ▸`, `Enclosure ▸` submenus keeps the
        top-level bar stable regardless of how many domains or actions-per-domain exist, at the
        real cost of one extra click of indirection to reach any single action. Accepted trade-off,
        confirmed directly with the user rather than assumed.
    *   **Library gets its own top-level menu, not a File submenu.** `Rail.tsx` (`SPEC-305`) already
        treats Library as a sidebar peer of Projects and Settings, not a child of either --
        `SPEC-315`'s own framing ("the sidebar shows libraries, not parts"; Default + optional
        custom libraries as tags, not containers) makes Library a first-class navigational concept
        in this app's existing IA, not an operation performed *on* a project. The menu should mirror
        that existing peer relationship, not invent a new hierarchy. Items: "Default Library", then
        one item per real custom library from `library.list_libraries()` (`SPEC-315`'s own
        `LibrarySummary[]`), each selecting that library the same way clicking it in the sidebar
        already does today.
    *   **Settings moves to the native macOS App-name menu, with Quit/About alongside it.** Today
        Quit lives in `File` and About lives in `Help` -- functional, but non-standard; macOS's own
        convention is a single leftmost menu named for the app itself, holding About/Preferences
        (`Cmd+,`)/Services/Hide/Quit. Confirmed directly with the user rather than defaulting to the
        smaller change (adding Settings to File): this spec moves `PredefinedMenuItem::quit` and the
        existing About item out of `File`/`Help` and into a new leftmost app-name `Submenu`,
        alongside a new "Settings…" item (`Cmd+,`) emitting a `menu://open-settings` event the same
        way `MENU_SAVE_PROJECT_EVENT` already works -- `App.tsx`'s existing `setView({kind:
        'settings'})` becomes the real handler, no new view logic needed.
*   **Data Flow / Interactions:**
    *   Rust (`menu.rs`) builds the menu structure once at launch, same as today -- the Library
        menu's *items* are the one piece that needs real data (the list of custom libraries) at
        build time, sourced by calling into the already-running Python daemon the same way
        `daemon::dispatch_to_daemon` already does elsewhere, or accepted as a known, real limitation
        (menu built before any daemon round-trip) that a later phase resolves with a rebuild-on-change
        approach -- exact mechanism is a `CTX-316.x` implementation decision, not fixed here.
    *   Every new menu item (Design submenu actions, Library items, Settings) emits a Tauri event;
        `App.tsx` gains new listeners exactly mirroring the two `CTX-312.3` already added for Save/Open
        Project. No new IPC routes, no new Rust-side business logic beyond menu construction and
        event emission.
*   **Cross-Module Impacts:**
    *   `core/tauri-rust/src/menu.rs` -- new `Design` top-level menu (3 submenus), new `Library`
        top-level menu, new app-name `Submenu` (About/Settings/Services/Hide/Quit), removing Quit
        from `File` and About from `Help`.
    *   `apps/tauri-ui/src/App.tsx` -- new menu-event listeners routing to each area's already-real
        handler and to `setView({kind:'settings'})`/`setView({kind:'library', ...})`.
    *   `apps/tauri-ui/src/components/{SchematicAdvisor,BoardAdvisor,EnclosurePanel}.tsx` -- each
        area's existing handler functions become callable from outside the component (via a prop
        callback or a lifted handler in `App.tsx`), since today they're closures private to each
        component; exact lifting mechanism is a `CTX-316.x` decision.

## 3. Known Constraints & Risks
*   **Known Issues / Technical Debt:** The disabled-not-hidden approach for inapplicable Design
    actions (e.g. "Check Schematic" with no project open) needs the menu to reflect real app state,
    which native `tauri::menu` items support via `set_enabled(...)` but requires the Rust side to be
    told about frontend state changes (project selected, board picked) -- a real, two-way sync this
    spec's Non-Goals section deliberately keeps simple (start conservative: enabled whenever a
    project is open, matching the existing in-view buttons' own real preconditions) rather than
    modeling every per-action precondition natively at launch.
*   **Gotchas & Hazards:** The Library top-level menu's items depend on real daemon data
    (`list_libraries()`) that doesn't exist until the daemon has started -- if the native menu is
    built before the daemon is ready (today's `daemon::spawn_daemon` happens in `.setup()`, after
    `.menu(...)` runs), the Library menu's custom-library items may need a placeholder ("Default
    Library" always present, custom libraries populated once known) or a menu-rebuild step. Not
    resolved here; named explicitly for `CTX-316.x` to design against, not assumed away.

## 4. Module Map & Reference Links
```text
[Root Spec](../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-300](SPEC-300-product-ia-interaction-model.md)
          └── [This Spec](SPEC-316-native-menu-command-surface.md)
                 ├── depends on [SPEC-312](SPEC-312-application-shell-project-portability-persistence.md) (base File/Edit/View/Help shell, CTX-312.3)
                 └── depends on [SPEC-315](SPEC-315-library-browsing-and-organization.md) (library model the Library menu reads)
```

## 5. User & Interaction
*   **Product Stage:** Cross-cutting -- every stage of working inside a project (Schematic, PCB,
    Enclosure), plus app-level navigation (Library, Settings).
*   **What the user is trying to accomplish:** Reach any real action -- run a schematic check,
    generate a PCB or enclosure result, open a specific library, open Settings -- from one
    consistent, discoverable place, with a keyboard accelerator where useful, instead of needing to
    already be on the exact right screen first.
*   **What the user sees and does:** A real native menu bar with an app-name menu (About, Settings…
    `Cmd+,`, Quit), `File`, `Edit`, a `Design` menu holding `Schematic`/`PCB`/`Enclosure` submenus
    of that area's real actions, a `Library` menu listing Default plus any real custom libraries,
    and `Help`. Clicking any item does exactly what its equivalent in-view button already does
    today; items that don't apply to the current state (no project open) render disabled rather than
    disappearing.

---
id: SPEC-315
title: "Library Browsing & Organization"
status: Completed
type: Feature
created: 2026-08-19
last_updated: 2026-08-19
target_version: v0.3.0
location: "apps/tauri-ui/specs/SPEC-315-library-browsing-and-organization.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-315: Library Browsing & Organization

## 1. Executive Summary & Goals

*   **High-Level Goal:** Turn the rail's Library entry from a real-but-unusable count (`SPEC-305`'s
    own named placeholder: "a real browsing UI ... is out of scope, deferred to a future spec") into
    a real place a user can find a Part they already saved, group their own growing collection into
    libraries that make sense to them, and reuse a saved object across projects -- without adding a
    second, project-scoped copy of anything `SPEC-304` already made global.
*   **Business / Technical Value:** Real, hands-on testing of `SPEC-314` (2026-08-19) surfaced the
    same gap from a different angle: a user who saves a Part has no way to see it again, no way to
    tell whether "Save to Library" means the project or the app, and no way to organize more than a
    handful of Parts before the sidebar becomes useless. `SPEC-304`'s own storage schema already
    solved the hard part (global objects, real files, provenance) -- nothing built since has given a
    human a way to actually browse what's in there. Left unaddressed, this also blocks the real
    payoff `SPEC-308`/`SPEC-309` will eventually need: pulling an *existing* saved Part, Symbol, or
    Footprint into a schematic or PCB from inside this app, not just KiCad's own installed libraries.
*   **Non-Goals:**
    *   **Not component discovery, search, or extraction.** `SPEC-306` owns finding and confirming a
        *new* Part; `SPEC-307` owns rendering its pins and the "Save to Library" action itself. This
        spec starts once an object is already saved and asks "how does a user find it again."
    *   **Not footprint/symbol *sourcing*.** `SPEC-308` (installed KiCad libraries, datasheet
        generation) and `SPEC-314` (curated community repos) are the real supply side -- where a
        Footprint or Symbol *comes from*. This spec is the organize/browse layer for whatever has
        already been saved, regardless of which of those three sources produced it. Conflating the
        two would re-litigate `SPEC-314`'s own already-shipped search/import flow for no reason.
    *   **Not project-scoped copies of anything.** `SPEC-304`/`SPEC-300` §2 already made this call
        for Footprint ("shared by many Parts, not one per Part") and this spec does not reopen it --
        a Part, Symbol, or Footprint remains exactly one global object; a custom library is a
        grouping *tag* on top of it, never a duplicate.
    *   **Not schematic or PCB library-picker UI.** `SPEC-308`/`SPEC-309` will eventually need a real
        "insert from your Library or from KiCad's own library" picker inside the Schematic/PCB
        advisor screens -- this spec's schema decisions must not foreclose that, but building the
        picker itself is a future context on those specs, not this one.
    *   **Not changing what "Save to Library" already does.** It still always saves into the one
        default library every object already implicitly belongs to today. This spec adds a second,
        optional action (tagging into a custom library); it never replaces the first.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **A "library" is a tag, not a container -- default-first, custom on top.** Every real Part,
        Symbol, and Footprint already belongs to one implicit library today (the flat, global
        `library/` directory `SPEC-304` defined); this spec makes that the real, always-present
        *Default* library and layers real, user-created custom libraries on top as pure grouping --
        no separate storage, no separate functionality, just membership. An object can belong to any
        number of custom libraries in addition to Default; removing it from every custom library
        never removes it from Default (there is no "delete from the app" action implied here -- that
        stays out of scope). This mirrors the same reasoning `SPEC-304` already used for Footprint
        sharing: fragmenting a global object into per-grouping copies would break exactly the reuse
        this whole storage layer exists for.
    *   **Library membership is tracked per real object, not per Part.** A Part, its linked Symbol,
        and its linked Footprint are tagged independently, not as a bundle. `SPEC-304` already treats
        Footprint as a real, independently-shared object (one SOIC-8 Footprint record, many Parts
        referencing it) -- tying a Footprint's library membership to whichever Part happened to save
        it first would misrepresent that sharing the moment a second, unrelated Part starts using the
        same Footprint. The real, direct consequence: "Save to Library" tags the Part, Symbol, and
        Footprint it just touched into Default together (matching today's implicit behavior exactly),
        but a later "add to library" action operates on one specific object at a time, and a custom
        library's own contents list is genuinely two lists -- Parts/Symbols (the pin/datasheet side)
        and Footprints (the board side) -- not one merged feed, because that split is real and
        already load-bearing throughout `SPEC-300`/`SPEC-304`/`SPEC-308`.
    *   **The sidebar shows libraries, not parts.** `SPEC-305`'s own rail already shows a real Part
        count next to the Library entry; this spec keeps that count but changes what selecting it
        opens: a list of libraries (Default plus any real custom ones, each showing its own real
        count), not a flat, unbounded list of every Part the user has ever saved -- which would
        become useless well before a real collection grows large. Selecting one library opens a
        dedicated main-content view (not an in-rail list) showing its two real sub-sections; search
        and filtering live inside that view, not the rail, since the rail's whole job elsewhere in
        this app is "which area, not which item within it."
    *   **This is deliberately the organizing layer, not the discovery layer.** `SPEC-306`
        (search-and-confirm a new Part), `SPEC-308` (installed-library and generated footprints),
        and `SPEC-314` (community-library import) all still end the same real way they do today:
        `library.save_part`/`save_symbol`/`save_footprint`. This spec's own new "add to a custom
        library" action is a separate, later step a user takes from an object's own detail view (Part
        Detail, or wherever a Footprint/Symbol is eventually shown standalone) -- it is not a new
        parameter threaded through every existing save call.
*   **Data Flow / Interactions:**

    ```text
    Rail: Library (N parts) -- click -->  Library area

      +-----------------------------------------------------------+
      | Libraries                                    [+ New]      |
      |                                                             |
      |  Default              128 parts, 41 footprints            |
      |  ESP32 boards           6 parts,  3 footprints    [open]   |
      |  Client X                9 parts,  4 footprints    [open]  |
      +-----------------------------------------------------------+

    selecting "ESP32 boards" -->

      +-----------------------------------------------------------+
      | ESP32 boards                                               |
      |                                                             |
      | Datasheets / Pins (6)          Footprints (3)              |
      |  ATtiny85-20PU                  generated__ATtiny85         |
      |  ESP32-WROOM-32                 sparkfun__...__C_0201       |
      |  ...                             ...                        |
      +-----------------------------------------------------------+

    Part Detail (SPEC-307) / a future standalone Footprint/Symbol view -->
      new "Add to library..." action, independent of "Save to Library" --
      tags this one object into 0+ custom libraries; Default is implicit,
      never shown as a choice to remove.
    ```

*   **Cross-Module Impacts:**
    *   `services/python-daemon`: `library_store.py`'s Part/Symbol/Footprint records gain a real
        `library_ids: string[]` field (always includes `"default"`); a new
        `library.list_libraries`/`library.create_library`/`library.tag_object` route family, and
        `library.list_parts`/`list_symbols`/`list_footprints` gain an optional library filter. A real
        migration concern, not a schema-only one: every record saved before this spec ships has no
        `library_ids` field at all -- read paths must treat that as `["default"]`, not a crash or a
        silently-empty library.
    *   `apps/tauri-ui`: `Rail.tsx`'s Library entry changes destination from a placeholder to a real
        library-list view; a new `LibraryArea`-shaped component (name TBD in implementation context)
        renders the two-list, one-library view above. `PartDetail.tsx` gains the new "Add to
        library..." action.
    *   `core/tauri-rust`/daemon transport: none -- no new secrets, no new process boundaries.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   **Every pre-existing Part/Symbol/Footprint record needs a real, honest migration.** Nothing
        saved before this spec ships has a `library_ids` field. The implementation context must
        decide and test the real read-time default (`["default"]` when absent) rather than silently
        breaking every object saved under `SPEC-304`/`SPEC-307`/`SPEC-314` to date.
*   **Gotchas & Hazards:**
    *   **The Part/Symbol/Footprint split is easy to accidentally re-merge in the UI**, the same real
        risk `SPEC-300` §2 already named for the data model itself -- a library view that shows one
        combined list instead of two would quietly imply a Part and its Footprint always travel
        together, which `SPEC-304` explicitly rejected for real reuse reasons (one Footprint, many
        Parts). Keep the two-section view real, not a convenience collapse.
    *   **A custom library with zero real members is a legitimate, expected state** (a user just
        created one and hasn't tagged anything into it yet) -- must render as an honest empty state,
        not implied as broken or hidden from the library list.
*   **Related findings from real, live testing (2026-08-19), out of this spec's own scope but worth
    capturing so they aren't lost:**
    *   **`SPEC-306`: an extremely generic search term ("button") returned a short, plausible-looking
        candidate list with no signal that the query itself was too broad to disambiguate
        meaningfully.** `SPEC-306`'s own *did you mean* design already requires an explicit confirm
        click per candidate, which limits the real damage, but the search step itself has no concept
        of "this query needs to be narrowed" -- worth a future revisit of that spec, not this one.
    *   **`SPEC-202`/`SPEC-306`: a confirmed candidate's own `datasheet_url` was observed dead in
        real use** (a real live 404 against an NXP datasheet URL for a Teensy 4.1 candidate) with no
        distinction surfaced between "couldn't be cached automatically" and "the link itself doesn't
        resolve." A real reachability check (or at least a clearer failure message) belongs in
        whichever of those two specs owns sourcing that URL, not here.
    *   **`SPEC-202`: a real "Extraction did not return valid JSON" failure was observed for a real
        part (Teensy 4.1), blocking the user from ever reaching Part Detail** -- and therefore from
        ever seeing this spec's own Library-tagging UI at all. This looked, from the outside, like
        "the Find Footprint / Community Libraries UI doesn't exist yet"; it was actually an
        unrelated, upstream extraction failure. `SPEC-202`'s own extraction step needs more robust
        handling of a malformed-JSON response (repair/retry) rather than surfacing a raw parse error
        as the user-facing result.

## 4. Module Map & Reference Links

```text
[SPEC-300] Product IA & Interaction Model
   └── [SPEC-315] Library Browsing & Organization
          └── [Context 315.1] (not yet written)
```

*   [SPEC-300](SPEC-300-product-ia-interaction-model.md) §2 -- the six-object model (Part, Symbol,
    Footprint kept separate on purpose) this spec's own two-section library view stays faithful to.
*   [SPEC-304](SPEC-304-project-library-storage.md) -- the real storage schema this spec extends
    with `library_ids`, not replaces; Footprint's existing "global, shared by many Parts" design is
    the direct precedent for tagging objects independently rather than bundling by Part.
*   [SPEC-305](SPEC-305-app-shell-navigation.md) §2 -- names the exact gap this spec resolves: "The
    Library rail entry ... a real browsing UI ... is out of scope, deferred to a future spec."
*   [SPEC-306](SPEC-306-component-discovery.md) / [SPEC-307](SPEC-307-part-detail-library-export.md)
    -- the existing search-confirm-save flow this spec extends with a later, optional tagging step;
    also where the two related-but-out-of-scope findings above (§3) belong once picked up.
*   [SPEC-308](SPEC-308-footprints-schematic-advisor.md) / [SPEC-309](SPEC-309-board-advisor.md) --
    the real future consumers of a browsable Library (insert an existing saved object into a
    schematic or PCB from inside this app), named here as a forward dependency this spec's schema
    must not block, not built here.
*   [SPEC-314](SPEC-314-community-library-discovery.md) -- a discovery source whose imported
    Footprints/Symbols land in the same global storage this spec organizes; no scope overlap.

## 5. User & Interaction

*   **Product Stage:** Library -- the rail's persistent, non-project-scoped entry (beside Projects
    and Settings), reachable from anywhere in the app at any time.
*   **What the user is trying to accomplish:** find a Part, Symbol, or Footprint they already saved
    (possibly weeks and many projects ago) without re-searching or re-generating it, and organize a
    growing personal collection into groups that make sense to them -- by client, by board family,
    by vendor, or however they actually think about their own parts -- without the app forcing a
    single, project-based organization scheme on them.
*   **What the user sees and does:** the rail's Library entry keeps its real count; selecting it
    opens a list of libraries -- the always-present Default plus any the user has created, each
    showing its own real Part/Symbol and Footprint counts -- with a real "New library" action.
    Selecting one library opens a dedicated view split into two real sections (Datasheets/Pins and
    Footprints), each item identifiable at a glance (part number, package, and its real source --
    generated, an installed KiCad library, or a community import with its license). From any saved
    object's own detail view, a new "Add to library..." action lets the user tag it into one or more
    custom libraries; Default membership is implicit and never shown as something to remove.

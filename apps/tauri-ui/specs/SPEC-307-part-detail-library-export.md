---
id: SPEC-307
title: "Part Detail & Library Export"
status: Completed
type: Feature
created: 2026-08-12
last_updated: 2026-08-12
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-307-part-detail-library-export.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-307: Part Detail & Library Export

## 1. Executive Summary & Goals

*   **High-Level Goal:** Replace `SPEC-306`'s confirmed-candidate dead end ("Part Detail (SPEC-307)
    isn't built yet") with a real Part Detail view: the confirmed part's real pin diagram and pin
    table, each pin labeled with its function, a real "Save to Library" action that persists a
    provenanced Part and Symbol, and a real "Export Symbol" action that writes a genuine
    `.kicad_sym` library file.
*   **Business / Technical Value:** This is the step that turns a search result into a real, owned
    object. `PRODUCT-PLAN.md` §6 M2's own "Done means" line is explicit: "search for a part,
    disambiguate it, see its pins with sources, save it to the parts library, reopen the app and
    it's still there, use it in a second project." Everything up through a confirmed candidate
    (`SPEC-306`) already exists; nothing yet writes a real `library.save_part` call or lets a human
    see a pin with its source.
*   **Non-Goals:**
    *   **Not schematic connection guidance** (decoupling, protection, power advice). That's
        `SPEC-308`'s own row in `PRODUCT-PLAN.md` §5.1, named there specifically so this spec
        doesn't duplicate it. "Per-pin guidance" here means labeling what a pin *is* (its function
        and electrical type), not advising how to *use* it in a circuit.
    *   **Not footprint search or creation.** Also `SPEC-308`.
    *   **Not live symbol injection into an open KiCad schematic session.** `CTX-108.1` already found
        that `kipy`'s `Schematic` class needs KiCad 11 (`.. versionadded:: 0.7.0`), unavailable on
        this development machine (10.0.3). This spec's export is a **standalone `.kicad_sym` library
        file written directly to disk** — a plain, versioned S-expression text format that needs no
        live IPC session at all, so it is not blocked by that same limitation. Live injection of a
        schematic symbol, if ever built, is a different capability for a future context.
    *   **Not a pin-editing UI.** This view renders what `SPEC-202`'s real extraction returned;
        correcting a wrong extraction is future work. Per-field provenance (already enforced by
        `CTX-304.1`) is what lets a human *see* what was inferred — it doesn't yet let them fix it.

## 2. System Architecture & Design Choices

*   **Design Rationale:**
    *   **Part Detail re-runs `SPEC-202`'s real extraction rather than inventing a second pipeline.**
        `kicad.generate_component(part_number)` already returns a real, validated
        `{part_number, package, pins, package_dimensions, courtyard}` schema — the pin diagram and
        pin table this spec renders are that same `pins` array, not a new call. This is a second
        real LLM call for the same part number (the first was `SPEC-306`'s ranking call) — a real
        latency/cost cost worth naming, not hidden, and consistent with `PRODUCT-PLAN.md` §2.3's own
        stage model where each stage does its own real work rather than silently reusing a prior
        stage's output.
    *   **Per-pin guidance is the pin's own `electrical_type` and `name`, not a new advisory call.**
        `SPEC-308`'s own row already owns "connection guidance (decoupling, protection, power)" —
        duplicating that here would blur a boundary `PRODUCT-PLAN.md` §5.1 already drew between the
        two specs. "GPIO / bidirectional," "VCC / power," "GND / ground" next to each pin is real,
        useful information the extraction schema already carries; it is not circuit advice.
    *   **Provenance is assembled at save time from two calls this spec already has, not by amending
        `SPEC-202`'s output shape.** `manufacturer`/`datasheet_url` provenance comes from `SPEC-306`'s
        confirmed candidate (`source: "search"`, the candidate's own `confidence`); `package`/`pins`
        provenance comes from this spec's own extraction call (`source: "llm_extraction"`, the real
        provider/model that ran it). This satisfies `CTX-304.1`'s already-enforced
        `_validate_part_provenance` using data this spec already holds, rather than reopening
        `component_pipeline.py`'s output contract — the exact re-scope `PRODUCT-PLAN.md` §5.2 names
        for `SPEC-202` ("needs provenance and per-field confidence added") is satisfied here at the
        assembly point, not inside the pipeline itself.
    *   **`.kicad_sym` export is a real file write, not a shell-out to KiCad.** KiCad's symbol
        library format is a plain, versioned S-expression text file — the same "hand-write the real
        format" approach `kicad_write.py` already established for `.kicad_mod`-shaped geometry
        (`CTX-108.1`), reused here for a different, static file rather than a live board
        transaction. Verified for real the same way: a file KiCad itself can open and parse, not
        just text that looks plausible.
*   **Data Flow / Interactions:**

    ```text
    SPEC-306's confirmed candidate --> Part Detail (this spec)

      kicad.generate_component(part_number) --> real pins[] (SPEC-202, re-run for real)

      +----------------------------------------------------+
      | ATtiny85-20PU            Microchip        DIP-8    |
      |                                                     |
      |   [pin diagram: 8 pins, each labeled]              |
      |                                                     |
      |   # | Name  | Type          | Source              |
      |   1 | RESET | bidirectional | llm_extraction       |
      |   2 | PB3   | gpio          | llm_extraction       |
      |   ...                                               |
      |                                                     |
      |   [ Save to Library ]   [ Export Symbol (.kicad_sym) ] |
      +----------------------------------------------------+

    "Save to Library" --> provenance assembled from the SPEC-306 candidate + this
                           extraction call --> library.save_part + library.save_symbol
    "Export Symbol"   --> a real .kicad_sym file written to disk, openable in KiCad
    ```

*   **Cross-Module Impacts:**
    *   `apps/tauri-ui`: a new Part Detail surface reached from `SPEC-306`'s confirmed state
        (replacing its "Part Detail (SPEC-307) isn't built yet" dead end), plus a new `lib/`
        wrapper for the extraction/save/export calls this spec needs.
    *   `services/python-daemon`: a new `library_store.py` function to write a real `.kicad_sym`
        file; no new AgentFlow agent needed (reuses `kicad.generate_component` as-is).
    *   No impact on `core/tauri-rust` — pure daemon-route and frontend work, same shape as
        `SPEC-305`/`SPEC-306`.

## 3. Known Constraints & Risks

*   **Known Issues / Technical Debt:**
    *   **The persisted Symbol record has no defined pin/layout schema yet.** `library_store.py`'s
        `save_symbol` only requires `symbol_id` today — nothing upstream has defined what a Symbol's
        pins or schematic layout actually look like as data. This spec has to define that shape
        (most likely the extraction schema's own `pins` array plus a simple, non-editable auto-
        arranged position per pin, since no visual symbol editor exists), not assume it already
        exists.
*   **Gotchas & Hazards:**
    *   **Symbols and Footprints are shared objects in `SPEC-300`'s own model** ("many parts share
        one footprint"), but nothing yet prevents saving a duplicate, functionally-identical Symbol
        per Part. A naive one-Symbol-per-Part save works but risks real duplication over time; at
        minimum, `symbol_id` should be derived from a stable signature (e.g. package + pinout), not
        a random id, so identical parts converge on one record rather than silently diverging.
    *   **A `.kicad_sym` file that merely looks plausible is not the bar.** The real verification is
        KiCad itself successfully opening/parsing the exported file, mirroring `CTX-108.1`'s own
        "real KiCad transaction, not a best-effort write" standard.
    *   **Re-running extraction is a second real LLM call per confirmed part**, with its own real
        cost, latency, and (per `CTX-306.1`'s own findings) real failure modes — provider/model
        overrides, response-truncation risk, etc. all apply here exactly as they did to `SPEC-306`'s
        search call and `SPEC-202`'s original extraction; this spec inherits those risks rather than
        introducing new ones, and should not re-litigate fixes already made there.

## 4. Module Map & Reference Links

*   [SPEC-300](SPEC-300-product-ia-interaction-model.md) §2.3 — Component Detail, stage 2 of the
    stage machine this spec builds.
*   [SPEC-306](SPEC-306-component-discovery.md) — the confirmed candidate this spec's Part Detail
    view receives and replaces the dead end in.
*   [SPEC-304](SPEC-304-project-library-storage.md) — the Part/Symbol schemas and
    `_validate_part_provenance` check this spec's "Save to Library" action must satisfy.
*   [SPEC-202](../../../services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) —
    the real extraction pipeline this spec re-runs for pin data, reused as-is.
*   [CTX-108.1](../../../services/python-daemon/context/CTX-108.1-kicad-write-path-footprint-injection.md) —
    the "hand-write the real KiCad format" precedent this spec's `.kicad_sym` export follows, and
    the KiCad-11 `kipy.Schematic` limitation this spec is explicitly *not* blocked by (a static file
    write, not a live IPC session).
*   [PRODUCT-PLAN.md](../../../PRODUCT-PLAN.md) §5.1, §6 M2 — this spec's own scope row and the
    milestone's "Done means" line this spec exists to satisfy.
*   `SPEC-308` *(not yet written — no file to link to)* — owns connection guidance and footprint
    work, deliberately not duplicated here.

```text
[SPEC-300] Product IA & Interaction Model
   └── [SPEC-306] Component Discovery
          └── [SPEC-307] Part Detail & Library Export
                 └── [Context 307.1] (not yet written)
```

## 5. User & Interaction

*   **Product Stage:** Component Detail — stage 2 of `PRODUCT-PLAN.md` §2.3's stage machine, right
    after Discovery.
*   **What the user is trying to accomplish:** See the pins of the part they just confirmed, with
    enough per-pin detail (function, electrical type, where it came from) to trust it, then commit
    it to their permanent parts library so it's still there next time and usable in another project.
*   **What the user sees and does:** A real pin diagram and pin table for the confirmed part
    (re-extracted for real, not reused from the search step), each pin labeled with its type and
    source. A "Save to Library" action persists a provenanced Part and Symbol. An "Export Symbol"
    action writes a real `.kicad_sym` file the user can point KiCad at directly.

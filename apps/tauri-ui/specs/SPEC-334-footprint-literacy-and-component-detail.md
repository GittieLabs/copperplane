---
id: SPEC-334
title: "Footprint Literacy & Component Detail"
status: Completed
type: Feature
created: 2026-09-02
last_updated: 2026-09-03
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-334-footprint-literacy-and-component-detail.md"
parent_spec: "SPEC-325-kicad-project-integration.md"
child_specs: []
user_facing: true
---

# SPEC-334: Footprint Literacy & Component Detail

> **Closed 2026-09-09.** The footprint-literacy half is delivered by `CTX-334.1` and `CTX-334.2`;
> searching KiCad's own libraries is delivered by `CTX-334.3`.
>
> **`SPEC-334` §2's second open question — *"which NE555P am I getting"* — is not carried forward
> here.** It is about disambiguating LLM part-search results by package, temperature grade and pin
> layout: a different mechanism from reading a `.kicad_mod` off disk, and `SPEC-306`'s surface
> rather than this one. Keeping it inside a spec titled *Footprint Literacy* is how it stays
> unaddressed while looking tracked. Deprioritised deliberately, not dropped by oversight:
>
> > *"q2 isn't really the focus right now. the education of the user for the project is a bigger
> > deal to me and we have been building the ground work for the teaching part given a project and
> > schematic goal."*
>
> Pick it up from `SPEC-306` when part selection is the actual focus.

## 1. Executive Summary & Goals

*   **High-Level Goal:** Let a user click a row in the board components table and understand *what
    that component and footprint actually are* — including what KiCad's naming is telling them, and
    what would change if they picked a different footprint.

*   **Business / Technical Value:** This is the same gap `SPEC-332` closed for DRC findings, one
    stage earlier. The maintainer, on his own board:

    > *"I get that the first part of the name convention describes where this footprint is listed
    > under, but there are often many options to choose from that have very similar names and it's
    > hard to know what `P2.54mm_Vertical` means when to use over `P2.00mm_Horizontal`. If I am a
    > user, that's what I am trying to get clarification on."*

    And on the part itself:

    > *"A component search gives me multiple options that at a glance seem very similar but each
    > option in kicad for adding to a schematic has different pin layouts... Which NE555P am I
    > getting."*

    A real search for `NE555P` returns NE555P/NE555D/SA555P/NA555P/SE555P — differing in package
    (PDIP-8 vs SOIC-8), temperature grade, and pin layout. The list shows a package string and a
    confidence, which is not enough to choose between them. The target reader is explicitly *"a
    hobbyist/maker... not a professional in schematics, pcbs, or cad"*.

*   **Non-Goals:**
    *   Changing a footprint from this app. This explains; KiCad edits. (`SPEC-329` territory.)
    *   A general PCB encyclopedia. Scope is what is in front of the user: the footprints on their
        board, and the parts their searches return.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **Settled: the footprint's own `descr` and `tags` are the primary source.** This was left open
    because those fields were assumed to be "often empty or unhelpful". Measured instead, across a
    random sample of 400 footprints from KiCad 10's own 155 libraries: **100% have a non-empty
    `descr` and 98% have `tags`.** They are also better than a parser could be —
    `PinHeader_1x04_P2.54mm_Vertical` reads *"Through hole straight pin header, 1x04, 2.54mm pitch,
    single row"*, which answers the maintainer's `P2.54mm_Vertical` question directly, and
    `Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles` carries a datasheet URL.

    So: read the file. It is authoritative, instant, free, and cannot hallucinate. A static decoder
    covers the naming conventions `descr` does not spell out (`SPEC-332`'s glossary is the
    precedent), and an LLM is reserved for the comparative question — *which of these should I
    use* — grounded in both.
*   **Settled: the abbreviations are decoded, not enumerated.** Raised by the maintainer after
    `CTX-334.1` shipped: *"THT, DIP and all of the other abbreviations are not intuitive."*
    `ROADMAP.md` already warned what the wrong answer looks like — *"a glossary that is not a
    hard-coded list ... wrong if it grows into a general PCB dictionary"*. So the families are
    taken from KiCad's own `Package_*` libraries, and the dozens of variants are read as a height
    letter plus a family rather than listed: 33 entries and 11 prefix letters explain **88.0% of
    the 15,433 footprints KiCad ships**, including combinations the glossary has never seen. A
    token belonging to a vendor's product line is named as one rather than expanded, because it has
    no standard meaning to give. Delivered in `CTX-334.2`.

*   **Settled: KiCad's own libraries are searched on every query, and never behind a classifier.**
    Delivered in `CTX-334.3`. `kicad.search_footprints` is local disk I/O — free, instant, unable to
    hallucinate — so it runs alongside the paid part search rather than instead of it, and its hits
    are labelled as footprints. Measured against KiCad's own libraries, the objection that this
    would clutter part results is empty: `NE555P` and `ATtiny85` return **zero** footprint hits,
    while `PinHeader_1x04_P2.54mm_Vertical` returns 4 and `DIP-8` returns 25. The search
    self-selects, so there was never a routing decision to get right. Original wording below.

*   **(Original wording, for the record)** Whether KiCad's own libraries are searchable. The maintainer searched a *footprint* name in
    *component* search and got vendor part numbers, because the two namespaces were never
    connected: *"I have a hunch that the component I searched for ... is a kicad only reference name
    and would not be searchable with our component search."* Correct. Decide whether component
    search should detect a footprint-shaped query and answer from KiCad's libraries instead of
    guessing at a manufacturer.
*   **Deferred to `SPEC-306`, see the header.** What "which NE555P am I getting" is answered with. Package, pin count and pin *layout*
    differ across a search's results. The footprint determines the physical part; the datasheet
    determines the pinout. Settle which of those the detail view leads with.
*   ~~**How this reaches the user.**~~ **Delivered in `CTX-334.1`:** an action on each row of the board components table, opening a detail view. Original wording below.

*   **(Original wording, for the record)** How this reaches the user. Proposed: an action on each row of the board components table
    (`SchematicComponents`), opening a detail view for that component and its footprint.

## 3. Known Constraints & Risks

*   Footprint naming is a convention, not a contract. A parser will meet names it cannot decode,
    and must say so rather than inventing a reading — the failure mode `SPEC-326` §1 exists to
    prevent.
*   `.kicad_mod` `descr`/`tags` were verified before being depended on (see §2): 400/400 and
    395/400 respectively, on KiCad 10's bundled libraries. **That is a claim about KiCad's own
    libraries only.** A user's personal or community `.pretty` may carry neither, so the surface
    must degrade to the naming decoder rather than showing an empty panel.
*   An LLM explanation of a footprint name is exactly the kind of confident-sounding output that is
    hard to check. It needs grounding in the footprint file, and must be marked when it is not.
*   **A decoder is not exempt from that risk.** `CTX-334.2` found this without an LLM anywhere in
    the path: `LFCSP` composes fluently to "Low profile, fine pitch CSP" and Analog Devices means
    *Lead Frame*. Any reading assembled from parts must be marked as assembled, and a whole-token
    meaning must always win over a composed one.

## 4. Module Map & Reference Links

*   `apps/tauri-ui/src/components/SchematicComponents.tsx` — the board components table this hangs
    off.
*   `apps/tauri-ui/src/lib/kicadGlossary.ts` — `SPEC-332`'s static-explanation precedent, for the
    vocabulary KiCad's DRC emits.
*   `apps/tauri-ui/src/lib/packageGlossary.ts` — the package and naming vocabulary (`CTX-334.2`).
*   `apps/tauri-ui/tests/glossaryCoverage.test.ts` — the corpus measurement that bounds it.
*   `services/python-daemon/kicad_bridge.py` — reads `.kicad_mod` files today
    (`resolve_footprint_model`, `read_footprint_courtyard`).
*   `services/python-daemon/kicad_cli.py` — `export_footprint_svg`, already able to render one.
*   `apps/tauri-ui/specs/SPEC-332` — DRC as a teaching surface, the same idea one stage later.

## 5. User & Interaction

*   **Product Stage:** Schematic/PCB — choosing and understanding parts already in the design.
*   **What the user is trying to accomplish:** Deciding whether the footprint on their board is the
    right one, and understanding what a differently-named alternative would mean physically.
*   **What the user sees and does:** Clicks a component row in the board components table and gets
    a detail view: what the footprint's name means, what the part is, what a different footprint
    would change, and a rendered view of the footprint itself where one is available.

---
id: SPEC-308
title: "Footprints & Schematic Advisor"
status: Draft
type: Feature
created: 2026-08-14
last_updated: 2026-08-14
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-308-footprints-schematic-advisor.md"
parent_spec: "../../../apps/tauri-ui/specs/SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-308: Footprints & Schematic Advisor

## 1. Executive Summary & Goals
*   **High-Level Goal:** Make the Footprint a first-class object with its own find-or-create flow,
    per `PRODUCT-PLAN.md` §5.1: find a footprint in the user's installed KiCad libraries, or create
    one from datasheet package dimensions; export it to a real `.pretty` library; link it to a Part.
    Plus connection guidance (decoupling, protection, power) once a part and its footprint are both
    real. This is M3 in `PRODUCT-PLAN.md` §6 -- the milestone after M2's shell/projects/components
    landed.
*   **Business / Technical Value:** `PRODUCT-PLAN.md` §2.1 already establishes *why* this is its own
    spec, not a field on Part: "creating a part and creating a footprint are separate user actions
    with separate flows... a part with pins and a datasheet is useful before any footprint exists."
    The storage layer already reserves a place for this (`library/footprints/`, exportable as a real
    KiCad `.pretty` library, per §4) and `services/python-daemon/library_store.py` already has real
    `save_footprint`/`load_footprint` functions (`CTX-304.1`) with a `footprint_id`-keyed record --
    the persistence half of this spec's job is already built. What's missing, confirmed by reading
    `kicad_bridge.py` directly: no route searches the user's *installed* KiCad footprint libraries at
    all today -- only board-level footprint queries (mounting holes) and single-footprint injection
    exist (`SPEC-108`).
*   **Non-Goals:**
    *   **Not schematic symbol injection.** That's `CTX-108.2`'s own explicitly reserved, still-open
        slot (needs KiCad 11's `Schematic` support).
    *   **Not the board advisor.** `SPEC-309` (ERC/DRC reading, explain-and-suggest) is separate,
        deliberately sequenced after this spec per `PRODUCT-PLAN.md` §6 M4.
    *   **Not redesigning `kicad.inject_component`'s own write path.** `SPEC-108`/`CTX-108.1`'s real
        `FootprintInstance`/`Pad`/courtyard build and KiCad transaction are reused as-is; this spec's
        job is finding or creating the footprint that gets injected, not how the injection itself
        works.

## 2. System Architecture & Design Choices
*   **Design Rationale:** Left as an open design question, not invented here -- `PRODUCT-PLAN.md`
    §8 open question 3 already names the real unresolved scoping call: *"Now that footprints are
    their own object, 'find a footprint' needs a defined corpus: the user's installed KiCad
    footprint libraries first, then the user's own library, then generation from datasheet package
    dimensions. Which of the three are in scope for SPEC-308, and how a generated footprint is
    marked as unverified, both need deciding."* The implementation context should resolve this
    against kipy's real library-search API (not yet checked against real kipy source for this spec)
    before writing any search code.
*   **Data Flow / Interactions:** Not designed here -- depends on the corpus decision above.
*   **Cross-Module Impacts:**
    *   `services/python-daemon`: likely a new `kicad_bridge` capability (installed-library search --
        genuinely new; nothing in `kicad_bridge.py` does this today) and/or a footprint-generation
        path in `component_pipeline.py`-adjacent code (datasheet package dimensions → footprint,
        parallel to `SPEC-202`'s existing datasheet → Part pipeline). `library_store.save_footprint`/
        `load_footprint` (`CTX-304.1`) are reused as-is for persistence.
    *   `apps/tauri-ui`: a real find-or-create UI, distinct from `SPEC-306`'s part-search flow.
    *   Depends on `SPEC-307` (Part Detail & Library Export) per `PRODUCT-PLAN.md` §5.1 -- a
        footprint gets linked to an already-real Part.

## 3. Known Constraints & Risks
*   **The three-source corpus question (`PRODUCT-PLAN.md` §8, item 3) is the real scoping risk for
    this spec** -- not a mechanical detail. Getting it wrong either ships a footprint search that
    only ever generates (never reuses a real installed library footprint a user already trusts) or
    one that never generates (leaving parts with no footprint path when nothing installed matches).
*   **Provenance applies to footprints too**, per `PRODUCT-PLAN.md` §2.2's general rule -- a
    generated-from-datasheet footprint needs to be marked as such (and as unverified) with the same
    honesty `SPEC-202` already applies to Part fields. Not yet designed how that's represented on the
    `Footprint` object `library_store.py` already persists.
*   **kipy's real installed-library-search API has not yet been checked against source** -- unlike
    prior specs in this repo, this spec's own Executive Summary above is honest that this gap
    exists rather than assuming an API shape. Implementation context must verify before designing.

## 4. Module Map & Reference Links
```text
[Root Spec](../../../specs/SPEC-000-architecture-overview.md)
   └── [SPEC-300](SPEC-300-product-ia-interaction-model.md)
          └── [This Spec](SPEC-308-footprints-schematic-advisor.md)
                 └── [Context 308.1](../context/CTX-308.1-subfeature.md)
```
*   [SPEC-108](../../../services/python-daemon/specs/SPEC-108-kicad-write-path-footprint-symbol-injection.md) -- the real write path this spec's found-or-created footprint eventually feeds into.
*   [SPEC-202](../../../services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) -- the datasheet-extraction pipeline pattern this spec's "create from datasheet dimensions" path likely parallels.
*   [SPEC-304](SPEC-304-project-library-storage.md) -- `library_store.save_footprint`/`load_footprint`, already real, already reused here.
*   [SPEC-307](SPEC-307-part-detail-library-export.md) -- this spec's own declared dependency; a footprint links to an already-real Part.
*   [PRODUCT-PLAN.md](../../../PRODUCT-PLAN.md) §5.1, §6 (M3), §8 item 3 -- the real, already-decided scope and the real, still-open scoping question this spec must resolve.

## 5. User & Interaction
*   **Product Stage:** After a Part exists (post-`SPEC-306`/`SPEC-307`) but before it's usable on a
    real board -- the point `PRODUCT-PLAN.md` §2.1 names explicitly: "a part with pins and a
    datasheet is useful before any footprint exists," so this is a deliberate, separate later step,
    not part of part creation itself.
*   **What the user is trying to accomplish:** get a real, trustworthy footprint attached to a part
    they already have -- either reusing one their own KiCad install already has (fastest, most
    trusted), or generating one from the datasheet when nothing installed matches -- then get real
    guidance on how to actually connect it (decoupling, protection, power) rather than guessing.
*   **What the user sees and does:** *Not yet decided -- depends on the corpus/search-UX design
    question in §2/§3 above.* Left as a prompt for the implementation context, per this repo's own
    norm against inventing an interaction design that hasn't actually been discussed.

---
id: SPEC-308
title: "Footprints & Schematic Advisor"
status: Completed
type: Feature
created: 2026-08-14
last_updated: 2026-08-24
target_version: v0.1.0
location: "apps/tauri-ui/specs/SPEC-308-footprints-schematic-advisor.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
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
*   **Corpus decision, resolved 2026-08-14 for the first real slice:** `PRODUCT-PLAN.md` §8 open
    question 3 named three possible sources (installed KiCad libraries, the user's own saved
    library, datasheet generation). Installed-library search is the first slice this spec's own
    implementation work targets; the other two remain real, explicitly deferred follow-up, not
    silently dropped.
*   **A real, significant finding, verified directly against kipy's own source, not assumed:**
    `kicad-python==0.7.1`'s live IPC connection (`kipy.kicad.KiCad`, the class
    `kicad_bridge.py` already wraps) has **no footprint-library-search capability at all**. Checked
    every class/method in `kipy/kicad.py`, `kipy/board.py`, `kipy/project.py`, and every proto
    command message under `kipy/proto/` for anything containing "library"/"fplib"/"footprint" --
    `Board.get_footprints()` only returns footprints already placed on the currently-open board, and
    no `GetLibraries`/`GetFootprintLibraryTable`/`SearchFootprints`-shaped RPC exists anywhere in the
    protocol. `kicad_write.py`'s own existing comment already flagged half of this ("kipy's real API
    has no call to write one" [into a library]); this confirms it also has no call to *read* one.
    **This means installed-library search cannot reuse `kicad_bridge.py`'s IPC connection pattern at
    all** -- it needs direct filesystem/config access instead: KiCad's own `fp-lib-table` config
    file(s) (global, plus a project-local one next to the `.kicad_pro`) enumerate configured
    `.pretty` library paths; footprint names inside each are `.kicad_mod` filenames, readable by
    directory listing alone for a name-searchable list. **Actually placing a found footprint**
    (parsing a `.kicad_mod` file's real pad/courtyard geometry into the plain-dict shape
    `kicad_write.build_footprint_instance` already expects) is real, separate, harder work --
    `.kicad_mod` is KiCad's S-expression format, and neither kipy nor any dependency already pinned
    in `requirements.txt` (`sexpdata`, `kiutils`, or equivalent) parses it. A new dependency, or a
    hand-rolled parser, is a real decision this spec defers to the implementation context rather than
    silently picking one here.
*   **Data Flow / Interactions:** `fp-lib-table` parsed once (or cached) → configured `.pretty`
    directory paths → directory-listed for `.kicad_mod` filenames → name-filtered against the user's
    search query → candidate list returned. No live KiCad IPC round trip needed for this slice at
    all, unlike every other route this daemon has shipped so far.
*   **Cross-Module Impacts:**
    *   `services/python-daemon`: a genuinely new module (filesystem-based, not `kicad_bridge.py`'s
        IPC pattern) for `fp-lib-table` parsing and `.pretty` directory search. Real footprint
        geometry parsing (S-expression) is separate, harder work, real dependency decision deferred.
        `library_store.save_footprint`/`load_footprint` (`CTX-304.1`) reused as-is for persistence --
        verified directly: `save_footprint` only requires a `footprint_id` key, no schema changes
        needed to persist a found footprint through it.
    *   `apps/tauri-ui`: a real find-or-create UI, distinct from `SPEC-306`'s part-search flow.
    *   Depends on `SPEC-307` (Part Detail & Library Export) per `PRODUCT-PLAN.md` §5.1 -- a
        footprint gets linked to an already-real Part.

## 3. Known Constraints & Risks
*   **Name-searchable browsing and actually-placeable footprints are two different amounts of work,
    confirmed by real source verification, not assumed equal.** Enumerating `.pretty` library paths
    and `.kicad_mod` filenames needs no new dependency and no geometry parsing. Turning a chosen
    footprint into real pads `kicad_write.build_footprint_instance` can consume requires parsing
    `.kicad_mod`'s S-expression format -- genuinely separate, harder work. Splitting these into
    separate implementation phases (or separate contexts) is the honest reflection of that gap, not
    an artificial phase boundary.
*   **`fp-lib-table` itself is also S-expression-shaped** (`(fp_lib_table (lib (name ...)...))`) --
    real verification needed on whether it's simple enough to parse with a small hand-written reader
    or whether it also wants a real S-expression library, before implementation starts.
*   **Provenance applies to footprints too**, per `PRODUCT-PLAN.md` §2.2's general rule -- when the
    datasheet-generation source (deferred, not this slice) eventually lands, a generated footprint
    needs to be marked as such and as unverified, with the same honesty `SPEC-202` already applies to
    Part fields. Not yet designed how that's represented on the `Footprint` object `library_store.py`
    already persists -- irrelevant to this slice specifically, since installed-library footprints are
    real KiCad library content, not model output.
*   **The user's own saved library and datasheet-generation sources remain real, explicitly deferred
    follow-up** -- `PRODUCT-PLAN.md` §8's open question isn't fully closed by this spec, only its
    first slice.

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
*   **What the user sees and does:** filled in for real by `CTX-308.2`, describing what actually
    shipped, not an invented design. After clicking "Save to Library" in Part Detail, a real "Find
    Footprint" section appears (reusing `ComponentDiscovery`'s own established search/select shape)
    once the saved part has no `footprint_id` yet. The user types a query and searches this
    machine's own configured KiCad footprint libraries (`CTX-308.1`'s real scope: direct
    `fp-lib-table` entries only, not yet KiCad's built-in library set); each candidate shows its
    library and footprint name with a "Use this" button. Selecting one persists the real footprint
    and links it to the part; the section then shows "Footprint linked: `<library>:<name>`" instead
    of the search form. A zero-result search shows an honest "no match in your configured
    libraries" message, not an error.

---
id: SPEC-326
title: "Component Volume Placeholders"
status: Draft
type: Feature
created: 2026-09-01
last_updated: 2026-09-01
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-326-component-volume-placeholders.md"
parent_spec: "SPEC-311-enclosure-refinement-interactive-preview.md"
child_specs: []
user_facing: true
---

# SPEC-326: Component Volume Placeholders

## 1. Executive Summary & Goals

*   **High-Level Goal:** When a component's footprint has no usable 3D model, give the enclosure a
    **stated, labelled envelope** instead of nothing — so "will it fit in the box" can be answered
    for a real design, and answered honestly about how much of it is measured.

*   **Business / Technical Value:** The maintainer's own blinking-LED project cannot currently get
    through the PCB-to-enclosure handoff. `BT1`'s footprint
    (`Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles`) references
    `Battery_Panasonic_CR2032-HFN_Horizontal.step`, which does not exist. **KiCad's own `Battery`
    library ships 53 footprints against 29 STEP models — 25 dangling references and zero `.wrl`
    fallbacks.** So "download the missing model" fails for half of a stock library, and
    `SPEC-311`'s height derivation correctly reports `unknown` and stops.

    `SPEC-325` now tells a user *which* components are in this state. This spec is what makes that
    actionable.

*   **This is a clearance question, not a rendering question.** The user does not need a model of
    their battery. They need to know whether the lid closes. That distinction is what makes a
    placeholder honest rather than a fake.

*   **Non-Goals:**
    *   **Not acquiring real models.** No manufacturer downloads, no SnapEDA/Ultra Librarian
        integration, no licensing surface. `SPEC-203` already explored and retired supplier APIs.
    *   **Not presenting a placeholder as a model.** It is an envelope with a stated basis, marked
        everywhere it appears. A user must never mistake one for real geometry.
    *   **Not writing to KiCad.** Nothing here attaches a model to a footprint or edits a board.
        `SPEC-329` owns any writing.
    *   **Not guessing a height.** See §2.3 — this is the hard part and the spec's main constraint.
    *   **Not improving `SPEC-311`'s own STEP path.** A footprint with a real, resolvable model
        keeps using it, unchanged.

## 2. System Architecture & Design Choices

### 2.1 X and Y come from the footprint's courtyard, which is real and measurable

**Decided: the envelope's footprint extents are read from the `F.CrtYd` layer of the real
`.kicad_mod`.** No inference, no LLM, no datasheet — the geometry is in a file the user already has.

Calibrated against a footprint that *does* have a model, `BatteryHolder_Keystone_1060_1x2032`:

| | X (mm) | Y (mm) | Z (mm) |
| :--- | :--- | :--- | :--- |
| Courtyard | 32.90 | 17.00 | — |
| Real STEP bounding box | 31.86 | 17.96 | 5.08 |

Close, and **not conservative in both axes**: the courtyard is 1mm wider in X and **1mm narrower in
Y** than the real body, because a courtyard is a PCB keep-out, not a 3D envelope — a part can
overhang it. Any placeholder built from it must apply a stated margin rather than be presented as a
bound.

### 2.2 Z has no honest source in the footprint, and that is the whole problem

The same calibration shows Z absent entirely: 5.08mm of real height that nothing in the
`.kicad_mod` records. A placeholder therefore cannot be derived from the footprint alone, and the
spec must say where Z comes from rather than quietly inventing it.

**And orientation is not recoverable.** `Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles` has
a courtyard of **22.59 × 4.60 mm** for a cell whose datasheet dimensions are 20mm diameter × 3.2mm
thick. Those numbers only reconcile if the cell stands *on edge*, making its real height ≈ 20mm —
the **diameter**, not the thickness. A rule of "height = the datasheet's height field" would report
3.2mm and be wrong by a factor of six, in the direction that makes a lid close in the preview and
not in reality.

### 2.3 Z is sourced, never guessed — in a stated order

**Decided, in priority order:**

1.  **A real STEP model**, if one resolves. Not a placeholder at all; `SPEC-311`'s existing path.
2.  **The app's own `package_dimensions`** for a Part matched to this component, which
    `component_extraction` already produces — with the orientation caveat in §2.2 recorded
    alongside it.
3.  **A user-supplied height**, entered once per footprint and remembered.
4.  **Unknown.** Reported as unknown, exactly as `SPEC-311` does today.

**There is no fifth option.** A default height would be the "looks fine, fails later" shape this
repository keeps paying for, and here it fails as a physical object that does not fit.

### 2.4 A placeholder is labelled everywhere it appears, including in the 3D view

**Decided: visually distinct in the enclosure preview, and named as a placeholder in every list,
export and report that includes it.** `CTX-311.12` already established that the exporter can emit
distinct materials for distinct geometry groups, so this reuses that rather than inventing a
mechanism.

A user reading a clearance result must be able to tell, without asking, which volumes were measured
and which were stated.

### 2.5 Per-footprint, not per-component

**Decided: a supplied height is keyed by footprint identity, not by reference designator.** Ten
identical resistors are one decision, not ten. It also survives a schematic edit that renumbers
references.

### 2.6 Cross-Module Impacts

*   `services/python-daemon` — courtyard extraction from `.kicad_mod`; placeholder solids in
    `freecad_bridge` (reusing `SPEC-109`'s parametric generation); `kicad.get_component_heights`
    extended to report a source per component.
*   `apps/tauri-ui` — placeholder state and the height-entry surface in `SPEC-325`'s component
    table; labelling in the enclosure preview.
*   `SPEC-311` — its `known`/`unknown` split gains a third state: *stated*.
*   `SPEC-325` — the component table is where a user sees which components need a height.
*   `SPEC-202` — `package_dimensions` becomes load-bearing for something physical, having been
    informational until now.

## 3. Known Constraints & Risks

*   **A courtyard can be absent or wrong.** Not every footprint has an `F.CrtYd` layer, and a
    hand-made one may be nominal. A footprint with no courtyard has no X/Y source and must fall
    back to the same "unknown" honesty as a missing height.
*   **`package_dimensions` is LLM-inferred.** `library_store.py`'s own comment already flags it as
    "exactly as LLM-inferred as" its neighbours. Using it for a physical clearance decision raises
    its stakes considerably, and §2.4's labelling is what keeps that honest.
*   **Orientation is the deepest problem and is not solved here.** §2.2's coin cell shows a part
    whose installed height is its diameter. This spec sources Z rather than deriving it precisely
    because no rule over available data gets that right.
*   **A placeholder that is too small is worse than none.** It produces a confident "it fits" for a
    box that does not close. Any margin applied must err large, and be stated.
*   **This makes `SPEC-311`'s output partly non-reproducible across machines.** Two users with the
    same board can get different volumes if one has a STEP the other lacks. The source-per-component
    reporting in §2.6 is what makes that visible rather than mysterious.

## 4. Module Map & Reference Links

*   `services/python-daemon/kicad_bridge.py` — `resolve_footprint_model` (SPEC-325), `list_footprint_models`
*   `services/python-daemon/freecad_bridge.py` — `get_step_bounding_box_mm`, `generate_enclosure`
*   `services/python-daemon/library_store.py` — `package_dimensions`, `courtyard` on Part
*   `services/python-daemon/daemon.py` — `kicad.get_component_heights`
*   [SPEC-311](SPEC-311-enclosure-refinement-interactive-preview.md) — parent; its unknown-height path
*   [SPEC-325](SPEC-325-kicad-project-integration.md) — supplies which components lack a model
*   [SPEC-202](../../../services/python-daemon/specs/SPEC-202-component-intelligence-pipeline.md) — `package_dimensions`
*   [CTX-311.12](../context/CTX-311.12-interior-cavity-color.md) — the distinct-material precedent §2.4 reuses

## 5. User & Interaction

*   **Product Stage:** Enclosure. After a board exists and before trusting a generated box.
*   **What the user is trying to accomplish:** Find out whether their enclosure actually clears the
    parts on their board — including the ones KiCad ships no model for, which on a simple design
    may be the tallest part on the board.
*   **What the user sees and does:** In the component table, a component with no model offers a
    height to enter, with whatever the app already knows pre-filled and its source named. In the
    enclosure preview, placeholder volumes are visually distinct from real geometry, and the
    clearance result says how many of the volumes it used were measured versus stated.

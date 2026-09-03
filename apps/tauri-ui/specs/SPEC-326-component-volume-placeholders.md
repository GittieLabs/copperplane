---
id: SPEC-326
title: "Component Volume Placeholders"
status: In-Progress
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

**Coverage measured before committing to it:** 902 of 903 footprints across five real KiCad
libraries (`Battery`, `LED_THT`, `Capacitor_THT`, `Package_DIP`, `Resistor_THT`) have a readable
courtyard — 99%.

**Accuracy calibrated against ten footprints that do have real STEP models**, comparing the
courtyard to the model's true bounding box:

| footprint | courtyard X × Y | real STEP X × Y × Z |
| :--- | :--- | :--- |
| `BatteryHolder_Keystone_1060_1x2032` | 32.90 × 21.40 | 31.86 × 17.96 × 5.08 |
| `BatteryHolder_Keystone_103_1x20mm` | 29.40 × 23.23 | 29.30 × **24.64** × 13.25 |
| `BatteryHolder_Keystone_105_1x2430` | 31.75 × 28.28 | **32.12** × **30.05** × 13.25 |
| `BatteryClip_Keystone_54_D16-19mm` | 14.10 × 20.00 | 13.97 × 16.51 × 19.86 |

**The courtyard is smaller than the real body in 4 of those 10 parts** — in X, in Y, or both. A
courtyard is a PCB keep-out, not a 3D envelope, and a part can overhang it. So it is a good
approximation and **not a bound**: any placeholder built from it must apply a stated margin, and
must never be presented as a guaranteed enclosure.

### 2.2 Z has no honest source in the footprint, and that is the whole problem

The same calibration shows Z absent entirely — 5.08mm of real height for the Keystone 1060, 19.86mm
for the `BatteryClip_Keystone_54`, and nothing in either `.kicad_mod` records it. Note also that the
tallest part in that sample is a battery clip at 19.86mm: on a simple board, the component with no
model is quite often the one that decides the enclosure height. A placeholder therefore cannot be derived from the footprint alone, and the
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

### 2.7 The schematic and the board can disagree, and every number here comes from the schematic

Everything above reads the **schematic**'s footprints. The enclosure is built around the **board**.
KiCad does not keep those in step: a schematic edit does not reach the `.kicad_pcb` until the user
runs *Tools → Update PCB from Schematic* by hand. Until they do, the two files describe different
designs — and each one opens and renders perfectly on its own, so neither KiCad view shows a
problem.

This is not hypothetical and not hygiene. It is live on the maintainer's own project, the same
board §1 is written about:

| | footprint for `BT1` | courtyard |
|---|---|---|
| schematic | `Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles` | 22.59 × 20.50 mm |
| board | `Battery_Panasonic_CR2032-VS1N_Vertical_CircularHoles` | 20.61 × 6.23 mm |

A horizontal and a vertical CR2032 holder are different heights. So the interior height this spec
recommends is derived from a part that **is not on the board being built** — a confident wrong
answer of exactly the shape §1 exists to avoid, arrived at by a different route.

**Decided: the board is the source of truth. Detect the disagreement, report it, and never
resolve it.**

The board is the thing going in the box, so the board is what gets measured. Measuring the
schematic answers a question nobody asked — how tall a box the design *would* need, if the board
matched it. The user is told which file the numbers came from and how to sync if the schematic is
the version they want.

Getting a *complete* list of what is on the board is harder than it looks, and both obvious routes
are wrong:

*   **`kicad-cli pcb export pos` silently omits footprints.** Position files honour KiCad's
    `exclude_from_pos_files` attribute — confirmed by setting it on a fixture and watching the
    component vanish from the CSV while the board was otherwise unchanged. That attribute is
    routinely set on mounting holes, fiducials, logos and test points: precisely the board-only
    mechanical parts that decide whether a board fits in a box.
*   **`kiutils` cannot read a full board at all** — `IndexError` on real boards, already recorded
    in `CTX-314.1` and re-confirmed here.

So `kicad_board.py` reads the file. Nothing can be excluded from it by an export setting, because
there is no export. Two format traps it handles, both found against real boards on this machine:
quoted values containing parentheses (`Battery_Cell (CR2032)`) which defeat a paren count, and the
pre-KiCad-7 `(fp_text reference "SW1" ...)` spelling, under which all 31 footprints of a real 2021
board read as reference `None` — a silent wrong answer, not a crash.

**The schematic remains a stated fallback.** A project whose schematic is drawn but whose board is
not laid out yet has *no* footprints on the board — one of the maintainer's own four projects is in
exactly that state. Falling back beats reporting an empty design, but `measured_from` says which
file was read, and the UI says so too. A fallback must never pass as a board measurement.

**What switching to board truth costs, on the maintainer's own board:** the 20.0mm height they
supplied is keyed to the *schematic's* horizontal holder, which is not on the board, so it no
longer applies. The recommendation drops to 15.515mm and `unknown` rises from 0 to 5. That is the
honest answer — the board's actual holder has no model and no stated height — and it is the
correct one: the previous 20.0mm described a part that is not there. Because §2.5 keys heights by
footprint, those 5 unknowns are only **2** entries to make, not 5.

*   **Detection uses KiCad's own check, not our own comparison.** `kicad-cli pcb drc
    --schematic-parity` reads the `.kicad_sch` beside a **closed** board and reports each
    disagreement under its own `schematic_parity` key, separate from `violations`. A hand-rolled
    diff of `sch export bom` footprints against `pcb export pos` packages was written first and
    produced **five** findings on this board, of which **one** was real: the other four were the
    mounting holes `H1`–`H4`, which are board-only by design and carry no schematic symbol.
    KiCad's own check reports the one real issue and stays silent about the mounting holes.
    Running it on three further boards of the maintainer's found real desyncs in all three.
*   **Reporting is the whole feature.** Resolving it means writing to the board, and choosing
    which of the two files is right is a design decision. The only mechanism available is
    `kipy`'s `run_action("pcbnew.EditorControl.importNetlist")` — the action behind the menu item,
    whose own docstring says it is unstable, not for use outside API development, and may have
    unintended side effects. It also needs KiCad running with the board focused, and opens a
    modal dialog. That is `SPEC-329` territory, deliberately deferred.
*   **One read feeds both the table and the summary.** The route returns the components it
    measured, and the UI renders those. The first version left the table on a separate schematic
    read, and shipped a panel listing 10 schematic components under a summary counting the board's
    14 — caught by the maintainer in the running app, with every test passing. Two reads of two
    files cannot be kept in step by discipline.
*   **The board check reports every kind of finding KiCad has, not just `violations`.** On the
    maintainer's board that key is empty while `unconnected_items` holds 18 entries, all severity
    `error`. `SPEC-309`'s route explained `violations` alone and so called the board clean.
*   **The warning is placed above the height recommendation**, not below it: the caveat has to
    arrive before the claim it qualifies.

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

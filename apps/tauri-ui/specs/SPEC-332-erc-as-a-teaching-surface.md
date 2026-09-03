---
id: SPEC-332
title: "ERC as a Teaching Surface"
status: In-Progress
type: Feature
created: 2026-09-03
last_updated: 2026-09-03
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-332-erc-as-a-teaching-surface.md"
parent_spec: "SPEC-319-ai-review.md"
child_specs: []
user_facing: true
---

# SPEC-332: ERC as a Teaching Surface

## 1. Executive Summary & Goals

*   **High-Level Goal:** Close the three specific things the schematic check does not do that the
    board check does — surface which tests were switched off, explain ERC's own vocabulary, and
    stop presenting a severity-filtered result as a clean one.

*   **Corrected before anything was built, 2026-09-03.** The first draft of this section claimed
    *"the schematic half got none of it"*, comparing the two routes' return values:
    `kicad_check_board` returns `violation_count`, `unconnected_count`, `parity_count` and
    `ignored_checks`; `kicad_check_schematic` returns `violation_count` and `source_path`.

    The maintainer's response — *"this seems like we just added to the schematic review"* — was
    right, and checking rather than defending showed the draft was comparing the wrong thing. An
    ERC violation **already carries its location**:

    ```json
    {"description": "Pin not connected",
     "items": [{"description": "Symbol #PWR03 Pin 1 [Power input, Line]", "pos": {...}}],
     "severity": "error", "type": "pin_not_connected"}
    ```

    and `_explain_or_report_plainly` / `_finding_for_agent` are **shared by both routes**, so the
    "keep `items`, they are the component and the pin" work `CTX-326.3` did for DRC already applies
    to ERC. The two halves are not far apart at all.

*   **What is actually missing, having looked:**

    1.  **`ignored_checks` is discarded.** KiCad's ERC report carries it — four entries on a clean
        run — and `kicad_check_schematic` never reads it. A schematic reported as clean may simply
        not have been checked for the thing that is wrong, which is the exact failure the DRC side
        already fixed.
    2.  **ERC's vocabulary has no glossary entries.** `kicadGlossary` covers the DRC nouns (PTH,
        F.Cu, `Net-(X-Y)`); ERC speaks in `pin_not_connected`, `power_pin_not_driven`,
        `lib_symbol_mismatch`, `endpoint_off_grid`. A maker reads "power pin not driven" and hunts
        for a wiring fault that is usually not there — the schematic is right and a `PWR_FLAG` is
        missing, which is a KiCad convention, not an electrical fact.
    3.  **`included_severities` is discarded.** A result filtered to errors only, presented as "no
        problems", is a lie of the same shape as the ignored-checks gap.

*   **So this is a narrow change, and the spec should say so.** It is not a second teaching
    surface; it is three specific omissions in one that already exists. Whether that deserves a
    spec at all is a fair question, and the honest answer is that the *first* item is the one worth
    the work: everything else is a paragraph of copy.

    **Delivered in `CTX-332.1` on 2026-09-03.** Nearly that size: one line in
    `kicad_check_schematic`, nine glossary entries, and no change to the findings list, because
    `SchematicAdvisor` already renders through `ViolationsList`. One correction to that claim —
    `included_severities` reached the daemon and was neither typed nor rendered, so the third
    omission was only half-closed until a `SeverityFilter` line was added. Of the three §2
    presentation questions, the tab-structure one is now settled (above); the other two remain
    open and nothing here needed them answered.

*   **KiCad already hands us what is missing.** An ERC report's own top-level keys are
    `ignored_checks`, `included_severities`, `sheets`, `source`, `kicad_version`,
    `coordinate_units`, `date` — and on a clean run of the maintainer's own schematic,
    `ignored_checks` held four entries:

    ```
    single_global_label      Global label only appears once in the schematic
    four_way_junction        Four connection points are joined together
    simulation_model_issue   SPICE model issue
    footprint_filter         Assigned footprint doesn't match footprint filters
    ```

    `run_erc` returns the report and `kicad_check_schematic` throws these away. Nothing needs to be
    computed or inferred; the data is already in the file we already parse.

*   **Nobody can currently tell whether the ERC explanation works at all.** Reported 2026-09-03:
    *"There were no errors on the schematic review so it is hard to confirm."* Correct — his
    schematic returns 0 violations, so the explanation path has never once run with real findings,
    on any provider.

*   **Non-Goals:**
    *   **Jumping to a finding on the canvas.** KiCad's own dialog centres the view on a
        double-click and `kipy` could plausibly do the same, but only with KiCad running — the
        dependency this month's work spent its effort removing. Stays in `SPEC-329`.
    *   Re-doing the DRC surface. It works; this follows it.
    *   Fixing a schematic. Copperplane explains; KiCad edits.

## 2. System Architecture & Design Choices

*   **Settled: ERC can be built and verified against committed fixtures, not personal files.**
    Measured before writing this: `services/python-daemon/tests/fixtures/parity_match.kicad_sch`,
    a 26-line fixture already in the repo, produces **4 violations across 3 types** —
    `pin_not_connected` ×2, `endpoint_off_grid`, `lib_symbol_mismatch`. So the "we cannot test this
    because the only schematic available is clean" problem does not exist, and no test needs to
    reach outside the repo.

    Deliberately verified further, by editing a copy of a real schematic and re-running ERC:

    | Edit | What KiCad reports |
    | :--- | :--- |
    | Delete one wire | 1 × `pin_not_connected` |
    | Delete the `PWR_FLAG` symbols | 2 × `power_pin_not_driven`, 2 × `pin_not_connected` |
    | Delete all 34 wires | 28 × `pin_not_connected`, 4 × `pin_not_driven`, 2 × `power_pin_not_driven` |

    Two edits that produced **nothing**, recorded so the next person does not repeat them: renaming
    a `Reference` property to force a duplicate designator, and breaking `PWR_FLAG`'s `lib_id`.
    KiCad 7+ keeps effective references in `(instances)` blocks, so editing the property text is
    inert.

*Open questions this spec must settle:*

*   ~~**Which ERC classes get a plain-language entry**~~ — delivered in `CTX-332.1`: the four
    ignored-check keys and five terms, in `kicadGlossary`'s existing flat list. **Still open:**
    whether that list and `SPEC-334`'s compositional `packageGlossary` should share a module.

*   **(Original wording, for the record)** Which ERC classes get a plain-language entry, and where
    it lives. `SPEC-334`'s
    `packageGlossary` decodes compositionally and `kicadGlossary` is a flat list for a dozen fixed
    DRC strings; ERC's vocabulary is a closed set of KiCad `type` keys (`pin_not_connected`,
    `power_pin_not_driven`, `lib_symbol_mismatch`, …), which argues for the flat list. Settle
    whether they share a module.
*   ~~**What `power_pin_not_driven` should say.**~~ Answered in `CTX-332.1`: *"Nothing on this net
    looks like a source to KiCad. Usually the wiring is right and a PWR_FLAG is missing, rather
    than the circuit being wrong."* Original reasoning kept below.

*   **(Original wording, for the record)** What `power_pin_not_driven` should say. It is the highest-value entry and the least
    obvious: the schematic is usually correct and missing only a `PWR_FLAG`, which is a KiCad
    convention rather than an electrical fact. A maker reads "not driven" and looks for a wiring
    fault that is not there.
*   ~~**Whether an ERC finding can say where it is.**~~ **Settled: do not show a schematic
    coordinate.** The maintainer, 2026-09-03: *"The user still needs to open the schematic to
    review and there is not coord markings visible that would make finding the error/issue with
    coords useful other than a general direction such as upper left so i would not add."*

    Decisive, and it applies to the board too, where the coordinate *is* shown: *"we have the coord
    show for the board review but i don't know that it is useful yet."* A millimetre position is
    only actionable against something that displays millimetre positions. KiCad's schematic editor
    shows no coordinate grid a reader can match against, so the number would buy a vague direction
    and cost a line of noise on every finding.

    What is shown instead is what a person actually searches for, and ERC already provides it:
    `Symbol #PWR03 Pin 1 [Power input, Line]` — the component and the pin, matching the text KiCad's
    own dialog shows.

    **Revisit only on evidence:** if a user says the board's coordinate helped them find something,
    the schematic's is worth reconsidering. Until then the board's own coordinate is on probation
    rather than endorsed.
*   ~~**Whether to mirror KiCad's own tab structure**~~ (Violations / Unconnected / Parity /
    Ignored). **Settled: no — and it was already settled in the board review, which this spec had
    not noticed.** The maintainer, 2026-09-03: *"we addressed the tab issue in the board review
    solution. since some tabs could be left empty, we chose a different option ... we are not using
    it in the board review either."*

    What the board review does instead, in `ViolationsList`:

    1.  **A single sentence naming each kind KiCad actually reported, with counts** — *"KiCad
        reports 0 design-rule violations, 18 unconnected items, and 4 schematic mismatches"* —
        rendered only when there is more than one kind to name. A category with nothing in it
        simply does not appear, where an empty tab would sit there inviting a click.
    2.  **One findings list**, all kinds together, each finding carrying its own severity and
        location.
    3.  **A collapsible for the checks that were switched off.**

    This works for ERC unchanged, and works *because* it is category-agnostic: ERC has one kind of
    finding rather than three, so the counts sentence stays silent and nothing looks missing. Tabs
    would have needed a decision about what to show in three empty ones.

    **The residual risk this leaves**, worth naming rather than declaring solved: a reader cannot
    filter to one kind. On a board with 18 unconnected items and 1 violation, the violation is in
    the same list as everything else. If that becomes a real complaint, filtering the one list is
    the answer, not tabs.
*   **Whether `included_severities` is worth surfacing.** The report says which severities it was
    asked for; a result filtered to errors only, presented as "no problems", would be a lie of the
    same shape as the ignored-checks gap this spec exists to close.

## 3. Known Constraints & Risks

*   **A clean schematic proves nothing**, which is the whole reason this is being specified rather
    than assumed done. Every test must run against a fixture with real violations, and the review
    path in particular has to be exercised with findings, not with "no violations found".
*   **The explanation path is shared with DRC**, so a change to how findings are rendered touches
    a surface that currently works and is verified. `CTX-326.3` records three separate review
    regressions caused by fixes to the review itself.
*   **`ignored_checks` for ERC needs its own notes.** `IGNORED_CHECK_NOTES` covers the DRC keys;
    the four ERC keys above are different and need writing, including an honest "a maker probably
    does not care" for `simulation_model_issue`.
*   **Severity is not importance.** `endpoint_off_grid` is an error and is usually cosmetic;
    `power_pin_not_driven` is an error and usually means a missing convention, not a broken
    circuit. Sorting or presenting purely by KiCad's severity would mislead.

## 4. Module Map & Reference Links

*   `services/python-daemon/daemon.py` — `kicad_check_schematic`, and `kicad_check_board` as the
    shape to match.
*   `services/python-daemon/kicad_cli.py` — `run_erc`, which already returns the whole report.
*   `apps/tauri-ui/src/lib/kicadGlossary.ts` — `IGNORED_CHECK_NOTES` and the DRC term list.
*   `apps/tauri-ui/src/components/ViolationsList.tsx` — `WhereItIs`, `IgnoredChecks`.
*   `services/python-daemon/tests/fixtures/parity_match.kicad_sch` — a committed schematic that
    already produces 4 ERC violations.
*   `apps/tauri-ui/specs/SPEC-319-ai-review.md` — parent.

## 5. User & Interaction

*   **Product Stage:** Schematic — after a KiCad project is linked, before the board is trusted.
*   **What the user is trying to accomplish:** Finding out whether their schematic has a real
    problem, and if so, what and where — without knowing what "power pin not driven" means.
*   **What the user sees and does:** Runs the schematic check and gets findings that name the
    component and pin, explain the term in a sentence, and separate "this is a real electrical
    problem" from "this is a KiCad convention you have not satisfied". Below them, the tests that
    were switched off, each with what it would have caught — the same treatment the board check
    already gives, so the two tabs stop feeling like different products.

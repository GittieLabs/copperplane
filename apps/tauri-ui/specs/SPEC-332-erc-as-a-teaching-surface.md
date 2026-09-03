---
id: SPEC-332
title: "ERC as a Teaching Surface"
status: Draft
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

*   **High-Level Goal:** Give the schematic check the same treatment the board check already got —
    findings that say where they are, what the jargon means, and which tests are switched off — so
    a maker can act on an ERC result instead of reading it twice and giving up.

*   **Business / Technical Value:** The board half of this shipped on 2026-09-02 and is now proven
    end to end: DRC findings carry KiCad's own `items` (pad, net, component, and a millimetre
    position), a static glossary expands the abbreviations without an LLM call, and
    `ignored_checks` is surfaced with a note per check saying what it would have caught. The
    schematic half got none of it.

    The gap is measurable, not a matter of taste. `kicad_check_board` returns `violation_count`,
    `unconnected_count`, `parity_count` and `ignored_checks`. `kicad_check_schematic` returns
    `violation_count` and `source_path`. That is the whole difference.

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

*   **Which ERC classes get a plain-language entry**, and where it lives. `SPEC-334`'s
    `packageGlossary` decodes compositionally and `kicadGlossary` is a flat list for a dozen fixed
    DRC strings; ERC's vocabulary is a closed set of KiCad `type` keys (`pin_not_connected`,
    `power_pin_not_driven`, `lib_symbol_mismatch`, …), which argues for the flat list. Settle
    whether they share a module.
*   **What `power_pin_not_driven` should say.** It is the highest-value entry and the least
    obvious: the schematic is usually correct and missing only a `PWR_FLAG`, which is a KiCad
    convention rather than an electrical fact. A maker reads "not driven" and looks for a wiring
    fault that is not there.
*   **Whether an ERC finding can say where it is.** DRC findings carry a millimetre position on a
    board. A schematic coordinate is a sheet plus an x/y, which is meaningful only if the user can
    act on it — and without `kipy` there is no way to move KiCad's view. Decide whether to show it
    at all, or to name the component and pin instead, which is what a person actually searches for.
*   **Whether to mirror KiCad's own tab structure** (Violations / Unconnected / Parity / Ignored).
    Left open since `SPEC-332` was first sketched, and still undecided; the current build uses one
    findings list plus a collapsible for ignored tests.
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

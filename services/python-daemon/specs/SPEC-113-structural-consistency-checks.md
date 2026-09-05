---
id: SPEC-113
title: "Structural Consistency Checks"
status: Draft
type: Feature
created: 2026-09-05
last_updated: 2026-09-05
target_version: v0.6.0
location: "services/python-daemon/specs/SPEC-113-structural-consistency-checks.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
user_facing: true
---

# SPEC-113: Structural Consistency Checks

## 1. Executive Summary & Goals

*   **High-Level Goal:** Compute the class of defect that ERC and DRC cannot see, deterministically,
    from files the app already reads -- so that it appears in a review the user did not have to
    know how to ask for.

*   **The gap, stated exactly.** The tutorial and the product video both lead with D1: a two-pin
    `Device:LED` symbol carrying a four-pin `LED_THT:LED_D5.0mm-4_RGB` footprint. Two pads with no
    net, one resistor where an RGB LED wants three. It is the clearest argument the product has.
    **It only appears if the user asks for it.** The review does not raise it, so the person who
    would benefit most -- someone who does not yet know this failure mode exists -- is exactly the
    person who will never type the question.

*   **KiCad genuinely cannot see it, and this was measured rather than assumed.**
    `kicad-cli pcb drc --schematic-parity --severity-all` on the tutorial board reports
    **0 schematic parity issues** and 4 DRC violations, all `annular_width`. The mismatch is
    invisible to every check KiCad ships. That is what makes this worth building and not merely a
    prompt change.

*   **It is deterministic, which is the whole point.** A symbol's pin count and a footprint's pad
    count are facts in files on disk. Making an LLM *discover* them is why the finding is
    unreliable today. The model's job should be to explain a finding, exactly as it already does
    for ERC and DRC output (`chat_agents._REVIEW_PROMPT`), never to notice it.

*   **Non-Goals:**
    *   **Not a replacement for ERC, DRC, or schematic parity.** It runs alongside them and its
        findings must be visually distinguishable from KiCad's own.
    *   **Never edits anything.** Every output is a sentence.
    *   **Not a manufacturability opinion.** `SPEC-327` owns layout and clearance judgement; this
        spec owns only disagreements that are true or false, not better or worse.

## 2. System Architecture & Design Choices

*   **The rule, and the evidence it already survived.** The check is: for each component, compare
    the schematic symbol's pin count against the count of distinct **numbered, plated** pads on its
    footprint. Run against the tutorial board this yields exactly two findings, both real:

    | Ref | Symbol | Pins | Footprint | Numbered pads | |
    | :--- | :--- | :--- | :--- | :--- | :--- |
    | D1 | `Device:LED` | 2 | `LED_THT:LED_D5.0mm-4_RGB` | 4 | the documented case |
    | SW1 | `Switch:SW_Push` | 2 | `Button_Switch_THT:KSA_Tactile_SPST` | 5 | not previously noticed |
    | R1 | `Device:R` | 2 | 2-pad THT | 2 | silent |
    | A1 | `MCU_Module:Arduino_UNO_R3` | 32 | 32 numbered + 4 unnumbered NPTH | 32 | silent |
    | H1-H4 | none, board-only | -- | 1 | -- | silent |

*   **The obvious cheaper rule is wrong, and there is a measurement to prove it.** "Flag pads with
    no net" was tried first. It reports D1, SW1 **and A1** -- A1 because a shield header legitimately
    carries four unplated mechanical holes. Excluding `np_thru_hole` pads and pads with an empty
    number removes that false positive entirely. This must be stated in the spec because the same
    trap has already been walked into once in this repo: `kicad_cli.check_schematic_parity`'s own
    docstring records a hand-rolled footprint diff that produced five findings of which one was
    real, the other four being mounting holes.

*   **SW1 is why severity is a design question, not a detail.** D1 is broken -- an RGB LED with one
    resistor and two dead pins was never going to work. SW1 is a four-legged tactile switch whose
    unconnected legs are internally common with the connected ones, so it will probably function.
    Both are the same structural fact and they are not the same problem. The spec must settle
    whether this check emits one severity or grades itself, and on what evidence, because a warning
    that cries wolf on SW1 costs the credibility that makes the D1 finding land.

*   **Where the finding enters.** `chat_agents._check_status_note` already reads
    `Project.last_results[area]` and feeds real ERC/DRC findings into the review prompt, and
    `library_store.set_project_check_result` already persists them. The intended shape is a third
    source alongside those two, so the model explains rather than discovers. Whether structural
    findings are stored under the same `last_results` key or their own is open.

*   **What it does when it cannot tell.** A component whose symbol cannot be resolved -- a custom
    library the user has not registered, a board-only footprint with no symbol at all -- must
    produce silence or an explicit "could not compare", never a mismatch. H1-H4 are the live
    example: they have no schematic symbol and must never be flagged.

*   **Open question: which other checks belong in this family.** Structural consistency is a
    category, not one rule. A footprint assigned to no symbol, a value that disagrees between
    schematic and board, a part whose datasheet pin count disagrees with both. Each needs the same
    bar this one cleared: measured against a real board, with its false positives counted.

## 3. Known Constraints & Risks

*   **A false positive here is more expensive than a missed finding.** This check's entire claim is
    "we see what KiCad cannot". The first time it is confidently wrong about a board the user
    understands better than the app does, that claim is spent.
*   **Symbol pin counts come from the `.kicad_sch`'s embedded `lib_symbols`, not from the user's
    installed libraries.** That is a feature -- it is what the schematic actually contains -- but it
    means a schematic saved by an older KiCad may not carry them.
*   **This has been measured on exactly one board**, on one machine, with KiCad 9. That is stated
    here rather than discovered later.

## 4. Module Map & Reference Links

*   `services/python-daemon/kicad_board.py` -- already parses `.kicad_pcb`; pads are not read yet.
*   `services/python-daemon/kicad_cli.py` -- `check_schematic_parity`, whose docstring holds the
    false-positive precedent this spec is built to avoid repeating.
*   `services/python-daemon/chat_agents.py` -- `_check_status_note`, `_REVIEW_PROMPT`.
*   `services/python-daemon/library_store.py` -- `set_project_check_result`.
*   [SPEC-319](../../../apps/tauri-ui/specs/SPEC-319-ai-review.md) -- the review that surfaces this.
*   [SPEC-327](../../../apps/tauri-ui/specs/SPEC-327-design-advice-layout-and-clearance.md) -- the
    judgement-class sibling; this spec is the true-or-false half.
*   `docs/site/src/content/docs/tutorials/blink-leds.md` -- "The mistake nothing flags".

## 5. User & Interaction

*   **Product Stage:** Review -- the existing schematic and PCB reviews, wherever ERC and DRC
    findings already appear.

*   **What the user is trying to accomplish:** Finding out what is wrong with their board before
    they order it, without knowing in advance which questions to ask. The person this is for cannot
    ask "is my footprint's pad count consistent with my symbol's pin count", because if they could
    they would not have made the mistake.

*   **What the user sees and does:** Nothing new to click. Running the review they already run
    produces an additional finding in plain language -- which component, which symbol, which
    footprint, what the disagreement is -- marked as coming from Copperplane rather than from
    KiCad, so it is never mistaken for a DRC violation. The current behaviour, where the same fact
    is available only by typing a question into the agent panel, is the failure this replaces.

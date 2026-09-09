---
id: SPEC-341
title: "One Findings List Per Area"
status: Draft
type: Feature
created: 2026-09-08
last_updated: 2026-09-08
target_version: v0.7.0
location: "apps/tauri-ui/specs/SPEC-341-one-findings-list-per-area.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-341: One Findings List Per Area

## 1. Executive Summary & Goals

*   **High-Level Goal:** Give each area one action that checks the design and one list of what it
    found, with every finding saying what found it. Today the PCB and Schematic tabs each carry two
    panels that run the same check engine independently, show different halves of the answer, and
    never refer to each other.

*   **Business / Technical Value:** This was reported by the maintainer using the app, twice, in
    almost the same words both times — first about the fabrication check duplicating the board
    check, then about the review duplicating it again:

    > "the check seems to show very similar info to what the review board does. what is the
    > disconnect?"
    >
    > "It also seems the review is disconnected from the drc card section. this is similar in the
    > schematic erc card and review below it."

    The first report was fixed inside `SPEC-340` by folding the fabrication profile into
    `kicad.check_board`. The second is the same shape one level up and cannot be fixed inside
    `SPEC-340`, because it is about the relationship between `SPEC-309`'s check and `SPEC-319`'s
    review across every area. `SPEC-340` shipped a cross-reference between the two panels as an
    interim measure; this spec is the actual repair.

*   **The concrete symptom.** On the tutorial board, the review panel reports **"2 findings"** while
    the same board has four annular-ring errors and a missing GND connection sitting in the DRC card
    above it. Neither number is wrong. The review deliberately lists only what ERC and DRC do *not*
    report, which is `SPEC-113`'s entire pitch. But a user reading "2 findings" has no way to know
    it means "2 more, on top of the 5 you were shown separately", and the app never says so.

*   **Non-Goals:**
    *   **Not changing what any check finds.** `SPEC-113`'s structural checks, KiCad's ERC and DRC,
        and `SPEC-114`'s capability profiles all keep their current semantics. This is about how
        their results are presented, not what they are.
    *   **Not removing the AI explanation.** The per-finding plain-language explanation is the most
        valuable thing on these screens and the merged list must keep it.
    *   **Not touching the Enclosure area** in the first pass; it has one surface today and does not
        have this problem.

## 2. System Architecture & Design Choices

### 2.1 The measurement this spec needs before it is built

**How many times is a check actually run per area today, and what does each run cost?** The answer
is believed to be three on the PCB tab with a profile set — `kicad.check_board`'s own DRC, the
baseline-plus-verified pair inside `fabrication_review`, and a third inside `chat_agents`'
`_check_status_note`, which deliberately re-runs rather than reading a stored result — but that is
inference from reading the code, not a measurement.

It matters because the merge's main practical benefit is doing that work once, and the main risk is
that consolidating changes when the LLM explanation call happens and therefore what it costs. The
same discipline `SPEC-114` §2.1 used applies: measure it, write the numbers down, and let the design
follow them. Building this on the assumption above without checking would repeat exactly the mistake
`SPEC-114` §2.2 was written to prevent.

### 2.2 The shape the merge probably takes

Recorded as a starting proposal, explicitly not a decision:

One action per area — "Check this board" — running KiCad's own check, the structural checks, and
schematic/board parity, returning one list. Each finding carries what produced it, which the review
panel already models: `origin: 'kicad' | 'copperplane'`, rendered today as a "Not reported by ERC or
DRC" badge. That vocabulary exists and works; the merge is largely a matter of putting both kinds of
finding through it.

The open question underneath is whether "review" survives as a separate concept at all, or becomes
the narrative summary that sits above one merged list. That is a product decision, not a technical
one, and it should be made against a real screen rather than in prose.

### 2.3 Why the interim cross-reference is not enough

`SPEC-340` made each panel name the other and state the other's count. That is honest and it removes
the "2 findings" misreading. It does not remove the two independent check runs, the two places a
user has to look, or the question of which one to run first. It buys time; it is not the answer.

## 3. Known Constraints & Risks

*   **The explanation call is the expensive part.** `explain_violations` caps at 15 findings and
    ranks by severity before spending. A merged list is longer, so what gets explained — and what is
    truncated — becomes a visible product decision rather than an implementation detail.
*   **`SPEC-339` persists reviews and `CTX-339.1` exists specifically to avoid charging twice.** Any
    merge has to keep that property, and a merged result is a bigger thing to persist.
*   **The review panel is used by more than these two areas.** It appears on Overview and Components
    as well, where there is no ERC/DRC sibling. A merge that assumes a sibling check will break
    those surfaces.
*   **`_check_status_note` re-runs deliberately, and that reasoning is sound.** It exists because a
    stored finding can be stale in ways the app cannot detect. Consolidating runs must not
    accidentally reintroduce cached staleness, which is a correctness regression dressed as an
    optimisation.
*   **This is the third time this shape has appeared.** `SPEC-302` shipped three functions sharing
    one text box; `SPEC-340` shipped a third overlapping check on the PCB tab. A spec that merges
    two panels without asking what else is already on the screen will produce a fourth.

## 4. Module Map & Reference Links

*   `apps/tauri-ui/src/components/BoardAdvisor.tsx` — the PCB check card and its board picker.
*   `apps/tauri-ui/src/components/SchematicAdvisor.tsx` — the same shape for ERC.
*   `apps/tauri-ui/src/components/ReviewPanel.tsx` — the review, its `origin` badges, and the
    interim `siblingCheck` cross-reference.
*   `apps/tauri-ui/src/components/ViolationsList.tsx` — the findings renderer both would share.
*   `services/python-daemon/chat_agents.py` — `_check_status_note`, the third DRC run.
*   [SPEC-309](SPEC-309-board-advisor.md) — the check card this spec would absorb or be absorbed by.
*   [SPEC-319](SPEC-319-ai-review.md) — the review, and the `origin` vocabulary worth keeping.
*   [SPEC-113](../../../services/python-daemon/specs/SPEC-113-structural-consistency-checks.md) —
    the findings that exist precisely because ERC and DRC do not report them.
*   [SPEC-332](SPEC-332-erc-as-a-teaching-surface.md) — ignored checks, already rendered once.
*   [SPEC-340](SPEC-340-ordering-this-board-from-a-real-house.md) — the interim cross-reference, and
    the first half of this problem.

## 5. User & Interaction

*   **Product Stage:** Schematic and PCB, whenever someone wants to know what is wrong with their
    design.

*   **What the user is trying to accomplish:** Finding out what is wrong with their design — not
    what each of the app's internal checkers thinks separately.

*   **What the user sees and does:** One action per area, and one list of findings, each saying what
    found it and what to do about it. A user should never have to work out whether two panels are
    describing the same problem, and should never see a count that is true only for one half of the
    work the app did.

*   **How we will know it worked:** Someone opens the PCB tab on a board with both kinds of problem,
    runs one thing, and can say how many problems their board has. Today that question has two
    answers on one screen and the app does not reconcile them.

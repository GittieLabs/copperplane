---
id: SPEC-340
title: "Ordering This Board From a Real House"
status: Draft
type: Feature
created: 2026-09-08
last_updated: 2026-09-08
target_version: v0.6.0
location: "apps/tauri-ui/specs/SPEC-340-ordering-this-board-from-a-real-house.md"
parent_spec: "SPEC-325-kicad-project-integration.md"
child_specs: []
user_facing: true
---

# SPEC-340: Ordering This Board From a Real House

> **Spec Reference:** the surface for
> [SPEC-114](../../../services/python-daemon/specs/SPEC-114-fabrication-capability-profiles.md)'s
> capability profiles.

## 1. Executive Summary & Goals

*   **High-Level Goal:** Let someone say which board house they are about to order from, and then
    show them where their board sits against that house's published limits — separating problems
    a fab would reject from the ones it would build silently wrong. `SPEC-114` built and verified
    every capability this needs; not one of them is reachable by a person today.

*   **Business / Technical Value:** `CTX-114.1` shipped three daemon routes, a verified sidecar
    generator, and a measured proof surface — 4 findings becoming 27 on the tutorial board — and
    closed with the sentence *"no user has used this."* Under this repo's own norm, written after
    `SPEC-302` shipped a mechanically perfect feature nobody could use, that means the feature is
    **not verified**. This spec is what makes it real, and it is deliberately small: the hard,
    dangerous, measured work is already done and behind a route.

*   **Non-Goals:**
    *   **No bundled profiles for named board houses.** `SPEC-114` section 2.9 calls real numbers a
        research task and section 3 warns that a too-strict profile spends the credibility this
        family runs on. `CTX-114.1` Deviation 6 declined to invent figures and attribute them to a
        real vendor; this spec does not reopen that. The user brings their own numbers, or uses
        the explicitly unbranded starting point.
    *   **No writing to `.kicad_pro`.** Limit 1 stands: a rule the project has set to `ignore` is
        reported, never re-enabled.
    *   **No "ready to order" verdict**, in any wording. Section 3 of `SPEC-114` is explicit, and
        this surface is where the temptation actually lives.
    *   **Not the enclosure or schematic areas.** This is the PCB area only.

## 2. System Architecture & Design Choices

*   **Design Rationale.** Every decision here is about not squandering what was already measured.

    **The profile is per project, not per install** (`SPEC-114` section 2.9). The same design may go
    to two houses, and a profile chosen for one project must not silently follow the user to the
    next. It persists through `library_store`'s existing project record, the way `intent` and
    `last_results` already do, so it travels with a linked project folder at no extra cost.

    **The before-and-after is the whole screen, not a detail.** `SPEC-114` section 2.8 calls it
    the entire argument in one view. The route already returns both counts; this surface must not
    reduce that to a single number: "27 findings" alone reads as a broken board, while "4 with
    KiCad's defaults, 27 against the house you picked" reads as the discovery it actually is.

    **What was not checked is part of the result, not a footnote.** The route returns three separate
    honesty fields — checks the project ignores, profile rules gated off by those, and numbers
    recorded that no DRC constraint can enforce. A surface rendering only `findings` would be
    quietly claiming a completeness the daemon deliberately refused to claim.

    **Staleness and confirmation are shown before ordering, not after.** Every field carries the
    date it was recorded and whether the user confirmed it. The bundled starting point ships with
    all nine fields unconfirmed on purpose, so the UI has something true to say.

*   **Data Flow / Interactions.** No new daemon work. Three routes exist on `develop`:

    | Route | Async | Returns |
    | :--- | :--- | :--- |
    | `fabrication.generic_profile` | no | The unbranded starting point, all fields unconfirmed |
    | `fabrication.validate_profile` | no | Enforceable, unenforceable, unconfirmed, stale |
    | `fabrication.review_board` | yes | Before and after counts, ranked findings, `not_checked` |

    `fabrication.review_board` runs two or three real `kicad-cli` invocations and is registered in
    `ASYNC_ROUTES`, so it goes through the existing `JobHandle` client from `CTX-105.2` rather than
    blocking. Measured at roughly five seconds on the example board.

*   **Cross-Module Impacts.** `library_store` gains one persisted field on the project record.
    `SPEC-319`'s review panel is the natural host for the findings list, and `SPEC-332` already
    renders ignored checks — that component should be reused rather than reimplemented.

### 2.1 The one genuinely new decision

Everything else here is plumbing. This is not: **what the user sees when the sidecar could not be
verified.**

`fabrication.review_board` can come back `indeterminate` — the board has no copper track for the
verification canary to catch, so whether the rules took effect cannot be observed. It is rare and it
is honest, and it must not be flattened into either a pass or a failure. The result is real; the
confidence in it is not. This surface needs a third state, and inventing one is the only design work
this spec actually contains.

A `SidecarDiscarded` error is different and simpler: the rules provably did not run, so there is no
result to show at all.

## 3. Known Constraints & Risks

*   **This is the screen where "you're good to order" wants to be written.** Every summary string
    should be read against that. The daemon's own `summarize()` refuses it; a caption added here
    could reintroduce it in one line.
*   **A too-strict profile manufactures findings.** If a user types their house's advanced-process
    numbers while ordering the standard process, the app produces confident findings about a board
    that is fine. The mitigation is showing which process the numbers describe, next to the numbers.
*   **27 findings is reviewable; a denser board will not be.** The ranking exists but has only ever
    been exercised against one board. Ordering is settled in `SPEC-114` section 2.9 as a proposal,
    and this surface is where it is either confirmed or corrected against a real reading.
*   **The measurements behind all of this are from one machine, one board, KiCad 10.0.3.**
    `SPEC-403` owns that gap. Nothing here narrows it.
*   **`via_diameter` and `thermal_spoke_width` remain unmeasured**, so a profile cannot offer them.
    A user who knows their house publishes a minimum via diameter will look for the field and not
    find it; saying why beats omitting it silently.

## 4. Module Map & Reference Links

*   `services/python-daemon/capability_profile.py` — the record, its provenance rules, and which
    fields can never be enforced.
*   `services/python-daemon/fabrication_review.py` — the before-and-after, ranking, and the
    `not_checked` surface this spec must render.
*   `services/python-daemon/kicad_dru.py` — the verification the three states come from.
*   `apps/tauri-ui/src/lib/degradedModules.ts` — already carries plain-language descriptions for
    both new modules.
*   [SPEC-114](../../../services/python-daemon/specs/SPEC-114-fabrication-capability-profiles.md) —
    the capability, and every measurement this surface depends on.
*   [SPEC-319](SPEC-319-ai-review.md) — the review panel that hosts the findings.
*   [SPEC-332](SPEC-332-erc-as-a-teaching-surface.md) — already renders ignored checks.
*   [SPEC-325](SPEC-325-kicad-project-integration.md) — parent; the PCB area this lives in.

## 5. User & Interaction

*   **Product Stage:** PCB, after a board exists and before it is ordered.

*   **What the user is trying to accomplish:** Finding out whether the board they are about to pay
    for will come back the way they drew it — without knowing what an annular ring is, and without
    having read their board house's capability page.

*   **What the user sees and does:** In the PCB area they name the house and process they intend to
    order from, once per project, either accepting the unbranded starting point or entering their
    own published numbers. The board check then reports against those numbers alongside KiCad's own,
    showing both counts so the difference the choice made is visible rather than implied. Findings
    are grouped by what the fab would actually do with them — rejected, or built silently wrong —
    and the result states plainly which of their numbers could not be checked and why.

*   **How we will know it worked:** A person who has never heard the phrase "annular ring" picks a
    profile on the tutorial board, sees the count go from 4 to 27, and can say out loud which of
    those findings would have come back as a working board that was quietly wrong. Until someone has
    actually done that, this spec is unverified no matter how green its tests are.

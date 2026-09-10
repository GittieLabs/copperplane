---
id: SPEC-343
title: "The Guided Path"
status: Draft
type: Feature
created: 2026-09-10
last_updated: 2026-09-10
target_version: v0.7.0
location: "apps/tauri-ui/specs/SPEC-343-the-guided-path.md"
parent_spec: "SPEC-300-product-ia-interaction-model.md"
child_specs: []
user_facing: true
---

# SPEC-343: The Guided Path

## 1. Executive Summary & Goals

*   **High-Level Goal:** One place that always answers *where am I, and what would move this
    forward* — without hiding anything, interrupting anyone, or deciding for them.

*   **The gap, stated by the maintainer:** every vertical slice of this product is strong on its
    own, and nothing joins them. *"We are making the assumptions that a project exists with a
    schematic that adheres to the goal that also has a matching pcb with components connected ready
    for an enclosure. This isn't wrong. We can be helpful at any of these tasks independently by
    design. But we also need to provide an option that would start from scratch, understand the
    goal, provides real guidance to get started and remembers where we left off."*

*   **The audience this is for, and the failure it exists to prevent.** A maker, not a professional.
    *"The maker wants to finish a project and not get discouraged or confused enough to say our app
    is not helpful bc they got lost."* Every decision below is answerable against that sentence.

*   **The flow is not linear and the design must not pretend otherwise.** Reviewing the PCB can send
    someone back to the schematic; teaching about either can change both; a project's considerations
    change when its schematic does. `SPEC-300` already calls the stage machine *"a DAG, not a
    wizard"*. This spec's job is to make the DAG legible, not to straighten it.

*   **Non-Goals:**
    *   **Not hiding views.** Ruled out explicitly by the maintainer, and it contradicts
        `SPEC-300`'s *"every stage is enterable directly"*. A novice who cannot find what someone
        told them about, in an app that decided for them, is a worse outcome than a busy tab bar.
    *   **Not a wizard.** No step lock, no forced order, no blocked stage.
    *   **Not chat.** See §2.1 — `SPEC-300` forbids it, and that constraint is the shape of this
        whole spec rather than an obstacle to it.
    *   **Not new knowledge.** Everything shown here is already computed by `SPEC-210`,
        `SPEC-328`, `SPEC-113`, `SPEC-339` and the check surfaces. This is where it is joined, not
        where it is invented.

## 2. System Architecture & Design Choices

### 2.1 Inherited from `SPEC-300`, not re-decided here

Two of that spec's rules settle most of this one, and both are load-bearing:

> *"A conversation surface can only ever produce an answer, never advance a stage, mutate a record,
> dispatch a flow step, or change which screen the user is on."*

**So the guided path cannot be chat.** This is why the existing per-area chat reads as user-initiated
rather than guiding: it was built that way deliberately. Any design where the agent walks someone
through stages violates a rule that exists to stop the app doing things nobody asked for.

> *"The stage machine is a DAG, not a wizard. Every stage is enterable directly."*

**So nothing is hidden and nothing is locked.** The guided path is a *reading* of the project, laid
beside the tabs, never in front of them.

### 2.2 The trigger is the timing

The maintainer's question, and the one this spec turns on: *"how/when do we tell the user anything
that we know they could be missing and that we know they need. Is that only done when they describe
their project?"*

**No — and description time is the worst moment for most of it.** `SPEC-210` §2.2 already settles
the timing without a new rule: a consideration cannot exist before its trigger is true, and once the
trigger is true it is as specific as it will ever be. So:

> **Say it when the trigger becomes true, not when the topic becomes relevant.**

The same knowledge legitimately arrives twice, at different specificity, because different triggers
fire. Measured on the maintainer's own board:

| moment | trigger | what it can say |
| :--- | :--- | :--- |
| intent stated | *"a blinking led controlled by a pushbutton"* | *"current-limiting resistor — without one in series, the LED will draw too much current from the Arduino pin"* |
| schematic saved | net `+5V` carries `D1`'s anode and no resistor | *"D1's anode is on +5V, and nothing on that net is a resistor"* |

Neither is redundant, and **the second could not have been said at description time** — there was no
`+5V` to point at. This is the argument against front-loading: saying everything at intent time means
saying all of it in its vaguest form, before any of it is actionable, which is exactly the
fourteen-things-on-day-one that makes a maker close the app.

### 2.3 Three trigger sources, and only one involves the user describing anything

*   **Intent.** What they said they are building (`SPEC-328`).
*   **A file.** The schematic or board changed, so the netlist changed, so packs re-run
    (`SPEC-210`, `CTX-210.1`). Nobody described anything; the app read a file.
*   **An answer.** A structured intent field changed what is in scope. `board_stage: being_sold`
    brings ESD, reverse polarity and connector keying into scope without the board changing at all
    — and `SPEC-210` §1 requires the app to be able to say those arrived *because that answer
    changed*.

### 2.4 Stage is computed, never declared

The project record already holds enough to say where someone is, with no new storage and nothing for
the user to set. Measured against the maintainer's three real projects:

| record state | what it means |
| :--- | :--- |
| no `intent` | never said what this is for |
| `intent`, no `kicad_project_path` | a goal and no files yet |
| both, no `last_results` | a design nothing has checked |
| `last_results` present, `stale_reason` set | **went back a stage** — the check is behind the file |

**The cycling is observable rather than asked about.** `CTX-210.1` Phase 4 reuses `SPEC-339`'s
staleness so a consideration set carries its source and goes stale when that file changes. *"You
edited the schematic, so the PCB check is behind"* is computed. A user never tells this app which
stage they are in, which is the only way a non-linear flow stays honest.

### 2.5 What may be volunteered is already decided

`SPEC-210` §1's initiative rule is the boundary between guidance and conversation, and it needs no
extension here:

*   **Computed and cited** claims may be raised unprompted. That is the guided path's content.
*   **A judgement** waits to be asked. That is chat's content.

So the two surfaces divide on a principle rather than on taste, and a new pack cannot accidentally
make the app opinionated — the rule is enforced in `considerations.py`, not in this spec's prose.

### 2.6 Telling, when the app may not interrupt

Given §2.1, *telling* reduces to **it is there when they look, and something makes them look.** The
only mechanism that violates nothing is a count on the Overview tab: a signal that something changed,
which the user may ignore entirely. No modal, no redirect, no chat message arriving unbidden, no
stage advanced on their behalf.

Which reframes the design question usefully — not *when do we tell them*, but *what makes Overview
worth returning to*. It changes when their project changes, without them asking.

*Open questions this spec must settle:*

*   **Absence-shaped triggers, and this is where the value probably is.** What a novice is missing is
    usually a part that is not there, so the trigger is an empty set rather than a present thing.
    `CTX-210.1` withdrew `power_pin_without_decoupling` because it could not distinguish a supply
    rail from ground — but the *shape* is legitimate and unresolved. An absence still has to name
    something real (§2.2): *"no capacitor on `+5V`"* names `+5V`. Settle what makes an absence
    nameable, because the alternative is the app staying silent about exactly the class of thing a
    beginner most needs.
*   **What "off" means.** Quiet entirely, or still *where am I* without the teaching? Those are
    different products for someone returning to a half-finished board.
*   **Whether a new project defaults it on.** Defaulting on and being dismissible means the novice
    gets it without choosing and the second-time user turns it off once; defaulting off means the
    people who need it most never see it.
*   **Ordering when several things are true at once.** `SPEC-210` §2.6 left the same question and
    named *"would this have built silently wrong"* as probably the right ranking. Answer both
    together.
*   **What the one sentence says when nothing is wrong.** A guided surface with nothing to report is
    where reinforcement belongs (`SPEC-210` §2.3), and generic praise is worse than silence.

## 3. Known Constraints & Risks

*   **A guided surface that is wrong once is worse than none.** It speaks with the app's whole voice
    rather than one stage's. `SPEC-210` §3 already says the first confidently wrong claim spends the
    family; this surface is where that spending happens fastest.
*   **Legibility is not the same as progress.** A user can be told exactly where they are and still
    be stuck. The measure is whether they take the next action, not whether the sentence is accurate.
*   **The DAG has no end state, and the UI will imply one.** Any *what's next* wording risks reading
    as a checklist with a bottom. A board is never finished; it is ordered.
*   **Everything here is designed against one maintainer's three projects**, two of which are the
    same tutorial board. Stated now rather than discovered later.

## 4. Module Map & Reference Links

*   [SPEC-300](SPEC-300-product-ia-interaction-model.md) — parent. Owns the stage machine, the
    navigation rule and the AI boundary this inherits. **Read §2's stage-machine and AI-boundary
    bullets before designing anything here.**
*   [SPEC-210](../../../services/python-daemon/specs/SPEC-210-design-considerations-model.md) — the
    considerations, the trigger discipline, and §1's initiative rule that splits guidance from chat.
*   [SPEC-328](SPEC-328-project-intent-and-suggested-parts.md) — intent, the structured fields, and
    the first trigger source.
*   [SPEC-339](SPEC-339-review-persistence-and-staleness.md) — the staleness mechanism §2.4 reuses
    to detect a stage regression.
*   [SPEC-313](SPEC-313-overview-tab-project-dashboard.md) — the tab this lands on.
*   `services/python-daemon/library_store.py` — the project record §2.4 computes stage from.
*   `apps/tauri-ui/src/components/Overview.tsx` — where it renders.

## 5. User & Interaction

*   **Product Stage:** Overview, across the whole project rather than any one stage.

*   **What the user is trying to accomplish:** Finishing a board without getting lost — knowing at
    any moment whether they are on track, and what one thing would move them forward.

*   **What the user sees and does:** On Overview, one sentence saying where the project stands and
    one action that would advance it, with anything the app has learned since they were last here
    shown beneath. They click the action, which takes them to the tab that already exists, or they
    ignore it entirely and use the tabs directly. Nothing is hidden from them, nothing happens
    without them, and the surface can be turned off for the project and back on at any point.

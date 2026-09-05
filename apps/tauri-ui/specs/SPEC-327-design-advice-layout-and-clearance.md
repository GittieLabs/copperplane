---
id: SPEC-327
title: "Design Advice: Layout & Clearance Warnings"
status: Draft
type: Feature
created: 2026-09-05
last_updated: 2026-09-05
target_version: v0.6.0
location: "apps/tauri-ui/specs/SPEC-327-design-advice-layout-and-clearance.md"
parent_spec: "SPEC-325-kicad-project-integration.md"
child_specs: []
user_facing: true
---

# SPEC-327: Design Advice: Layout & Clearance Warnings

## 1. Executive Summary & Goals

*   **High-Level Goal:** Say the things about a board that are true and that no rule checker will
    ever tell you, using only what `SPEC-325` already reads. Advise; never edit.

*   **Why this is a different job from DRC.** DRC answers "did you break a rule you configured".
    It cannot answer "are these two parts too close to solder comfortably", "is this board mixing
    through-hole and surface-mount in a way that costs you an assembly step", or "there is nowhere
    to screw this down". Those are judgements about a design rather than violations of a
    constraint, and they are exactly what a maker moving from breadboard to PCB does not yet know
    to ask.

*   **The precedent is already in the product, and it landed well.** The board review already
    emits a finding nobody's DRC produced: *courtyard checking is turned off, which affects the
    enclosure-sizing tool*. Nothing was violated. It was noticed because something else in the app
    depends on it, and it is the clearest illustration in the tutorial of what this app adds. This
    spec is that idea, deliberately.

*   **Non-Goals:**
    *   **Never edits the board.** Every finding is a sentence, not a fix. `SPEC-329` owns writing.
    *   **Not a replacement for DRC.** It runs alongside and says so; a reader must never come away
        thinking these warnings substitute for KiCad's own checks.
    *   **Not a manufacturability quote.** Fab-house-specific rules are a different product.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **Which advice, and how it is justified.** The roadmap names mixed through-hole and SMD,
    components too close together, missing mounting holes, undeclared off-board connections, and
    trace width. Each needs a defensible threshold and a stated source, or the app is guessing with
    confidence. "Too close" is meaningless without a number and a reason for that number.

*   **How advice is separated from findings.** The board review already distinguishes `WARNING`
    from `SUGGESTION`. Whether layout advice joins that list or occupies its own surface changes
    whether a user reads it as "your board is wrong" or "here is something to think about".

*   **What it does when it cannot tell.** Six of eight components on the tutorial board have no 3D
    model, so their heights are unknown. Any clearance advice inherits that: the honest output is
    frequently "these two might collide, and I cannot measure one of them". The product already
    does this well for enclosure height; the same discipline has to hold here.

*   **Where it lives.** The roadmap proposes the PCB tab becoming a component table plus board view
    plus warnings — the same shape as the schematic table. Whether that replaces the current DRC
    panel or sits beside it is a real IA decision, and the tab is already busy.

*   **How much is arithmetic and how much is a model.** Component spacing is geometry and should be
    computed, not asked of a language model. "Is this header's off-board connection undeclared" is
    closer to judgement. The line between them decides how much of this is deterministic and
    therefore testable.

## 3. Known Constraints & Risks

*   **Advice that is wrong is worse than no advice.** A maker who has not built a board cannot
    evaluate a warning; they will act on it. A confident false positive costs them a redesign, and
    the credibility does not come back.

*   **Volume is a real failure mode.** A board with forty passives will trip a naive spacing rule
    forty times. The board review's grouping — four annular violations shown as one finding — is
    the precedent to follow, and it exists because raw KiCad output was unreadable.

*   **This depends on measurements the project often does not have.** `SPEC-326` supplies volumes
    and heights where models exist and placeholders where they do not, and the placeholder case is
    common. Advice built on a placeholder must be labelled as such.

## 4. Module Map & Reference Links

*   `apps/tauri-ui/specs/SPEC-325-kicad-project-integration.md` — parent; supplies the read.
*   `apps/tauri-ui/specs/SPEC-326-component-volume-placeholders.md` — courtyards, heights, and the
    placeholder volumes any clearance judgement rests on.
*   `services/python-daemon/agentflow/agents/board_advisor.prompt.md` — the existing board review,
    including the courtyard suggestion that is this spec's precedent.
*   `docs/site/src/content/docs/tutorials/blink-leds.md` — the third finding, explained.

## 5. User & Interaction

*   **Product Stage:** Board layout — after a `.kicad_pro` is open and `SPEC-325` has read the
    board, alongside the existing DRC results rather than in place of them.

*   **What the user is trying to accomplish:** Finding out what is wrong with a board they cannot
    yet evaluate themselves. Someone on their first PCB does not know that two parts 0.4mm apart
    are a soldering problem, or that one through-hole part on an otherwise SMD board adds a whole
    assembly step. They are not looking for rule violations; they are looking for the judgement
    they do not have yet.

*   **What the user sees and does:** On the PCB tab, a short list of plain-sentence findings, each
    naming the components involved and the number and source behind the threshold, visually
    distinct from KiCad's DRC output so the two are never mistaken for each other. Every finding
    that rests on data the app does not have says so in the finding itself — "these may collide; I
    have no 3D model for U1" — rather than being silently omitted. Nothing here is clickable in the
    sense of applying a change; the user reads, decides, and fixes it in KiCad.

---
id: SPEC-335
title: "New Project Wizard"
status: Draft
type: Feature
created: 2026-09-02
last_updated: 2026-09-02
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-335-new-project-wizard.md"
parent_spec: "SPEC-312-application-shell-project-portability-persistence.md"
child_specs: []
user_facing: true
---

# SPEC-335: New Project Wizard

## 1. Executive Summary & Goals

*   **High-Level Goal:** Replace the two-field sidebar form with a guided first run that ends with
    the user knowing what state their design is actually in.

*   **Business / Technical Value:** Creating a project today is a name and an optional
    "what are you building?" in a 192px sidebar column, with **no way to cancel**, after which the
    user lands on a tabbed view with nothing in it. The maintainer's account:

    > *"There is not a way to cancel creating a new project. And the 'what are you building' field
    > should be displayed in the main content prominantly and require the user to provide an
    > answer. We should make creating a project do everything in the main content area and not show
    > our tabbed view until the project is submitted."*

    The deeper problem is that **nothing in this app works without a linked KiCad project** — every
    surface now reads the `.kicad_pro` (SPEC-325) — and creation never mentions it. A user can
    finish creating a project and find every tab empty, with no indication why.

    Intent has the same shape: it is optional, so it is skipped, and then every agent answers
    generically. The Overview says so itself — *"Not stated yet — agents answer generically until
    you add one."*

*   **The steps, as specified by the maintainer:**

    1.  **Project name.**
    2.  **The linked KiCad project.** *"if none exists, we need to prompt them to create one as
        nothing else works without one."*
    3.  **A project chat to describe the goal.** The user describes it; the assistant summarises and
        asks for confirmation that it understood — intent by conversation, not by textarea.
    4.  **"We are reviewing the project."** Run the real checks and report: schematic/board parity,
        the board components table, missing footprints and 3D models, and the initial ERC/DRC runs.
        Beneath that, four buttons — one per tab — and choosing one dismisses the wizard and lands
        there.

*   **Non-Goals:**
    *   Creating the KiCad project itself. Step 2 prompts and points at KiCad; it does not author a
        `.kicad_pro`.
    *   Replacing the Overview tab. What belongs on a *returning* visit is a separate question (§3).

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **Whether every step is mandatory.** The maintainer wants intent required. A user who has no
    KiCad project yet cannot complete step 2 — decide whether that blocks creation, or creates a
    project parked at that step.
*   **Whether the wizard is resumable.** A project created without a link would need to re-enter it.
*   **What step 4 actually runs.** Every input already exists: `kicad.check_schematic_parity`,
    `kicad.component_envelopes`, `kicad.check_board`, `kicad.check_schematic`. Together they are
    several seconds and several LLM calls — decide what is run eagerly versus on first visit.
*   **Whether step 3's confirmation writes `intent` verbatim or the summary.** The summary is the
    agent's words; the intent is the user's. `project.set_intent` takes one string.
*   **How cancel behaves at each step.** Nothing is created until submit, per the maintainer, so
    cancel before step 4 should leave no project behind.

## 3. Known Constraints & Risks

*   **The Overview tab is now nearly empty**, and deliberately so: its four per-area status cards
    and project-level Run Review were removed on 2026-09-02 as *"a guess at what the future would
    need"*. Deciding what a returning user should see there is adjacent to this spec and explicitly
    unresolved — do not let the wizard quietly become the answer to it.
*   Step 4 is the first surface that runs several real checks together. `SPEC-319`'s review is one
    LLM call and already takes seconds; four checks plus explanation could be a long, silent wait.
    Progress has to be visible, and partial results usable.
*   A wizard that must be completed before anything is usable is a hard gate. If step 2 cannot be
    satisfied, the user must still be able to leave with something.

## 4. Module Map & Reference Links

*   `apps/tauri-ui/src/components/Rail.tsx` — today's inline create form, and the missing cancel.
*   `apps/tauri-ui/src/App.tsx` — `handleCreateProject`, and the view switch this must precede.
*   `apps/tauri-ui/src/components/Overview.tsx` — `IntentEditor`, the surface step 3 replaces.
*   `apps/tauri-ui/src/lib/kicadProject.ts` — `pickKicadProject`, `resolveKicadProject`.
*   `services/python-daemon/daemon.py` — the check routes step 4 composes.
*   `apps/tauri-ui/specs/SPEC-325` — why a linked `.kicad_pro` is a precondition, not a nicety.

## 5. User & Interaction

*   **Product Stage:** First run of a project — before any tab is meaningful.
*   **What the user is trying to accomplish:** Getting from "I have a KiCad project" to "I know what
    state it is in and where to start", without needing to know which tab does what.
*   **What the user sees and does:** The main content area, not the sidebar, walks them through
    naming the project, linking their `.kicad_pro`, describing what they are building in a short
    conversation, and finally reading a plain-language summary of their design's current state —
    then picks one of four buttons to land on the tab they want.

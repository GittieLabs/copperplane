---
id: SPEC-337
title: "Naming the Two Project Links"
status: Completed
type: Feature
created: 2026-09-03
last_updated: 2026-09-03
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-337-naming-the-two-project-links.md"
parent_spec: "SPEC-325-kicad-project-integration.md"
child_specs: []
user_facing: true
---

# SPEC-337: Naming the Two Project Links

## 1. Executive Summary & Goals

*   **High-Level Goal:** A project has two independent links to the filesystem. Give them two
    different names, everywhere they appear, so that being told one is "linked" can never be read
    as the other.

*   **Business / Technical Value:** Reported by the maintainer on 2026-09-03, from a real project,
    with three statements on screen at once:

    > a warning banner: *"No KiCad project linked, so board and schematic checks, the component
    > list and the enclosure cannot run."*
    > the header: *"Linked KiCad project: none yet"*
    > and directly beneath, in green: *"Linked to
    > /Users/keithelliott/repos/PCBs/Hello_World_Blinky/Hello_World_Blinky"*

    He linked the folder, was told it was linked, and reasonably concluded the project was linked.
    The record read `directory: /Users/.../Hello_World_Blinky`, `kicad_project_path: <none>`.

*   **The cost is not cosmetic.** With no `.kicad_pro` there is no board outline, so
    `freecad.generate_enclosure` runs in manual mode with `standoffs=[]` and produces an enclosure
    with **no mounting posts at all**. He was trying to see the standoff defect `SPEC-111`
    describes and hit this instead — and from the 3D view the two are indistinguishable. One
    confusing word cost a whole diagnostic session and produced a physically wrong artifact.

*   **Neither field is wrong, and neither is redundant.**
    *   `directory` (`SPEC-304` §2.1, built in `CTX-312.1`) — a folder on disk for artifacts and
        the portable manifest. A project legitimately has one before it has any KiCad files.
    *   `kicad_project_path` (`SPEC-325` §2.1) — the `.kicad_pro` every check, the component list
        and the enclosure are read from.

    The defect is that one word does both jobs in the same place, and the green success message is
    true about the less consequential one.

*   **Non-Goals:**
    *   **Merging the two fields.** They answer different questions and both are load-bearing.
    *   **Removing the folder link.** `SPEC-312`'s portability manifest depends on it.
    *   **Changing what either link does.** This spec is about what they are called and how their
        state is reported, not about their behaviour.

## 2. System Architecture & Design Choices

**Settled by the maintainer, 2026-09-03:**

*   **The names are "KiCad project" and "project folder".** The vocabulary already in the header
    and on the Schematic tab, kept — the change is that the folder action stops using the word
    *linked* at all. A KiCad project is *linked*; a project folder is *set*. Rejected: "design
    file" / "working folder", which separates the two words further at the cost of inventing a term
    KiCad does not use, in an app whose job is to explain KiCad's vocabulary rather than add to it.
*   **A folder holding exactly one `.kicad_pro` is offered, never assumed.** Setting the folder
    then says so and offers to link the `.kicad_pro` it found, in one click. Rejected: linking it
    automatically, which performs a second consequential write from a single choice.

*Open questions this spec must settle:*

*   ~~**What each is called.**~~ Settled above. "Linked" is currently used for both and must be used for neither
    without qualification. The candidates for `kicad_project_path` are the specific ones — *KiCad
    project*, *`.kicad_pro`* — and for `directory`, *project folder* or *working folder*. Settle
    one pair and apply it to every string in §4's list, including the success messages, which are
    where the confusion actually landed.
*   ~~**Whether choosing a folder should offer the `.kicad_pro` inside it.**~~ Settled above:
    offered, not assumed. **Still open:** what happens for zero and for several. Zero is a plain
    statement; several needs either a picker or silence, and a picker duplicates the existing
    **Link KiCad project…** file dialog.
*   ~~**Whether the banner should name which link is missing.**~~ **Settled and delivered:** it now
    reads *"No KiCad project (`.kicad_pro`) is linked ... A project folder is a different setting
    and does not replace this."*
*   ~~**What the wizard says.**~~ **Settled and delivered:** its bare *"Linked: <path>"* became
    *"KiCad project linked: <path>"*. The skip copy already named the KiCad project explicitly and
    needed no change.
*   ~~**Whether a success message should state the consequence.**~~ **Settled: the offer says it
    better than a sentence could.** Setting a folder now reports *"Project folder set to <path>"*
    and, when that folder holds a `.kicad_pro`, immediately offers to link it. A user who declines
    still has the banner, which now names which link is missing. Stating the consequence in the
    success message as well would be the third place saying it.

## 3. Known Constraints & Risks

*   **Renaming a concept is not a rename of one string.** `SPEC-337`'s whole subject is
    consistency, so a partial application is worse than none: a header saying "project folder"
    while a button still says "Link to folder…" reproduces the original defect in new words.
    §4 lists every occurrence found; the list must be re-derived at implementation time rather than
    trusted, because it was assembled by grep and a missed string is exactly the failure mode.
*   **Tests assert on this copy.** `App.test.tsx`, `NewProjectWizard.test.tsx` and
    `SchematicComponents.test.tsx` all query by these strings. They will need updating, and each
    change should be checked for whether it is still asserting the behaviour it meant to.
*   **The word "link" is also correct English for both operations.** The fix is not to avoid the
    verb but to always attach the noun — what is being linked — which is the part currently
    missing.
*   **No test can catch this class of defect.** Every string involved renders correctly, every
    handler works, and the app behaves exactly as written. It took a person reading three true
    sentences and drawing the only reasonable conclusion.

## 4. Module Map & Reference Links

Every user-facing occurrence found on 2026-09-03, to be re-derived at implementation time:

*   `apps/tauri-ui/src/App.tsx` — the banner (*"No KiCad project linked, so…"* + **Link one**), the
    header (*"Linked KiCad project: …"* + **Link**), **Choose project folder…**, **Copy project
    path**, and the green *"Linked to <path>"* from `handleLinkDirectory`.
*   `apps/tauri-ui/src/components/SchematicComponents.tsx` — **Link KiCad project…** and *"Pick
    your `.kicad_pro` …"*.
*   `apps/tauri-ui/src/components/SchematicAdvisor.tsx` — *"Link your KiCad project on the
    Schematic components panel above…"*.
*   `apps/tauri-ui/src/components/NewProjectWizard.tsx` — *"No KiCad project linked yet. You can
    link one later…"*.
*   `apps/tauri-ui/src/lib/projects.ts` — `directory` and `kicad_project_path`, and the
    `project.open_from_directory` route.
*   `apps/tauri-ui/specs/SPEC-325-kicad-project-integration.md` — parent; owns
    `kicad_project_path`.
*   `apps/tauri-ui/specs/SPEC-312-application-shell-project-portability-persistence.md` — owns the
    folder link and the manifest that needs it.

## 5. User & Interaction

*   **Product Stage:** Project setup — after a project exists, before anything can be checked.
*   **What the user is trying to accomplish:** Connecting their existing KiCad work to a
    Copperplane project, once, and knowing afterwards whether it worked.
*   **What the user sees and does:** Two clearly different actions with two clearly different
    names, each reporting a result that names what was linked. A user who has set only the folder
    is told that checks still need a KiCad project — in the message that confirms the folder, not
    only in a banner elsewhere on the page. A user who has set both sees both, and can tell at a
    glance which is which.

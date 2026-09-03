---
id: SPEC-331
title: "Enclosure Fit Review"
status: Completed
type: Feature
created: 2026-09-03
last_updated: 2026-09-03
target_version: v0.4.0
location: "apps/tauri-ui/specs/SPEC-331-enclosure-fit-review.md"
parent_spec: "SPEC-326-component-volume-placeholders.md"
child_specs: []
user_facing: true
---

# SPEC-331: Enclosure Fit Review

## 1. Executive Summary & Goals

*   **High-Level Goal:** Turn the switched-off Enclosure review back on, answering one question the
    user cannot answer alone: **will the parts on my board actually fit in the box I generated?**

*   **Business / Technical Value:** `SPEC-319` mounted a Run Review panel on the Enclosure tab. It
    was switched off on 2026-09-02, showing a `NotBuiltPlaceholder` instead, at the maintainer's
    call: *"I don't even know what the run review check is supposed to show for the enclosure."*

    It is a real feature, not a stub — `chat_enclosure.prompt.md` defines it as physical fit. Two
    things were wrong with it, and only one has since been fixed:

    **Its data tool needed KiCad running.** `kicad.get_component_heights` goes through `kicad_bridge`
    → `kipy`, so with KiCad closed it raised `KiCadUnavailableError` on every call. That tool was
    removed from the agent entirely on 2026-09-02, because a permanently-failing tool was starving
    the review of its `max_tool_rounds` and turning a review into unreadable output. **The agent now
    has no physical board data at all** — `context.search` and nothing else.

    **Its enclosure parameters are stale by construction.** `_assemble_context` hands the agent
    `last_results.enclosure`, which `EnclosurePanel` writes when an enclosure is *generated*. A user
    who changes the height and re-runs the review gets an assessment of the previous box. This is
    the same defect the ERC/DRC path had, fixed there on 2026-09-02 by running the check live
    instead of reading a cache — *"Re-running or clicking review would still just show cached and
    potentially stale results."*

    `SPEC-326` since built the replacement: `kicad.component_envelopes` reads **closed** files, and
    returns a per-part envelope with an honest `measured` / `stated` / `unknown` split plus the
    interior height the parts imply. It is already what drives the height recommendation the user
    sees on the panel. Pointing the review at it makes the feature work with KiCad closed *and*
    gives it better data than it ever had.

*   **What a fit review should say.** The roadmap entry names this as the thing to settle, and it is
    the whole design: **"your box is 16mm inside and BT1 needs 20mm" is useful; restating the
    parameters the user just typed is not.** A review that reads the user's own inputs back to them
    is noise, and worse than silence because it looks like analysis.

*   **Non-Goals:**
    *   Changing the enclosure. The review explains; the user edits the parameters.
    *   Geometry beyond height and plan area. Overhangs, connector cut-outs and lid clearance are
        real fit questions this deliberately does not attempt (see §3).
    *   Standoff geometry — `SPEC-330` owns that.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **What the agent is given, and how fresh it is.** Proposed: `_assemble_context`'s enclosure
    branch runs `component_envelopes` live against the linked project's board, exactly as
    `_check_status_note` runs ERC/DRC — so the review can never assess a box the user has already
    changed. The generated parameters still come from `last_results.enclosure`, because they *are* a
    record of a real generate; the spec must say plainly that they can lag the form.
*   **Which fit questions are answerable, and which are refused.** Height is answerable:
    `min_interior_height_mm` versus the generated `height_mm`. Plan area is answerable from the
    board outline plus `clearance_mm`. Anything needing real 3D shape is not, and must be declined
    rather than guessed.
*   **How `unknown` heights are reported.** `SPEC-326` is explicit that a component with no known
    height is not counted, so the real minimum may be taller. A fit review that says "it fits"
    while some parts are unmeasured is making a claim it cannot support.
*   **Whether the panel is re-enabled by this spec or by its context.** The
    `NotBuiltPlaceholder` naming `SPEC-331` is live in the app today and must be removed in the same
    change that makes the review work.

## 3. Known Constraints & Risks

*   **Enclosure parameters only exist after a generate.** A user who opens the Enclosure tab and
    runs a review without generating has no `last_results.enclosure` at all. That is an ordinary
    state and must read as "nothing generated yet", never as a fit verdict.
*   **A courtyard is not the part.** `SPEC-326` §2.1 measured this: on 10 real footprints the
    courtyard was *smaller* than the physical body in 4 of them. Plan-area fit computed from
    courtyards is therefore optimistic, and saying so is part of the answer.
*   **`unknown` heights are common.** On the maintainer's own board, 5 of 14 components have no
    known height. A fit review is often working from partial data, and its confidence must track
    that rather than the tidiness of the numbers it does have.
*   **The agent has no tools that see the board.** After the 2026-09-02 removal it has only
    `context.search`. Everything physical must arrive in its context block, or a new closed-file
    tool must be added — a decision §2 has to make.

## 4. Module Map & Reference Links

*   `services/python-daemon/chat_agents.py` — `_assemble_context`'s enclosure branch, and
    `_check_status_note` as the live-check precedent to follow.
*   `services/python-daemon/agentflow/agents/chat_enclosure.prompt.md` — the agent's brief, which
    still describes data it no longer has.
*   `services/python-daemon/daemon.py` — `kicad.component_envelopes`.
*   `apps/tauri-ui/src/components/EnclosurePanel.tsx` — the `NotBuiltPlaceholder` to remove, and
    where the generated parameters are recorded.
*   `apps/tauri-ui/specs/SPEC-326-component-volume-placeholders.md` — the data source, and the
    measured/stated/unknown discipline this must inherit.
*   `apps/tauri-ui/specs/SPEC-330` — standoffs, deliberately out of scope here.

## 5. User & Interaction

*   **Product Stage:** Enclosure — after a box has been generated, before it is printed.
*   **What the user is trying to accomplish:** Finding out whether the enclosure they just made will
    actually hold their board and its parts, without knowing which measurements matter.
*   **What the user sees and does:** Presses **Run Review** on the Enclosure tab and gets findings
    about fit in their own terms — which part sets the minimum height, whether the generated box
    clears it, and how much of the answer rests on parts nobody has measured — instead of the
    "not built yet" placeholder standing there now.

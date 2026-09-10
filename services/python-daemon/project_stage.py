"""Where a project stands, computed from its record -- `SPEC-343` §2.4.

Nothing here is stored and nothing is declared by the user. That is the whole
design: a non-linear flow stays honest only if the app reads the state rather
than asking someone to keep it up to date, and `SPEC-300` calls the stage
machine *"a DAG, not a wizard"*.

`CTX-343.1` Phase 1 measured two things about this before it was built, and both
shaped what is here:

*   **The reading is the feature; the action is a convenience.** Four of six
    actions are "go to the tab this points at and press the button already on
    it". But *"your schematic changed after the PCB check"* is something **no tab
    can say**, because no tab knows about two stages at once.
*   **Ordering is a real decision.** A first version put staleness above
    everything, which reached 32 of 64 states and was wrong at least once: a
    project whose owner never said what they were building, and which also has a
    stale check, should be told the first.
"""

#: `SPEC-343` §2.4, in precedence order. The list IS the ranking, so changing
#: the answer means moving a line rather than editing a condition -- and the
#: order is reviewable as a list, which is the point.
#:
#: `SPEC-210` §2.6 and `SPEC-343` §2.6 both asked how to rank when several things
#: are true, and named *"would this have built silently wrong"* as probably the
#: right measure. This ranks by **what the app cannot work without**: with no
#: stated goal every downstream answer is generic, so that outranks a stale
#: check, which is merely out of date.
NO_GOAL = "no_goal"
NO_FILES = "no_files"
REGRESSED = "regressed"
NOTHING_CHECKED = "nothing_checked"
SCHEMATIC_ONLY = "schematic_only"
BOARD_ONLY = "board_only"
BOTH_CHECKED = "both_checked"
COMPLETE = "complete"


def read(project: dict, stale_areas: list = None) -> dict:
    """One reading, with the evidence that produced it.

    `stale_areas` is what `get_project_review_result` and
    `get_project_considerations` already compute; this function does no file I/O
    of its own so it stays testable without a filesystem.

    Every reading carries `evidence`, per `CTX-343.1` Phase 2: a wrong reading
    must be debuggable by the person looking at it, not only by whoever wrote
    the ranking.
    """
    stale_areas = list(stale_areas or [])
    results = project.get("last_results") or {}
    reviews = project.get("last_reviews") or {}
    checked = set(results) | set(reviews)

    schematic = "schematic" in checked
    board = "pcb" in checked
    enclosure = "enclosure" in checked

    def out(state, action, area, evidence):
        return {
            "state": state,
            "action": action,
            # Which tab the action lives on. `SPEC-300`'s AI boundary applies:
            # this NAMES a destination, it never navigates. The user clicks.
            "area": area,
            "evidence": evidence,
            "stale_areas": stale_areas,
        }

    if not project.get("intent"):
        return out(
            NO_GOAL,
            "Say what you're building",
            "overview",
            "no intent recorded on this project",
        )

    if not project.get("kicad_project_path"):
        return out(
            NO_FILES,
            "Link a KiCad project",
            "overview",
            "an intent is recorded and no KiCad project is linked",
        )

    if stale_areas:
        # The reading that earns this surface its place. No single tab knows
        # that one stage moved after another was checked.
        area = stale_areas[0]
        return out(
            REGRESSED,
            f"Re-check the {area}",
            area,
            f"{', '.join(stale_areas)} changed since it was last checked",
        )

    if not schematic and not board:
        # `CTX-343.1` Phase 1: the only ambiguous state in 64, and the tie-break
        # is upstream-first. A board derived from a schematic with problems
        # wastes the board check, so the schematic is the cheaper thing to be
        # wrong about first.
        return out(
            NOTHING_CHECKED,
            "Check the schematic",
            "schematic",
            "a linked project with nothing checked yet; schematic first because "
            "a board check inherits whatever the schematic got wrong",
        )

    if schematic and not board:
        return out(BOARD_ONLY, "Check the board", "pcb",
                   "the schematic has been checked and the board has not")

    if board and not schematic:
        return out(SCHEMATIC_ONLY, "Check the schematic", "schematic",
                   "the board has been checked and the schematic has not")

    if not enclosure:
        return out(BOTH_CHECKED, "Generate an enclosure", "enclosure",
                   "schematic and board are both checked, no enclosure yet")

    # `SPEC-343` §2.6 and §3: what this says when nothing is wrong is an open
    # question, and generic praise is worse than silence. So it says nothing and
    # names why, rather than inventing an encouragement.
    return out(COMPLETE, None, None,
               "schematic, board and enclosure have all been checked")

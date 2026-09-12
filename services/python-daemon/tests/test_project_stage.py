"""SPEC-343 §2.4 / CTX-343.1 Phase 2: where a project stands.

The reading is the feature. `CTX-343.1` Phase 1 measured that four of six next
actions are "press the button on the tab this points at" -- but *"your schematic
changed after the PCB check"* is something no tab can say, because no tab knows
about two stages at once. These tests are mostly about the reading being right,
and about it never being confidently right about the wrong thing.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import project_stage as ps


def _project(**over):
    base = {"name": "p", "intent": None, "kicad_project_path": None,
            "last_results": {}, "last_reviews": {}}
    base.update(over)
    return base


class TestStageReading(unittest.TestCase):
    # TEST-001
    def test_001_a_project_with_no_intent_reads_as_the_earliest_stage(self):
        """Not an error, not empty -- the earliest real state, with something to
        do about it. SPEC-343 §2.5.1: this is the callout."""
        out = ps.read(_project())

        self.assertEqual(out["state"], ps.NO_GOAL)
        self.assertEqual(out["action"], "Say what you're building")
        self.assertEqual(out["area"], "overview")

    # TEST-003
    def test_003_every_reading_names_the_evidence_it_came_from(self):
        """A wrong reading has to be debuggable by whoever is looking at it, not
        only by whoever wrote the ranking."""
        for project in [
            _project(),
            _project(intent="x"),
            _project(intent="x", kicad_project_path="/x"),
            _project(intent="x", kicad_project_path="/x", last_reviews={"schematic": {}}),
            _project(intent="x", kicad_project_path="/x",
                     last_reviews={"schematic": {}, "pcb": {}}),
            _project(intent="x", kicad_project_path="/x",
                     last_reviews={"schematic": {}, "pcb": {}}, last_results={"enclosure": {}}),
        ]:
            out = ps.read(project)
            self.assertTrue(out["evidence"], f"no evidence for {out['state']}")

    # TEST-002
    def test_002_a_stale_check_reports_a_regression(self):
        """The reading that earns this surface its place: no single tab knows
        that one stage moved after another was checked."""
        out = ps.read(
            _project(intent="x", kicad_project_path="/x",
                     last_reviews={"schematic": {}, "pcb": {}}),
            stale_areas=["pcb"],
        )

        self.assertEqual(out["state"], ps.REGRESSED)
        self.assertEqual(out["area"], "pcb")
        self.assertIn("pcb", out["evidence"])

    # TEST-004
    def test_004_a_missing_goal_outranks_a_stale_check(self):
        """CTX-343.1 Phase 1 found this wrong in a first version, where
        staleness outranked everything and reached 32 of 64 states. A project
        whose owner never said what they were building, and which also has a
        stale check, should be told the first: with no stated goal every
        downstream answer is generic, while a stale check is merely out of
        date."""
        out = ps.read(_project(last_reviews={"pcb": {}}), stale_areas=["pcb"])

        self.assertEqual(out["state"], ps.NO_GOAL)

    def test_the_only_ambiguous_state_breaks_upstream_first(self):
        """Phase 1 enumerated 64 combinations and found exactly one ambiguous
        state: nothing checked at all. The tie-break is the schematic, because a
        board check inherits whatever the schematic got wrong -- so being wrong
        about the schematic first is the cheaper mistake."""
        out = ps.read(_project(intent="x", kicad_project_path="/x"))

        self.assertEqual(out["state"], ps.NOTHING_CHECKED)
        self.assertEqual(out["area"], "schematic")
        self.assertIn("inherits", out["evidence"])

    def test_a_checked_schematic_points_at_the_board(self):
        out = ps.read(_project(intent="x", kicad_project_path="/x",
                               last_reviews={"schematic": {}}))
        self.assertEqual(out["state"], ps.BOARD_ONLY)
        self.assertEqual(out["area"], "pcb")

    def test_a_checked_board_with_no_schematic_check_points_back_upstream(self):
        """The DAG going backwards. Entering at the PCB stage is legal per
        SPEC-300, so this state is reachable and is not an error."""
        out = ps.read(_project(intent="x", kicad_project_path="/x",
                               last_reviews={"pcb": {}}))
        self.assertEqual(out["state"], ps.SCHEMATIC_ONLY)
        self.assertEqual(out["area"], "schematic")

    def test_nothing_to_say_says_nothing_rather_than_inventing_encouragement(self):
        """SPEC-343 §2.6 leaves open what this says when nothing is wrong, and
        §3 warns that generic praise is worse than silence. Until that is
        settled it offers no action and names why, rather than filling the space."""
        out = ps.read(_project(intent="x", kicad_project_path="/x",
                               last_reviews={"schematic": {}, "pcb": {}},
                               last_results={"enclosure": {}}))

        self.assertEqual(out["state"], ps.COMPLETE)
        self.assertIsNone(out["action"])
        self.assertIsNone(out["area"])
        self.assertTrue(out["evidence"])

    def test_a_result_counts_as_checked_as_well_as_a_review(self):
        """A user who ran the check but never asked for a review has still
        checked. Counting only reviews would send them to do something they
        already did, which is the fastest way to lose their trust in this
        surface."""
        out = ps.read(_project(intent="x", kicad_project_path="/x",
                               last_results={"schematic": {}}))
        self.assertEqual(out["state"], ps.BOARD_ONLY)

    def test_the_reading_does_no_file_io(self):
        """`read` takes staleness as an argument on purpose: it stays testable
        without a filesystem, and the one thing that needs the disk is gathered
        by the route instead."""
        out = ps.read(_project(intent="x", kicad_project_path="/nonexistent/path"))
        self.assertEqual(out["state"], ps.NOTHING_CHECKED)


if __name__ == "__main__":
    unittest.main()


class EvidenceSaysWhatTheRecordHeld(unittest.TestCase):
    """`SPEC-343` §2.4 -- evidence explains the input, never the conclusion.

    Reported from a screenshot on 2026-09-12: the `complete` card read

        Schematic, board and enclosure have all been checked.
        schematic, board and enclosure have all been checked

    -- the heading and the line under it, word for word. Four states restated
    their own conclusion that way.

    Nothing could have caught it. The heading is written by `sentenceFor` in
    `Overview.tsx` and the evidence by this module; they live in different
    languages, and neither suite can see the other. So this pins the half that
    is checkable: an evidence line has to name something the RECORD held, which
    a restatement of the conclusion never does.
    """

    #: The vocabulary of "what was on file", which is what evidence is for.
    _RECORD_WORDS = ("recorded", "on record", "linked", "changed")

    def _every_reading(self):
        base = {"intent": "a logger", "kicad_project_path": "/p/x.kicad_pro"}
        return [
            ps.read({}, []),
            ps.read({"intent": "a logger"}, []),
            ps.read(base, ["schematic"]),
            ps.read(base, []),
            ps.read({**base, "last_reviews": {"schematic": 1}}, []),
            ps.read({**base, "last_results": {"pcb": 1}}, []),
            ps.read(
                {**base, "last_reviews": {"schematic": 1}, "last_results": {"pcb": 1}}, []),
            ps.read(
                {**base, "last_reviews": {"schematic": 1, "enclosure": 1},
                 "last_results": {"pcb": 1}}, []),
        ]

    def test_020_every_evidence_line_names_something_the_record_held(self):
        for reading in self._every_reading():
            with self.subTest(reading["state"]):
                self.assertTrue(
                    any(w in reading["evidence"] for w in self._RECORD_WORDS),
                    f"{reading['state']}'s evidence states a conclusion rather than "
                    f"what was on file: {reading['evidence']!r}",
                )

    def test_021_the_check_would_notice(self):
        """A check that cannot fail is not evidence -- `CLAUDE.md`.

        The exact string this replaced, which passes every other assertion in
        this file and was wrong on screen."""
        restatement = "schematic, board and enclosure have all been checked"

        self.assertFalse(any(w in restatement for w in self._RECORD_WORDS))

    def test_022_the_finished_reading_says_why_it_is_not_a_stale_one(self):
        """`complete` outranks nothing, so the question a reader actually has
        there is why this is not `regressed`. The evidence answers it."""
        reading = self._every_reading()[-1]

        self.assertEqual(reading["state"], ps.COMPLETE)
        self.assertIn("out of date", reading["evidence"])

    def test_023_no_two_states_share_an_evidence_line(self):
        lines = [r["evidence"] for r in self._every_reading()]

        self.assertEqual(len(lines), len(set(lines)))

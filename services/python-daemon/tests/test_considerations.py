"""SPEC-210 / CTX-210.1 Phase 2-3: the consideration record and its discipline.

The rules under test are not conveniences. SPEC-210 §2.2's trigger requirement is
the property that stops this family becoming a generative best-practices essay,
and §1's initiative rule is the line between SPEC-113 correctly volunteering a
finding and the same surface volunteering an opinion.

Both are enforced at construction rather than described, because this repo has
twice paid for a rule that lived only in prose: SPEC-342 §2.6's read-only flag
that nothing ever set, and CTX-326.4's placeholder volumes drawn on the two parts
that did not need them.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import considerations as C


def _valid(**over):
    base = dict(
        id="led_without_series_resistor",
        domain="power",
        claim_class=C.COMPUTED,
        trigger={"kind": "net", "ref": "Net-(D1-A)"},
        explanation="D1's anode net reaches no resistor.",
    )
    base.update(over)
    return base


class TestTriggerDiscipline(unittest.TestCase):
    """SPEC-210 §2.2, the safety property everything else rests on."""

    # TEST-001
    def test_001_a_consideration_with_no_trigger_is_refused(self):
        with self.assertRaises(C.ConsiderationError) as ctx:
            C.make(**_valid(trigger={}))
        self.assertIn("naming something real", str(ctx.exception))

    def test_a_trigger_with_a_kind_but_no_ref_is_refused(self):
        """The subtler failure: a trigger shaped like a trigger that names
        nothing. "a net" is not a net."""
        with self.assertRaises(C.ConsiderationError):
            C.make(**_valid(trigger={"kind": "net"}))

    def test_a_trigger_with_a_ref_but_no_kind_is_refused(self):
        with self.assertRaises(C.ConsiderationError):
            C.make(**_valid(trigger={"ref": "Net-(D1-A)"}))

    def test_a_real_trigger_is_kept_verbatim(self):
        c = C.make(**_valid(trigger={"kind": "reference", "ref": "R1", "extra": "kept"}))
        self.assertEqual(c["trigger"], {"kind": "reference", "ref": "R1", "extra": "kept"})

    def test_the_trigger_is_copied_not_aliased(self):
        """A caller mutating the dict it passed in must not rewrite what the
        consideration says it was triggered by."""
        trigger = {"kind": "net", "ref": "GND"}
        c = C.make(**_valid(trigger=trigger))
        trigger["ref"] = "something else"
        self.assertEqual(c["trigger"]["ref"], "GND")


class TestSourceRules(unittest.TestCase):
    """SPEC-210 §2.1: "Empty is only legal for a computed claim." """

    # TEST-002
    def test_002_a_cited_claim_with_no_source_is_refused(self):
        with self.assertRaises(C.ConsiderationError) as ctx:
            C.make(**_valid(claim_class=C.CITED))
        self.assertIn("where the fact came from", str(ctx.exception))

    def test_a_cited_claim_with_a_sourceless_source_is_refused(self):
        with self.assertRaises(C.ConsiderationError):
            C.make(**_valid(claim_class=C.CITED, source={"note": "somewhere"}))

    # TEST-003
    def test_003_a_computed_claim_carrying_a_source_is_refused(self):
        """The other direction of the same rule, and the one an implementation
        forgets: a computed claim IS the source, and attaching one implies an
        authority the calculation neither has nor needs."""
        with self.assertRaises(C.ConsiderationError) as ctx:
            C.make(**_valid(source={"ref": "IPC-2221"}))
        self.assertIn("carries no source", str(ctx.exception))

    def test_a_cited_claim_with_a_real_source_is_built(self):
        c = C.make(**_valid(claim_class=C.CITED, source={"ref": "IPC-2221", "section": "6.2"}))
        self.assertEqual(c["source"]["ref"], "IPC-2221")

    def test_a_judgement_may_carry_a_source_or_not(self):
        """A judgement is an opinion; it is neither required to cite nor barred
        from it, and forcing either way would be inventing a rule §2.1 does not
        state."""
        self.assertIsNone(C.make(**_valid(claim_class=C.JUDGEMENT))["source"])
        self.assertEqual(
            C.make(**_valid(claim_class=C.JUDGEMENT, source={"ref": "a book"}))["source"]["ref"],
            "a book",
        )


class TestInitiativeRule(unittest.TestCase):
    """SPEC-210 §1: a computed or cited claim may be raised unprompted; a
    judgement waits to be asked."""

    # TEST-004
    def test_004_a_judgement_is_not_raised_unprompted(self):
        judgement = C.make(**_valid(claim_class=C.JUDGEMENT))
        computed = C.make(**_valid())
        cited = C.make(**_valid(claim_class=C.CITED, source={"ref": "IPC-2221"}))

        self.assertFalse(C.may_raise_unprompted(judgement))
        self.assertTrue(C.may_raise_unprompted(computed))
        self.assertTrue(C.may_raise_unprompted(cited))

        shown = C.raisable([computed, cited, judgement])
        self.assertEqual([c["claim_class"] for c in shown], [C.COMPUTED, C.CITED])

    # TEST-005
    def test_005_a_judgement_is_still_reachable_when_asked(self):
        """The rule is about initiative, not about hiding. A judgement the user
        asked for is exactly what a judgement is for."""
        judgement = C.make(**_valid(claim_class=C.JUDGEMENT))

        self.assertEqual(C.raisable([judgement], asked=True), [judgement])
        self.assertEqual(C.raisable([judgement]), [])


class TestRecordShape(unittest.TestCase):
    # TEST-007
    def test_007_a_consideration_carries_the_copperplane_prefix(self):
        """SPEC-113's convention, inherited: a type starting copperplane. is
        this app's own claim and never KiCad's. chat_agents already tells the
        model what the prefix means."""
        self.assertTrue(C.make(**_valid())["type"].startswith("copperplane."))

    def test_an_id_that_already_carries_the_prefix_is_not_doubled(self):
        c = C.make(**_valid(id="copperplane.already_prefixed"))
        self.assertEqual(c["type"], "copperplane.already_prefixed")

    def test_the_arithmetic_is_kept_because_it_is_what_makes_a_claim_checkable(self):
        """SPEC-210 §2.0.1: a pack is a trigger, a formula AND a shown
        calculation. The person being taught cannot check the teaching any
        other way."""
        c = C.make(**_valid(
            claim_class=C.CITED, source={"ref": "IPC-2221"},
            arithmetic={"formula": "width for 1A at 10C rise", "result_mm": 0.4},
        ))
        self.assertEqual(c["arithmetic"]["result_mm"], 0.4)

    def test_a_new_consideration_starts_raised(self):
        self.assertEqual(C.make(**_valid())["state"], C.RAISED)

    def test_an_unknown_claim_class_or_state_is_refused(self):
        with self.assertRaises(C.ConsiderationError):
            C.make(**_valid(claim_class="vibes"))
        with self.assertRaises(C.ConsiderationError):
            C.make(**_valid(state="maybe"))

    def test_the_fields_that_cannot_be_empty_are_refused_empty(self):
        for field in ("id", "domain", "explanation"):
            with self.assertRaises(C.ConsiderationError, msg=f"accepted empty {field}"):
                C.make(**_valid(**{field: ""}))


#: The maintainer's own board, as `kicad_cli.export_netlist` really returns it.
#: Copied from a real run rather than invented, because an invented fixture is
#: what let the naive rule below look correct -- see `test_008b`.
_REAL_BOARD_NETS = [
    {"name": "GND", "nodes": [
        {"reference": "A1", "pin": "7", "function": "GND_7", "type": "power_in"},
        {"reference": "D1", "pin": "1", "function": "K_1", "type": "passive"},
        {"reference": "SW1", "pin": "1", "function": "1_1", "type": "passive"}]},
    {"name": "Net-(D1-A)", "nodes": [
        {"reference": "D1", "pin": "2", "function": "A_2", "type": "passive"},
        {"reference": "R1", "pin": "1", "function": None, "type": "passive"}]},
]


def _led_pack(nets):
    """Does each LED anode net reach a resistor? Keyed on KiCad's own pin
    naming, not on "there is a D somewhere on this net"."""
    out = []
    for net in nets:
        if not any(n["reference"].startswith("D") and (n["function"] or "").startswith("A")
                   for n in net["nodes"]):
            continue
        if not any(n["reference"].startswith("R") for n in net["nodes"]):
            out.append(C.make(
                id="led_without_series_resistor", domain="power", claim_class=C.COMPUTED,
                trigger={"kind": "net", "ref": net["name"]},
                explanation=f"{net['name']} carries an LED anode and reaches no resistor."))
    return out


class TestPackQuietness(unittest.TestCase):
    # TEST-008
    def test_008_a_pack_raises_nothing_when_its_trigger_is_absent(self):
        """The row that matters most. Every other test checks the machinery
        works; this checks it stays quiet, which is the property SPEC-210 §3
        says the whole family is spent on the first time it gets wrong.

        Modelled as a pack function: given a project that does not contain what
        the pack looks for, it must produce nothing -- not a hedged finding, not
        a "could not determine" entry."""
        raised = _led_pack(_REAL_BOARD_NETS)
        self.assertEqual(raised, [], "a correct board must produce silence")

        broken = [{"name": "Net-(D9-A)", "nodes": [
            {"reference": "D9", "pin": "2", "function": "A_2", "type": "passive"},
            {"reference": "A1", "pin": "3", "function": None, "type": "bidirectional"}]}]
        out = _led_pack(broken)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["trigger"]["ref"], "Net-(D9-A)")

    def test_008b_a_trigger_can_name_something_real_and_still_be_wrong(self):
        """The finding that cost this phase its assumption.

        A first version of this pack asked "is there a D on this net and no R"
        and fired on GND, because the LED's CATHODE sits on ground and no
        resistor does. `GND` is real, so §2.2's trigger discipline passed it --
        the claim was still false, on a board that is correct.

        So the trigger rule is necessary and not sufficient. What fixes it is
        another file fact rather than a heuristic: KiCad names the pin `A_2` and
        `K_1`, so the pack asks about the ANODE's net. This is the shape §3
        means by "measurement against a real board with its false positives
        counted, not plausibility"."""
        naive = [net for net in _REAL_BOARD_NETS
                 if any(n["reference"].startswith("D") for n in net["nodes"])
                 and not any(n["reference"].startswith("R") for n in net["nodes"])]

        self.assertEqual([n["name"] for n in naive], ["GND"],
                         "the naive rule's false positive, kept as the regression it is")
        self.assertEqual(_led_pack(_REAL_BOARD_NETS), [],
                         "and the corrected rule is silent on the same board")


if __name__ == "__main__":
    unittest.main()


class TestRealPack(unittest.TestCase):
    """SPEC-210 §3's bar: measurement against a real board with its false
    positives counted, not plausibility.

    Both fixtures are real files run through the real kicad-cli. The broken one
    is committed on purpose, because §3 names that as a real work item: without
    it a pack can only be tested when a user happens to have the bug.
    """

    _BROKEN = os.path.join(os.path.dirname(__file__), "fixtures", "led_no_resistor.kicad_sch")

    def setUp(self):
        import kicad_cli
        if not kicad_cli.__dict__.get("find_kicad_cli"):
            self.skipTest("kicad_cli unavailable")
        try:
            kicad_cli.find_kicad_cli()
        except Exception:
            self.skipTest("kicad-cli not found on this machine.")

    def _nets(self, path):
        import kicad_cli
        return kicad_cli.export_netlist(path)["nets"]

    def test_the_pack_raises_on_a_board_broken_on_purpose(self):
        import consideration_packs as packs
        raised = packs.run(self._nets(self._BROKEN))

        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["id"], "led_without_series_resistor")
        self.assertEqual(raised[0]["trigger"]["ref"], "+5V", "the ANODE's net, not the cathode's")

    def test_the_cathode_net_stays_silent_on_the_same_broken_board(self):
        """The regression that matters. The first version of this rule fired on
        the ground net because an LED's cathode sits there -- a claim that was
        false about a board that was correct. It must stay false-free even on a
        board that IS broken."""
        import consideration_packs as packs
        raised = packs.run(self._nets(self._BROKEN))

        self.assertNotIn("GND", [c["trigger"]["ref"] for c in raised])

    def test_only_one_pack_is_registered_and_that_is_deliberate(self):
        """A second pack was written, run against a real board, and withdrawn
        the same hour -- it could not tell a supply rail from ground, because
        KiCad marks both `power_in`. The registry records the outcome; the
        module records why."""
        import consideration_packs as packs
        self.assertEqual(len(packs.PACKS["power"]), 1)

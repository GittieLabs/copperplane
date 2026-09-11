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

    def test_the_withdrawn_pack_stays_withdrawn(self):
        """`power_pin_without_decoupling` was written, run against a real board,
        and withdrawn the same hour -- it could not tell a supply rail from
        ground, because KiCad marks both `power_in`.

        This originally asserted the pack count was 1, which pinned the wrong
        thing: the decision was that THAT pack stays out, not that there is
        exactly one pack forever. `CTX-343.1` Phase 5 added a second, legitimate
        one and the count assertion failed for a reason that was not a
        regression."""
        import consideration_packs as packs
        registered = {p.__name__ for packs_list in packs.PACKS.values() for p in packs_list}

        self.assertNotIn("power_pin_without_decoupling", registered)
        self.assertIn("led_series_resistor", registered)


class TestAbsenceShapedTriggers(unittest.TestCase):
    """SPEC-343 §2.6 / CTX-343.1 Phase 5.

    What a novice is missing is usually a part, or a number, that is not there,
    so the trigger is an empty set. SPEC-210 §2.2 still applies unchanged: an
    absence must be an absence OF something, ON something the files name.
    """

    def _sym(self, reference="R1", lib_id="Device:R", value="R"):
        return {"reference": reference, "lib_id": lib_id, "value": value,
                "footprint": None, "pin_count": 2}

    def test_a_passive_with_kicads_placeholder_value_is_raised(self):
        import consideration_packs as packs
        out = packs.component_without_value([self._sym()])

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["trigger"]["ref"], "R1")
        self.assertEqual(out[0]["claim_class"], "computed")

    def test_a_passive_with_a_real_value_is_not(self):
        import consideration_packs as packs
        self.assertEqual(packs.component_without_value([self._sym(value="220")]), [])

    def test_the_eleven_false_positives_the_naive_rule_produced(self):
        """The measurement that narrowed this rule, kept as the regression it is.

        KiCad writes a symbol's own name into its value by default, so "value
        equals symbol name" looks like a perfect never-set detector. On the
        maintainer's correct board it matches ALL ELEVEN symbols -- power:GND
        whose value GND is right, four mounting holes with no value to set, and
        the Arduino whose value IS its part name.

        Every symbol below satisfies the naive rule. None may be raised."""
        import consideration_packs as packs
        correct_board = [
            self._sym("#PWR05", "power:GND", "GND"),
            self._sym("#PWR04", "power:+5V", "+5V"),
            self._sym("SW1", "Switch:SW_Push", "SW_Push"),
            self._sym("H1", "Mechanical:MountingHole", "MountingHole"),
            self._sym("H2", "Mechanical:MountingHole", "MountingHole"),
            self._sym("A1", "MCU_Module:Arduino_UNO_R3", "Arduino_UNO_R3"),
            self._sym("D1", "Device:LED", "LED"),
        ]
        for s in correct_board:
            self.assertEqual((s["value"] or ""), (s["lib_id"] or "").split(":")[-1],
                             f"{s['reference']} should satisfy the naive rule")

        self.assertEqual(packs.component_without_value(correct_board), [],
                         "none of these are missing a value that anything computes with")

    def test_a_symbol_with_no_reference_names_nothing_and_is_skipped(self):
        """SPEC-210 §2.2 holds for absences too: a claim anchored to nothing is
        indistinguishable from a claim invented."""
        import consideration_packs as packs
        self.assertEqual(packs.component_without_value([self._sym(reference=None)]), [])

    def test_an_empty_value_counts_as_missing(self):
        import consideration_packs as packs
        out = packs.component_without_value([self._sym(value="")])
        self.assertEqual(len(out), 1)

    def test_the_explanation_says_what_the_absence_blocks(self):
        """SPEC-343 §2.5.2: the point of this consideration is converting "we
        cannot help" into "set this and it becomes answerable". An absence that
        does not say what it costs is just a complaint."""
        import consideration_packs as packs
        out = packs.component_without_value([self._sym()])

        self.assertIn("draws", out[0]["explanation"])

    def test_the_registry_names_which_source_each_pack_reads(self):
        """Declared rather than inferred from a signature, so a caller knows
        what to gather before running. One pack needs the netlist, the other
        the schematic's symbols."""
        import consideration_packs as packs
        self.assertEqual(packs.PACK_INPUTS["led_series_resistor"], "nets")
        self.assertEqual(packs.PACK_INPUTS["component_without_value"], "symbols")

    def test_run_gives_each_pack_the_source_it_asked_for(self):
        import consideration_packs as packs
        out = packs.run([], symbols=[self._sym()])
        self.assertEqual([c["id"] for c in out], ["component_without_value"])


class TestClearedItems(unittest.TestCase):
    """SPEC-343 §2.7: a silent pack is the reinforcement.

    SPEC-210 §2.3 sets a bar generic praise cannot clear -- telling a user their
    design is good is worthless unless the app knows what the bad version would
    have been. It does know: that is exactly what a silent pack is.
    """

    def _net(self, name, nodes):
        return {"name": name, "nodes": nodes}

    def _node(self, ref, pin="1", function=None, type_="passive"):
        return {"reference": ref, "pin": pin, "function": function, "type": type_}

    def test_a_pack_reports_what_it_cleared_and_why(self):
        import consideration_packs as packs
        out = packs.led_series_resistor([
            self._net("Net-(D1-A)", [self._node("D1", "2", "A_2"), self._node("R1")]),
        ])

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["state"], C.SATISFIED)
        self.assertIn("D1", out[0]["explanation"])
        self.assertIn("R1", out[0]["explanation"])
        # It teaches rather than congratulating.
        self.assertIn("current", out[0]["explanation"])

    def test_a_pack_whose_trigger_is_absent_says_nothing(self):
        """SPEC-343 §2.7's second constraint. A board with no LEDs has learned
        nothing from "no LED is missing a resistor" -- true, useless, and
        faintly absurd."""
        import consideration_packs as packs
        out = packs.led_series_resistor([
            self._net("GND", [self._node("A1", "7", "GND_7", "power_in")]),
        ])

        self.assertEqual(out, [])

    def test_a_cleared_item_is_never_raised_as_needing_attention(self):
        c = C.cleared(id="x", domain="power", trigger={"kind": "net", "ref": "N"},
                      explanation="fine")
        self.assertEqual(C.raisable([c]), [])
        self.assertEqual(C.raisable([c], asked=True), [])

    def test_cleared_items_are_found_by_their_own_accessor(self):
        """Kept apart rather than filtered at each call site: the whole point is
        that these read differently, and a caller who has to remember to
        separate them will one day not."""
        needs = C.make(id="y", domain="power", claim_class=C.COMPUTED,
                       trigger={"kind": "net", "ref": "M"}, explanation="problem")
        fine = C.cleared(id="x", domain="power", trigger={"kind": "net", "ref": "N"},
                         explanation="fine")

        self.assertEqual([c["id"] for c in C.cleared_items([needs, fine])], ["x"])
        self.assertEqual([c["id"] for c in C.raisable([needs, fine])], ["y"])

    def test_a_cleared_item_with_nothing_to_name_is_refused(self):
        """SPEC-210 §2.2 holds for reinforcement too. Praise anchored to nothing
        is the generic praise §3 says is worse than silence."""
        with self.assertRaises(C.ConsiderationError):
            C.cleared(id="x", domain="power", trigger={}, explanation="looks good")

    def test_the_cathode_net_is_not_cleared_either(self):
        """The GND false positive's mirror image, and an easy one to ship: a net
        carrying only a cathode has no anode to have cleared, so praising it
        would be as wrong as flagging it was."""
        import consideration_packs as packs
        out = packs.led_series_resistor([
            self._net("GND", [self._node("D1", "1", "K_1"), self._node("A1", "7", None, "power_in")]),
        ])

        self.assertEqual(out, [])

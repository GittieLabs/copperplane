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


class TestModuleInputPack(unittest.TestCase):
    """`SPEC-211` §2.0 / `CTX-211.1` Phase 5 -- the pack that speaks about the
    boards this project actually has.

    None of the five carries a discrete linear regulator, so the regulator a
    maker really does have is the one inside the dev board. This pack reasons
    only from what the symbol declares, because the app does not hold the
    Arduino's datasheet and must not pretend otherwise.
    """

    def _node(self, ref, pin, function, type_):
        return {"reference": ref, "pin": pin, "function": function, "type": type_}

    def _module(self, rail, supply_pin="VIN_8", outputs=(("5", "+5V_5", None),)):
        nets = [
            {"name": rail, "nodes": [self._node("A1", "8", supply_pin, "power_in")]},
            {"name": "GND", "nodes": [self._node("A1", "7", "GND_7", "power_in")]},
        ]
        for pin, function, net in outputs:
            nets.append({
                "name": net or f"unconnected-(A1-{function}-Pad{pin})",
                "nodes": [self._node("A1", pin, function, "power_out+no_connect")],
            })
        return nets

    def test_a_rail_matching_the_module_s_own_output_is_raised(self):
        import consideration_packs as packs
        raised = packs.regulated_rail_into_module_input(self._module("+5V"))

        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["id"], "regulated_rail_into_module_input")
        self.assertEqual(raised[0]["trigger"]["ref"], "+5V")

    def test_a_rail_with_headroom_is_left_alone(self):
        import consideration_packs as packs
        # 9V into a module that makes 5V is the ordinary, correct arrangement.
        self.assertEqual(
            packs.regulated_rail_into_module_input(self._module("+9V")), []
        )

    def test_it_asks_rather_than_asserts(self):
        """`SPEC-211` §2.4's surviving shape, and §3's worst case avoided.

        The app cannot see inside the module. A buck-boost would accept 5V on
        VIN quite happily, so a flat "this is wrong" would be confidently wrong
        on a real design."""
        import consideration_packs as packs
        explanation = packs.regulated_rail_into_module_input(self._module("+5V"))[0]["explanation"]

        self.assertIn("?", explanation)

    def test_it_claims_no_number_it_cannot_source(self):
        """Every figure in the explanation must appear in the schematic.

        The Arduino's real VIN minimum is a datasheet fact this app does not
        hold, and `SPEC-211` §3 says an unknown produces silence, not a
        plausible number."""
        import re
        import consideration_packs as packs
        explanation = packs.regulated_rail_into_module_input(self._module("+5V"))[0]["explanation"]
        # Voltage-shaped figures only. A reference designator's digit is not a
        # claim about anything, and an earlier version of this test failed on
        # the `1` in `A1` -- which was the test being wrong, not the pack.
        volts = set(re.findall(r"(\d+(?:\.\d+)?)\s*V\b", explanation))

        # 5V is on the schematic twice over: the rail is labelled `+5V` and the
        # module declares a `+5V` output pin. Nothing else may be stated.
        self.assertEqual(volts, {"5"}, f"unsourced voltages: {volts - {'5'}}")
        self.assertNotIn("7V", explanation, "the Arduino's VIN minimum is not ours to state")

    def test_an_unconnected_output_pin_is_mentioned_and_a_connected_one_is_not(self):
        import consideration_packs as packs
        spare = packs.regulated_rail_into_module_input(self._module("+5V"))[0]
        self.assertIn("not connected", spare["explanation"])

        used = packs.regulated_rail_into_module_input(
            self._module("+5V", outputs=(("5", "+5V_5", "Net-(A1-+5V)"),))
        )[0]
        self.assertNotIn("not connected", used["explanation"])

    def test_an_unconnected_supply_pin_raises_nothing(self):
        import consideration_packs as packs
        # Real: the Feather's VBUS. An unconnected input is not being fed at all.
        self.assertEqual(packs.regulated_rail_into_module_input([
            {"name": "unconnected-(AF1-VBUS-Pad24)",
             "nodes": [self._node("AF1", "24", "VBUS_24", "power_in+no_connect")]},
            {"name": "Net-(N1-CS)",
             "nodes": [self._node("AF1", "2", "3.3V_2", "power_out")]},
        ]), [])


class TestModuleInputPackOnRealBoards(unittest.TestCase):
    """The regression that matters, per `SPEC-210` §3 and `CTX-211.1` Phase 1.

    The heuristic this pack replaced returned three parts across five boards and
    every one was a false positive. So what needs pinning is not that the pack
    fires -- it is that it stays quiet on every board we can actually check, and
    speaks on exactly the one that earns it.
    """

    _BOARDS = {
        "Blink_LEDs": "/Users/keithelliott/repos/PCBs/Copperplane_Tutorials/"
                      "Copperplane_Blink_LEDs/Copperplane_Blink_LEDs.kicad_sch",
        "NFC_ESP32": "/Users/keithelliott/repos/PCBs/NFC_Reader_ESP32/"
                     "NFC_Reader_ESP32.kicad_sch",
        "MacroPad": "/Users/keithelliott/repos/PCBs/MacroPad/MacroPad.kicad_sch",
        "Hello_Blinky": "/Users/keithelliott/repos/PCBs/Hello_World_Blinky/"
                        "Hello_World_Blinky/Hello_World_Blinky.kicad_sch",
        "BB8": "/Users/keithelliott/repos/PCBs/BB8-Breakout/bb8-breakout/"
               "bb8-breakout.kicad_sch",
    }

    def setUp(self):
        import kicad_cli
        try:
            kicad_cli.find_kicad_cli()
        except Exception:
            self.skipTest("kicad-cli not found on this machine.")
        missing = [n for n, p in self._BOARDS.items() if not os.path.exists(p)]
        if missing:
            self.skipTest(f"boards not on this machine: {', '.join(missing)}")

    def _raised(self, path):
        import kicad_cli
        import consideration_packs as packs
        return packs.regulated_rail_into_module_input(
            kicad_cli.export_netlist(path)["nets"]
        )

    def test_it_speaks_on_the_one_board_that_earns_it(self):
        raised = self._raised(self._BOARDS["Blink_LEDs"])

        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["trigger"]["ref"], "+5V")
        self.assertEqual(raised[0]["trigger"]["reference"], "A1")
        self.assertEqual(raised[0]["trigger"]["pin"], "8")

    def test_it_stays_silent_on_every_other_real_board(self):
        for name, path in self._BOARDS.items():
            if name == "Blink_LEDs":
                continue
            self.assertEqual(self._raised(path), [], f"false positive on {name}")


class TestRegulatorDissipation(unittest.TestCase):
    """`SPEC-211` §2.1 item 1 / `CTX-211.1` Phase 3 -- the lead case."""

    _FIXTURE = os.path.join(
        os.path.dirname(__file__), "fixtures", "regulator_from_12v.kicad_sch"
    )

    def setUp(self):
        import kicad_cli
        try:
            kicad_cli.find_kicad_cli()
        except Exception:
            self.skipTest("kicad-cli not found on this machine.")

    def _run(self, intent):
        import kicad_cli
        import structural_checks
        import consideration_packs as packs
        return packs.regulator_dissipation({
            "nets": kicad_cli.export_netlist(self._FIXTURE)["nets"],
            "symbols": structural_checks.read_schematic_symbols(self._FIXTURE),
            "intent_fields": intent,
        })

    def test_the_spec_s_own_worked_example_comes_out_of_the_real_pipeline(self):
        """`SPEC-211` §1: 12V to 3.3V at half an amp is 4.35W.

        Through real kicad-cli on a real .kicad_sch, not hand-built dicts --
        though the file is one authored for this test, because no board
        available to this project has a discrete regulator at all."""
        raised = self._run({"current_budget": {"milliamps": 500}})

        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["id"], "regulator_dissipation")
        self.assertEqual(raised[0]["arithmetic"]["result"], {"value": 4.35, "unit": "W"})

    def test_every_number_says_where_it_came_from(self):
        """`SPEC-211` §2.2. An unlabelled estimate is the confidently-wrong
        output that spends this family's credibility."""
        inputs = self._run({"current_budget": {"milliamps": 500}})[0]["arithmetic"]["inputs"]

        self.assertEqual(inputs["Vin"]["from"], "rail")
        self.assertEqual(inputs["Vin"]["ref"], "+12V")
        self.assertEqual(inputs["Vout"]["from"], "symbol")
        self.assertEqual(inputs["Iout"]["from"], "intent")

    def test_it_states_watts_and_refuses_to_state_a_temperature(self):
        """The spec corrected rather than implemented.

        `SPEC-211` §1 wants the ceiling -- "your 1A regulator is a 130mA
        regulator on this supply" -- which needs a thermal resistance. This app
        holds no thermal data for any part and no numeric datasheet field of any
        kind, so §2.6's "never an assumed value" decides it."""
        explanation = self._run({"current_budget": {"milliamps": 500}})[0]["explanation"]

        self.assertIn("4.35W", explanation)
        for invented in ("degC", "°C", "88", "125", "150"):
            self.assertNotIn(invented, explanation)

    def test_a_missing_current_names_that_one_thing_and_not_a_list(self):
        raised = self._run({})

        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["id"], "regulator_dissipation_unanswerable")
        self.assertIn("how much current", raised[0]["explanation"])

    def test_an_explicit_unknown_is_treated_as_no_answer(self):
        raised = self._run({"current_budget": "unknown"})

        self.assertEqual(raised[0]["id"], "regulator_dissipation_unanswerable")

    def test_a_board_with_no_regulator_raises_nothing(self):
        import consideration_packs as packs
        self.assertEqual(packs.regulator_dissipation({
            "nets": [], "symbols": [{"reference": "R1", "lib_id": "Device:R"}],
            "intent_fields": {"current_budget": {"milliamps": 500}},
        }), [])

    def test_an_adjustable_regulator_says_so_rather_than_guessing_its_output(self):
        import consideration_packs as packs
        raised = packs.regulator_dissipation({
            "nets": [{"name": "+12V", "nodes": [{"reference": "U1", "pin": "3",
                                                 "function": "VI_3", "type": "power_in"}]}],
            "symbols": [{"reference": "U1", "lib_id": "Regulator_Linear:AMS1117"}],
            "intent_fields": {"current_budget": {"milliamps": 500}},
        })

        self.assertEqual(raised[0]["id"], "regulator_dissipation_unanswerable")
        self.assertIn("adjustable", raised[0]["explanation"])

    def test_a_switching_regulator_is_never_given_this_arithmetic(self):
        """It is the FIX this pack recommends, not the problem."""
        import consideration_packs as packs
        self.assertEqual(packs.regulator_dissipation({
            "nets": [{"name": "+12V", "nodes": [{"reference": "U1", "pin": "3",
                                                 "function": "VI_3", "type": "power_in"}]}],
            "symbols": [{"reference": "U1", "lib_id": "Regulator_Switching:LM2596-3.3"}],
            "intent_fields": {"current_budget": {"milliamps": 500}},
        }), [])


class TestTraceWidthAndReversePolarity(unittest.TestCase):
    """`SPEC-211` §2.1 items 4 and 5 / `CTX-211.1` Phase 6."""

    def _tracks(self, width, net="+9V", layer="F.Cu"):
        return [{"net": net, "width_mm": width, "layer": layer}]

    def _bb8_nets(self):
        return [
            {"name": "Net-(J4-Pin_1)", "nodes": [
                {"reference": "J4", "pin": "1", "function": None, "type": "passive"},
                {"reference": "X1", "pin": "5V", "function": None, "type": "power_in"}]},
            {"name": "GND", "nodes": [
                {"reference": "J4", "pin": "2", "function": None, "type": "passive"}]},
        ]

    def test_a_supply_trace_too_narrow_for_the_stated_current_is_raised(self):
        import consideration_packs as packs
        raised = packs.trace_too_narrow_for_current({
            "tracks": self._tracks(0.2),
            "intent_fields": {"current_budget": {"milliamps": 2000}},
        })

        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["trigger"]["ref"], "+9V")
        self.assertEqual(raised[0]["arithmetic"]["result"]["unit"], "mA")

    def test_a_wide_enough_trace_is_left_alone(self):
        import consideration_packs as packs
        self.assertEqual(packs.trace_too_narrow_for_current({
            "tracks": self._tracks(0.2),
            "intent_fields": {"current_budget": {"milliamps": 50}},
        }), [])

    def test_it_is_cited_and_names_the_standard_it_used(self):
        """`SPEC-210` §2.1: a claim relaying someone else's fact says whose.
        The arithmetic is ours; the relationship is IPC's."""
        import consideration_packs as packs
        raised = packs.trace_too_narrow_for_current({
            "tracks": self._tracks(0.2),
            "intent_fields": {"current_budget": {"milliamps": 2000}},
        })[0]

        self.assertEqual(raised["claim_class"], "cited")
        self.assertEqual(raised["source"]["ref"], "IPC-2221")

    def test_it_says_a_newer_standard_supersedes_the_one_it_used(self):
        """`SPEC-211` §2.5, and not optional: presenting a superseded standard
        as current is the confidently-wrong output this family cannot afford."""
        import consideration_packs as packs
        raised = packs.trace_too_narrow_for_current({
            "tracks": self._tracks(0.2),
            "intent_fields": {"current_budget": {"milliamps": 2000}},
        })[0]

        self.assertIn("IPC-2152", raised["explanation"])
        self.assertIn("IPC-2152", raised["source"]["note"])

    def test_it_says_the_copper_weight_is_an_assumption(self):
        # No board measured states one, so this assumption is always in play.
        import consideration_packs as packs
        raised = packs.trace_too_narrow_for_current({
            "tracks": self._tracks(0.2),
            "intent_fields": {"current_budget": {"milliamps": 2000}},
        })[0]

        self.assertIn("1oz copper", raised["explanation"])
        self.assertEqual(raised["arithmetic"]["inputs"]["copper"]["from"], "assumed")

    def test_a_signal_net_is_never_checked_against_the_board_s_total(self):
        """Only a supply rail can be said to carry the whole budget. What a
        signal trace draws is something nothing here knows."""
        import consideration_packs as packs
        self.assertEqual(packs.trace_too_narrow_for_current({
            "tracks": self._tracks(0.2, net="Net-(U2-THRES)"),
            "intent_fields": {"current_budget": {"milliamps": 2000}},
        }), [])

    def test_an_unrouted_board_raises_nothing(self):
        # Ordinary, not exceptional: two of five real boards have no segments.
        import consideration_packs as packs
        self.assertEqual(packs.trace_too_narrow_for_current({
            "tracks": [], "intent_fields": {"current_budget": {"milliamps": 2000}},
        }), [])

    def test_without_a_current_budget_it_stays_quiet_rather_than_asking_again(self):
        import consideration_packs as packs
        self.assertEqual(packs.trace_too_narrow_for_current({
            "tracks": self._tracks(0.2), "intent_fields": {},
        }), [])

    def test_a_bare_two_pin_power_input_is_raised(self):
        import consideration_packs as packs
        raised = packs.reversible_power_input({
            "nets": self._bb8_nets(),
            "footprints": [{"reference": "J4", "footprint":
                            "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"}],
        })

        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["trigger"]["ref"], "J4")
        self.assertIn("X1 pin 5V", raised[0]["explanation"])

    def test_a_keyed_power_input_is_left_alone(self):
        import consideration_packs as packs
        self.assertEqual(packs.reversible_power_input({
            "nets": self._bb8_nets(),
            "footprints": [{"reference": "J4", "footprint":
                            "Connector_BarrelJack:BarrelJack_Horizontal"}],
        }), [])

    def test_with_no_board_yet_it_raises_nothing(self):
        import consideration_packs as packs
        self.assertEqual(packs.reversible_power_input({
            "nets": self._bb8_nets(), "footprints": [],
        }), [])


class TestCurrentBudgetAgainstSource(unittest.TestCase):
    """`SPEC-211` §2.1 item 3 / `CTX-211.2` -- twelve LEDs off a USB port."""

    def _intent(self, source, milliamps):
        fields = {"input_supply": {"source": source, "nominal_volts": 5}}
        if milliamps is not None:
            fields["current_budget"] = {"milliamps": milliamps}
        return {"intent_fields": fields}

    def _run(self, source, milliamps):
        import consideration_packs as packs
        return packs.current_budget_against_source(self._intent(source, milliamps))

    def test_a_usb_board_over_the_guarantee_is_raised_and_cites_the_standard(self):
        raised = self._run("usb", 900)

        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["claim_class"], "cited")
        self.assertEqual(raised[0]["source"]["ref"], "USB 2.0 Specification")
        self.assertEqual(raised[0]["arithmetic"]["result"], {"value": 400, "unit": "mA"})

    def test_it_reports_a_guarantee_and_does_not_predict_a_failure(self):
        """The failure mode this pack actually has.

        Exceeding 500mA does not mean the board fails -- the charger on the
        user's desk probably delivers two amps. A confident "this will not work"
        about a board that works fine is `SPEC-211` §3's worst case, and it is
        the easy thing to write here."""
        explanation = self._run("usb", 900)[0]["explanation"]

        self.assertIn("does not mean it will not run", explanation)
        self.assertIn("some ports and not others", explanation)

    def test_a_source_with_no_capability_this_app_holds_stays_silent(self):
        # An adapter's capability is printed on the adapter, a battery's depends
        # on the cell, and a host board's is a datasheet figure this app does not
        # have. Inventing one is the assumed value §2.6 rules out.
        for source in ("adapter", "battery", "host_board"):
            self.assertEqual(self._run(source, 900), [], source)

    def test_a_budget_inside_the_guarantee_is_reinforced_not_merely_ignored(self):
        """`SPEC-343` §2.7: the reinforcement is the finding that was not raised."""
        import considerations
        raised = self._run("usb", 300)

        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["state"], considerations.SATISFIED)
        self.assertEqual(raised[0]["claim_class"], "cited")

    def test_the_good_news_is_sourced_as_rigorously_as_the_bad(self):
        """`considerations.cleared` builds a COMPUTED claim, and this figure is
        USB's however it is being used -- so the satisfied case goes through
        `make` directly with its source attached."""
        self.assertEqual(
            self._run("usb", 300)[0]["source"]["ref"], "USB 2.0 Specification"
        )

    def test_exactly_at_the_guarantee_fits(self):
        import considerations
        self.assertEqual(self._run("usb", 500)[0]["state"], considerations.SATISFIED)

    def test_without_a_current_budget_it_asks_nothing(self):
        # `regulator_dissipation` already asks for this number. Asking twice in
        # one review is nagging.
        self.assertEqual(self._run("usb", None), [])

    def test_an_unknown_supply_raises_nothing(self):
        import consideration_packs as packs
        self.assertEqual(packs.current_budget_against_source({
            "intent_fields": {"input_supply": "unknown",
                              "current_budget": {"milliamps": 900}},
        }), [])

    def test_a_project_with_no_intent_at_all_raises_nothing(self):
        import consideration_packs as packs
        self.assertEqual(packs.current_budget_against_source({"intent_fields": {}}), [])


class TestSupplyExceedsAbsoluteMaximum(unittest.TestCase):
    """`SPEC-211` §2.1 item 2 / `CTX-211.3` -- the literal fry case."""

    _FRY = os.path.join(os.path.dirname(__file__), "fixtures", "attiny_on_12v.kicad_sch")
    _ATTINY = [{"quote": "Voltage on RESET with respect to Ground......-0.5V to +13.0V", "page": 161},
               {"quote": "Maximum Operating Voltage............................................6.0V", "page": 161}]

    def setUp(self):
        import kicad_cli
        try:
            kicad_cli.find_kicad_cli()
        except Exception:
            self.skipTest("kicad-cli not found on this machine.")

    def _run(self, parts, path=None):
        import kicad_cli
        import structural_checks
        import consideration_packs as packs
        path = path or self._FRY
        return packs.supply_exceeds_absolute_maximum({
            "nets": kicad_cli.export_netlist(path)["nets"],
            "symbols": structural_checks.read_schematic_symbols(path),
            "parts": parts,
        })

    def test_a_twelve_volt_rail_on_a_six_volt_part_is_raised(self):
        """`SPEC-211` §1's own example, through the real pipeline."""
        raised = self._run([{"part_id": "ATTINY85-20PU",
                             "absolute_maximum_ratings": self._ATTINY}])

        self.assertEqual(len(raised), 1)
        self.assertEqual(raised[0]["claim_class"], "cited")
        self.assertEqual(raised[0]["arithmetic"]["result"], {"value": 6.0, "unit": "V"})

    def test_the_datasheet_row_is_shown_not_summarised_away(self):
        """The only thing making this extraction defensible is that the user can
        see the row the number came from and judge it."""
        raised = self._run([{"part_id": "ATTINY85-20PU",
                             "absolute_maximum_ratings": self._ATTINY}])[0]

        self.assertIn("Maximum Operating Voltage", raised["explanation"])
        self.assertIn("page 161", raised["explanation"])
        self.assertIn("if it is the wrong row, this finding is wrong with it",
                      raised["explanation"])

    def test_a_rail_within_the_rating_raises_nothing(self):
        raised = self._run([{"part_id": "ATTINY85-20PU", "absolute_maximum_ratings": [
            {"quote": "Maximum Operating Voltage......20.0V", "page": 161}]}])

        self.assertEqual(raised, [])

    def test_a_part_with_no_absolute_maximum_quotes_raises_nothing(self):
        self.assertEqual(
            self._run([{"part_id": "ATTINY85-20PU", "absolute_maximum_ratings": []}]), []
        )

    def test_a_part_not_on_this_board_raises_nothing(self):
        self.assertEqual(self._run([{"part_id": "NE555", "absolute_maximum_ratings": [
            {"quote": "V Supply voltage(2) 3 V", "page": 4}]}]), [])

    def test_a_project_linking_no_parts_raises_nothing(self):
        self.assertEqual(self._run([]), [])

    def test_it_never_reassures_only_ever_warns(self):
        """The asymmetry that makes the extraction safe.

        A parse reading too LOW is a visible false positive beside the quote
        that contradicts it. A parse reading too HIGH is silence -- what this
        app did before the pack existed. There is no path to a false "you are
        fine", which is the failure `SPEC-211` §3 actually forbids."""
        import considerations
        raised = self._run([{"part_id": "ATTINY85-20PU",
                             "absolute_maximum_ratings": self._ATTINY}])

        self.assertTrue(all(c["state"] != considerations.SATISFIED for c in raised))
        self.assertEqual(self._run([{"part_id": "ATTINY85-20PU",
                                     "absolute_maximum_ratings": [
                                         {"quote": "Maximum Operating Voltage......20.0V",
                                          "page": 161}]}]), [],
                         "a rail inside the rating produces silence, not a reassurance")

"""`SPEC-211` / `CTX-211.1` Phase 2 -- identifying a linear regulator.

The tests that matter here are the negative ones. Phase 1 measured that the
obvious heuristic was 0% precise and that a naive name parse is wrong on about a
third of the library, so what needs pinning is mostly what this module must
*refuse* to answer.
"""

import os
import re
import unittest

import power_path as P

_KICAD_LINEAR_LIB = (
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/"
    "Regulator_Linear.kicad_sym"
)


class TestRegulatorIdentification(unittest.TestCase):
    """TEST-001: library membership classifies, and the split is preserved."""

    def test_a_linear_regulator_is_identified_by_its_library(self):
        self.assertEqual(
            P.regulator_kind("Regulator_Linear:AMS1117-3.3"), P.LINEAR
        )

    def test_a_switching_regulator_is_classified_but_is_not_linear(self):
        # Not merely "not a regulator" -- it IS one, and the distinction is the
        # whole reason the classifier exists. The dissipation arithmetic is
        # nonsense here, and a switcher is what this pack recommends as the fix.
        self.assertEqual(
            P.regulator_kind("Regulator_Switching:LM2596-3.3"), P.SWITCHING
        )

    def test_an_ordinary_part_is_not_a_regulator(self):
        self.assertIsNone(P.regulator_kind("Device:R"))

    def test_a_dev_board_module_is_not_a_regulator(self):
        # The heuristic Phase 1 rejected returned exactly these three across
        # five real boards, and every one of them is a module. They do contain
        # regulators, which is what made the false positive convincing.
        for lib_id in (
            "MCU_Module:Arduino_UNO_R3",
            "Adafruit:Adafruit-Feather-ESP32-S3",
            "MyComponentLibs:XIAO_ESP32-S3",
        ):
            self.assertIsNone(P.regulator_kind(lib_id), lib_id)

    def test_the_library_classifies_and_not_the_part_name(self):
        # A part CALLED AMS1117 that lives in Device: is not a regulator record.
        # `component_without_value` distrusts the value string for the same
        # reason: both are user-authored.
        self.assertIsNone(P.regulator_kind("Device:AMS1117-3.3"))


class TestOutputVoltageFromName(unittest.TestCase):
    """TEST-002: read the unambiguous form, stay silent on everything else."""

    def test_a_name_encoded_output_voltage_is_read(self):
        self.assertEqual(P.output_volts("Regulator_Linear:AMS1117-3.3"), 3.3)

    def test_an_adjustable_part_yields_nothing_rather_than_a_default(self):
        self.assertIsNone(P.output_volts("Regulator_Linear:AMS1117"))

    def test_a_package_code_is_not_read_as_a_voltage(self):
        # 223V, 220V, 89V. Absurd enough to spot, which makes these the SAFE
        # failures -- they are not the reason the rule is conservative.
        for lib_id, would_be in (
            ("Regulator_Linear:LM317_SOT-223", 223),
            ("Regulator_Linear:LM317_TO-220", 220),
            ("Regulator_Linear:LM317L_SOT-89", 89),
        ):
            self.assertIsNone(P.output_volts(lib_id), f"{lib_id} -> {would_be}V")

    def test_a_trailing_variant_code_is_not_read_as_a_voltage(self):
        # THE dangerous one, and 125 symbols wear this shape. The real output is
        # the `-12` in the middle (1.2V); a naive parse says 3V. Nothing about
        # "3V" reads as a bug, which is exactly why it would have shipped.
        self.assertIsNone(P.output_volts("Regulator_Linear:APE8865N-12-HF-3"))

    def test_the_decimal_elided_convention_is_refused_not_guessed(self):
        # `TC1262-33` really is 3.3V, and this module really should say nothing.
        # Telling it apart from a genuine 33V part needs a rule with evidence
        # behind it, and inventing one to cover a few symbols is how a wrong
        # number gets into an arithmetic claim about someone's board.
        self.assertIsNone(P.output_volts("Regulator_Linear:TC1262-33"))

    def test_a_non_regulator_is_never_parsed_for_a_voltage(self):
        self.assertIsNone(P.output_volts("Device:R-3.3"))


class TestPinRole(unittest.TestCase):
    """TEST-003: a compound pintype matches on its first field."""

    def test_a_compound_pintype_matches_on_its_role(self):
        self.assertEqual(P.pin_role("power_out+no_connect"), "power_out")

    def test_a_plain_pintype_is_unchanged(self):
        self.assertEqual(P.pin_role("power_in"), "power_in")

    def test_a_missing_pintype_is_empty_rather_than_an_error(self):
        # Real: `BB8-Breakout`'s X1 has nodes whose pintype is absent entirely.
        self.assertEqual(P.pin_role(None), "")


class TestRegulatorsOnASchematic(unittest.TestCase):

    def test_a_board_with_no_regulator_yields_nothing_and_does_not_raise(self):
        # The ordinary case, not an edge case: none of the five boards
        # available to this project carries a discrete linear regulator.
        self.assertEqual(P.regulators([
            {"reference": "A1", "lib_id": "MCU_Module:Arduino_UNO_R3"},
            {"reference": "D1", "lib_id": "Device:LED"},
            {"reference": "R1", "lib_id": "Device:R"},
        ]), [])

    def test_a_regulator_is_returned_with_what_is_known_about_it(self):
        self.assertEqual(P.regulators([
            {"reference": "U1", "lib_id": "Regulator_Linear:AMS1117-3.3"},
        ]), [{
            "reference": "U1",
            "lib_id": "Regulator_Linear:AMS1117-3.3",
            "output_volts": 3.3,
        }])

    def test_a_regulator_with_no_reference_names_nothing_so_is_skipped(self):
        self.assertEqual(
            P.regulators([{"lib_id": "Regulator_Linear:AMS1117-3.3"}]), []
        )

    def test_a_switching_regulator_is_not_in_the_pack_s_subject(self):
        self.assertEqual(
            P.regulators([
                {"reference": "U1", "lib_id": "Regulator_Switching:LM2596-3.3"},
            ]), []
        )


@unittest.skipUnless(
    os.path.exists(_KICAD_LINEAR_LIB),
    "KiCad's symbol libraries are not installed on this machine",
)
class TestAgainstKicadsRealLibrary(unittest.TestCase):
    """Verified against the real thing, per `CLAUDE.md`: 1,626 real symbols.

    Skips cleanly where KiCad is absent, which is CI on two of three platforms.
    """

    @classmethod
    def setUpClass(cls):
        text = open(_KICAD_LINEAR_LIB, encoding="utf-8").read()
        cls.names = [
            m.group(1) for m in re.finditer(r'^\t\(symbol "([^"]+)"', text, re.M)
        ]

    def test_the_library_is_the_size_this_module_was_measured_against(self):
        # If KiCad reshapes this library the measurements in `power_path`'s
        # comments stop describing reality, and this says so rather than
        # letting them quietly rot.
        self.assertGreater(len(self.names), 1000)

    def test_every_parsed_voltage_is_a_plausible_regulator_output(self):
        parsed = {
            n: P.output_volts("Regulator_Linear:" + n) for n in self.names
        }
        got = {n: v for n, v in parsed.items() if v is not None}
        self.assertTrue(got, "parsed nothing at all from a real library")
        for name, volts in got.items():
            self.assertGreaterEqual(volts, 0.8, name)
            self.assertLessEqual(volts, 24.0, name)

    def test_no_package_or_variant_suffix_is_read_as_a_voltage(self):
        traps = [
            n for n in self.names
            if re.search(r"(SOT|TO)-\d+$", n) or re.search(r"-HF-\d$", n)
        ]
        self.assertTrue(traps, "found no trap-shaped symbols to check")
        for name in traps:
            self.assertIsNone(
                P.output_volts("Regulator_Linear:" + name), name
            )

    def test_the_case_that_matters_still_parses(self):
        self.assertIn("AMS1117-3.3", self.names)
        self.assertEqual(P.output_volts("Regulator_Linear:AMS1117-3.3"), 3.3)


if __name__ == "__main__":
    unittest.main()


class TestPinNaming(unittest.TestCase):
    """Phase 5. What a power pin is called, across three symbol conventions."""

    def test_a_pin_function_is_read_with_kicad_s_number_suffix_stripped(self):
        self.assertEqual(P.pin_name({"function": "+5V_5", "pin": "5"}), "+5V")

    def test_a_pin_number_is_the_name_when_the_symbol_gives_no_function(self):
        # Real: every XIAO_ESP32-S3 pin. A rule keyed only on `pinfunction`
        # reads nothing from that board and looks like a board with no power.
        self.assertEqual(P.pin_name({"function": None, "pin": "3V3"}), "3V3")

    def test_a_role_named_pin_keeps_its_role(self):
        self.assertEqual(P.pin_name({"function": "VIN_8", "pin": "8"}), "VIN")


class TestGroundAndVoltageNames(unittest.TestCase):

    def test_ground_is_recognised_by_name_across_conventions(self):
        for name in ("GND", "gnd", "VSS", "AGND", "/GND"):
            self.assertTrue(P.is_ground(name), name)

    def test_a_supply_rail_is_not_ground(self):
        for name in ("+5V", "VIN", "3V3"):
            self.assertFalse(P.is_ground(name), name)

    def test_the_v_as_decimal_point_convention_is_read(self):
        self.assertEqual(P.nominal_volts("3V3"), 3.3)
        self.assertEqual(P.nominal_volts("+3V3"), 3.3)
        self.assertEqual(P.nominal_volts("1V8"), 1.8)

    def test_a_plain_voltage_is_read_with_or_without_a_sign_or_path(self):
        self.assertEqual(P.nominal_volts("+5V"), 5.0)
        self.assertEqual(P.nominal_volts("/5V"), 5.0)
        self.assertEqual(P.nominal_volts("3.3V"), 3.3)
        self.assertEqual(P.nominal_volts("+9V"), 9.0)

    def test_a_role_name_states_no_voltage_and_is_not_guessed(self):
        # VBUS is 5V by USB convention. Reciting a convention is not the same
        # kind of fact as reading a net the user labelled, and this module is
        # only allowed the second kind.
        for name in ("VIN", "VBUS", "VBAT", "VCC", "VDD"):
            self.assertIsNone(P.nominal_volts(name), name)

    def test_ground_states_no_voltage(self):
        self.assertIsNone(P.nominal_volts("GND"))


class TestModulePowerPins(unittest.TestCase):

    def _node(self, ref, pin, function, type_):
        return {"reference": ref, "pin": pin, "function": function, "type": type_}

    def _arduino_nets(self):
        # The real shape of Copperplane_Blink_LEDs, including the two details
        # that broke earlier attempts: GND typed `power_in`, and the module's
        # own +5V pin left unconnected.
        return [
            {"name": "+5V", "nodes": [self._node("A1", "8", "VIN_8", "power_in")]},
            {"name": "GND", "nodes": [self._node("A1", "7", "GND_7", "power_in")]},
            {"name": "unconnected-(A1-+5V-Pad5)",
             "nodes": [self._node("A1", "5", "+5V_5", "power_out+no_connect")]},
            {"name": "unconnected-(A1-3V3-Pad4)",
             "nodes": [self._node("A1", "4", "3V3_4", "power_out+no_connect")]},
        ]

    def test_ground_is_excluded_even_though_it_is_typed_power_in(self):
        pins = P.module_power_pins(self._arduino_nets())
        self.assertEqual([s["name"] for s in pins["A1"]["supplies"]], ["VIN"])

    def test_a_supply_pin_carries_the_rail_s_voltage_not_the_pin_s(self):
        # The bug this pack shipped with for one run. A supply pin is named for
        # its role and has no voltage of its own; all of it is in the net.
        supply = P.module_power_pins(self._arduino_nets())["A1"]["supplies"][0]
        self.assertIsNone(supply["volts"], "VIN states no voltage")
        self.assertEqual(supply["net_volts"], 5.0, "the +5V rail does")

    def test_an_output_pin_carries_the_voltage_its_own_name_states(self):
        outputs = P.module_power_pins(self._arduino_nets())["A1"]["outputs"]
        self.assertEqual(
            sorted(o["volts"] for o in outputs), [3.3, 5.0]
        )

    def test_a_part_with_only_supplies_is_not_a_module(self):
        # An NE555 takes power in and makes no rail. Nothing here applies to it.
        self.assertEqual(P.module_power_pins([
            {"name": "+9V", "nodes": [self._node("U2", "8", "VCC_8", "power_in")]},
            {"name": "GND", "nodes": [self._node("U2", "1", "GND_1", "power_in")]},
        ]), {})

    def test_ground_typed_power_out_is_still_excluded(self):
        # Real, and the reason type cannot identify ground: the XIAO declares
        # its ground pin `power_out` where the Arduino declares its `power_in`.
        pins = P.module_power_pins([
            {"name": "Net-(J4-Pin_1)",
             "nodes": [self._node("X1", "5V", None, "power_in")]},
            {"name": "GND", "nodes": [self._node("X1", "GND", None, "power_out")]},
            {"name": "unconnected-(X1-Pad3V3)",
             "nodes": [self._node("X1", "3V3", None, "power_out+no_connect")]},
        ])
        self.assertEqual([o["name"] for o in pins["X1"]["outputs"]], ["3V3"])


class TestSupplyResolution(unittest.TestCase):
    """Phase 4. Derive before asking, per `SPEC-343` §2.5.2."""

    def _nets(self, rail):
        return [
            {"name": rail, "nodes": [{"reference": "U1", "pin": "3",
                                      "function": "VI_3", "type": "power_in"}]},
            {"name": "GND", "nodes": [{"reference": "U1", "pin": "1",
                                       "function": "GND_1", "type": "power_in"}]},
        ]

    def test_the_rail_name_answers_it_without_asking_anyone(self):
        # Four of five real boards name their own rail. Asking a user to type a
        # number their schematic already states teaches them the app is not
        # paying attention.
        got = P.supply_volts("U1", self._nets("+12V"))
        self.assertEqual(got, {"volts": 12.0, "source": P.FROM_RAIL, "ref": "+12V"})

    def test_a_plain_regulator_resolves_even_with_no_output_pin_in_the_netlist(self):
        """The bug the real fixture caught.

        This was written on top of `module_power_pins`, which requires a part to
        have an output pin too. A three-pin regulator whose output is not routed
        yet has none in the netlist, so the one part the pack most needed an
        answer for resolved to `None`."""
        nets = self._nets("+12V")
        self.assertEqual(P.module_power_pins(nets), {}, "not a module, correctly")
        self.assertEqual(P.supply_volts("U1", nets)["volts"], 12.0)

    def test_intent_answers_when_the_schematic_does_not(self):
        got = P.supply_volts(
            "U1", self._nets("Net-(U1-VI)"),
            {"input_supply": {"source": "adapter", "nominal_volts": 12}},
        )
        self.assertEqual(got["source"], P.FROM_INTENT)
        self.assertEqual(got["volts"], 12.0)

    def test_the_schematic_wins_over_intent_when_both_exist(self):
        got = P.supply_volts(
            "U1", self._nets("+9V"),
            {"input_supply": {"source": "adapter", "nominal_volts": 12}},
        )
        self.assertEqual(got["source"], P.FROM_RAIL)
        self.assertEqual(got["volts"], 9.0)

    def test_unknown_is_not_an_answer_and_produces_no_number(self):
        got = P.supply_volts("U1", self._nets("Net-(U1-VI)"),
                             {"input_supply": "unknown"})
        self.assertIsNone(got["volts"])
        self.assertIsNone(got["source"])

    def test_usb_without_a_stated_voltage_yields_no_number(self):
        # `nominal_volts: None` is legal and meaningful -- the user knows it is
        # USB-powered without knowing or caring that USB is 5V. This module is
        # not allowed to fill that in.
        got = P.supply_volts("U1", self._nets("Net-(U1-VI)"),
                             {"input_supply": {"source": "usb", "nominal_volts": None}})
        self.assertIsNone(got["volts"])

    def test_a_current_budget_is_read_and_unknown_is_not(self):
        self.assertEqual(P.budget_milliamps({"current_budget": {"milliamps": 500}}), 500.0)
        self.assertIsNone(P.budget_milliamps({"current_budget": "unknown"}))
        self.assertIsNone(P.budget_milliamps({}))

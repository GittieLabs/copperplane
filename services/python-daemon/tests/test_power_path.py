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

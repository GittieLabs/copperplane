"""SPEC-113: what ERC and DRC cannot see.

Measured against the real example project rather than a fixture, because the
whole risk in this check is false positives on legitimate parts -- and a
fixture written by the same session that wrote the rule proves nothing about
that.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import structural_checks

EXAMPLE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "examples", "Copperplane_Blink_LEDs"
))
EXAMPLE_SCH = os.path.join(EXAMPLE, "Copperplane_Blink_LEDs.kicad_sch")


def _stock_libraries_installed():
    """Whether this machine can resolve the example project's footprints.

    CI cannot: no KiCad, so every footprint fails and the check correctly
    collapses to one finding about the machine. Every test that asserts
    something about the comparison itself has to stand down there, and two of
    them originally did not -- CI caught it on all three runners.
    """
    if not os.path.exists(EXAMPLE_SCH):
        return False
    try:
        import kicad_bridge  # noqa: F401
        findings = structural_checks.check_pin_counts(EXAMPLE_SCH)
    except Exception:  # noqa: BLE001
        return False
    return not any(f["type"] == structural_checks.FOOTPRINT_UNRESOLVED for f in findings)


@unittest.skipUnless(os.path.exists(EXAMPLE_SCH), "the example project is not present")
class ReadingASchematicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.symbols = structural_checks.read_schematic_symbols(EXAMPLE_SCH)
        cls.by_ref = {s["reference"]: s for s in cls.symbols}

    def test_001_pin_counts_come_from_the_schematics_own_lib_symbols(self):
        self.assertEqual(self.by_ref["D1"]["pin_count"], 2)
        self.assertEqual(self.by_ref["R1"]["pin_count"], 2)
        self.assertEqual(self.by_ref["SW1"]["pin_count"], 2)

    def test_002_pins_are_summed_across_a_symbols_units(self):
        """Pins live in unit sub-symbols, not on the definition. Counting only
        the definition returns 0 for every part in the file."""
        self.assertEqual(self.by_ref["A1"]["pin_count"], 32)

    def test_003_a_symbol_with_no_pins_reports_zero_not_none(self):
        self.assertEqual(self.by_ref["H1"]["pin_count"], 0)

    def test_004_parts_excluded_from_the_bom_are_still_seen(self):
        """`kicad-cli sch export bom` omits the mounting holes entirely. This
        check has to see them to conclude they are fine."""
        for reference in ("H1", "H2", "H3", "H4"):
            self.assertIn(reference, self.by_ref)

    def test_005_a_symbol_with_no_footprint_reports_none_not_empty_string(self):
        self.assertIsNone(self.by_ref["#PWR01"]["footprint"])

    def test_006_a_file_that_is_not_a_schematic_is_refused(self):
        with tempfile.NamedTemporaryFile("w", suffix=".kicad_sch", delete=False) as handle:
            handle.write("(kicad_pcb (version 20240108))")
            path = handle.name
        try:
            with self.assertRaises(structural_checks.SchematicReadError):
                structural_checks.read_schematic_symbols(path)
        finally:
            os.unlink(path)

    def test_007_a_missing_file_is_refused(self):
        with self.assertRaises(structural_checks.SchematicReadError):
            structural_checks.read_schematic_symbols("/no/such/file.kicad_sch")


class CountingPadsTests(unittest.TestCase):
    """The count is distinct, numbered and plated. Each word earns its place."""

    def _mod(self, body):
        handle = tempfile.NamedTemporaryFile("w", suffix=".kicad_mod", delete=False)
        handle.write(body)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_101_plain_numbered_pads_are_counted(self):
        path = self._mod('(footprint "x" (pad "1" thru_hole circle) (pad "2" thru_hole circle))')
        self.assertEqual(structural_checks.count_numbered_plated_pads(path), 2)

    def test_102_unplated_holes_are_not_pins(self):
        """A shield header's mounting holes are drilled, not plated. Counting
        them is what makes a correct 32-pin Arduino footprint look like 36."""
        path = self._mod(
            '(footprint "x" (pad "1" thru_hole circle) (pad "" np_thru_hole circle)'
            ' (pad "" np_thru_hole circle))'
        )
        self.assertEqual(structural_checks.count_numbered_plated_pads(path), 1)

    def test_103_a_repeated_pad_number_is_one_pin(self):
        """Two legs of the same electrical node share a number."""
        path = self._mod(
            '(footprint "x" (pad "1" thru_hole circle) (pad "1" thru_hole circle)'
            ' (pad "2" thru_hole circle) (pad "2" thru_hole circle))'
        )
        self.assertEqual(structural_checks.count_numbered_plated_pads(path), 2)

    def test_104_a_numbered_smd_pad_counts(self):
        path = self._mod('(footprint "x" (pad "1" smd rect) (pad "2" smd rect))')
        self.assertEqual(structural_checks.count_numbered_plated_pads(path), 2)

    @unittest.skipUnless(os.path.exists(EXAMPLE_SCH), "the example project is not present")
    def test_105_the_real_arduino_footprint_counts_32_not_36(self):
        """`footprint_detail._pads` reports 36 for this file. That is the
        function this one exists because it is not."""
        import kicad_bridge
        resolved = kicad_bridge.resolve_footprint_model("Module:Arduino_UNO_R3_WithMountingHoles")
        path = resolved.get("footprint_path")
        if not path or not os.path.exists(path):
            self.skipTest("KiCad's Module library is not installed")

        self.assertEqual(structural_checks.count_numbered_plated_pads(path), 32)


@unittest.skipUnless(os.path.exists(EXAMPLE_SCH), "the example project is not present")
class TheRealProjectTests(unittest.TestCase):
    """Two findings, both real, and silence for everything else.

    The rule that produced this replaced an obvious cheaper one -- flag pads
    with no net -- which additionally reported A1, whose shield header
    legitimately carries four unplated holes. `kicad_cli.check_schematic_parity`
    records the same trap being walked into once already: a hand-rolled diff,
    five findings, one real.
    """

    @classmethod
    def setUpClass(cls):
        if not _stock_libraries_installed():
            raise unittest.SkipTest("KiCad's stock footprint libraries are not installed")
        cls.findings = structural_checks.check_pin_counts(EXAMPLE_SCH)
        cls.refs = sorted(
            f["items"][0]["description"].split()[1] for f in cls.findings
        )

    def test_201_exactly_d1_and_sw1(self):
        self.assertEqual(self.refs, ["D1", "SW1"])

    def test_202_the_documented_case_names_both_counts(self):
        d1 = next(f for f in self.findings if f["items"][0]["description"].startswith("Symbol D1"))
        self.assertIn("has 2", d1["description"])
        self.assertIn("has 4 numbered pads", d1["description"])
        self.assertEqual(d1["type"], structural_checks.PIN_COUNT_MISMATCH)

    def test_203_mounting_holes_are_silent_with_no_rule_naming_them(self):
        """Zero pins against zero numbered plated pads. The spec expected to
        need an exclusion for these and does not."""
        self.assertNotIn("H1", self.refs)

    def test_204_power_symbols_are_skipped_for_having_no_footprint(self):
        self.assertFalse(any(r.startswith("#PWR") for r in self.refs))

    def test_205_a_correct_part_produces_nothing(self):
        for reference in ("A1", "R1"):
            self.assertNotIn(reference, self.refs)


class UnresolvableFootprintTests(unittest.TestCase):
    """Silence would read as a clean part. It has to say it could not compare."""

    @unittest.skipUnless(os.path.exists(EXAMPLE_SCH), "the example project is not present")
    def test_301_no_footprints_at_all_is_one_finding_about_the_machine(self):
        """CI caught this. With no KiCad installed every footprint fails to
        resolve, and one finding per part meant eight warnings about eight
        perfectly correct parts -- noise of exactly the kind that spends the
        credibility this check depends on."""
        findings = structural_checks.check_pin_counts(
            EXAMPLE_SCH, resolve_footprint=lambda _fp: {"footprint_path": None}
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["type"], structural_checks.FOOTPRINT_UNRESOLVED)
        self.assertIn("No footprint in this project could be found", findings[0]["description"])
        self.assertIn("NOT a clean result", findings[0]["description"])

    @unittest.skipUnless(_stock_libraries_installed(),
                         "KiCad's stock footprint libraries are not installed")
    def test_303_one_missing_footprint_among_working_ones_names_that_part(self):
        """A part that fails while its neighbours resolve really is about that
        part -- a custom library the user has not registered."""
        import kicad_bridge

        def resolve(footprint_id):
            if "LED" in footprint_id:
                return {"footprint_path": None}
            return kicad_bridge.resolve_footprint_model(footprint_id)

        findings = structural_checks.check_pin_counts(EXAMPLE_SCH, resolve_footprint=resolve)
        unresolved = [f for f in findings
                      if f["type"] == structural_checks.FOOTPRINT_UNRESOLVED]

        self.assertEqual(len(unresolved), 1)
        self.assertIn("D1's footprint", unresolved[0]["description"])

    @unittest.skipUnless(os.path.exists(EXAMPLE_SCH), "the example project is not present")
    def test_302_a_resolver_that_raises_does_not_take_the_check_down(self):
        def boom(_fp):
            raise RuntimeError("fp-lib-table is unreadable")

        findings = structural_checks.check_pin_counts(EXAMPLE_SCH, resolve_footprint=boom)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["type"], structural_checks.FOOTPRINT_UNRESOLVED)


if __name__ == "__main__":
    unittest.main()

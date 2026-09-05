import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import kicad_write as kw

_SOIC8_DIMS = {"length_mm": 4.9, "width_mm": 3.9, "height_mm": 1.75, "pitch_mm": 1.27}
_DIP8_DIMS = {"length_mm": 9.81, "width_mm": 6.35, "height_mm": 5.08, "pitch_mm": 2.54}
_0603_DIMS = {"length_mm": 1.6, "width_mm": 0.8, "height_mm": 0.45, "pitch_mm": 0}


class TestTwoPinLayout(unittest.TestCase):

    def test_001_two_pins_symmetric_about_center(self):
        """TEST-001: a 2-pad passive places pin 1 left of center, pin 2
        right of center, symmetric about the package origin."""
        pads = kw.generate_pad_layout("0603", ["1", "2"], _0603_DIMS)
        self.assertEqual(len(pads), 2)
        by_number = {p["number"]: p for p in pads}
        self.assertLess(by_number["1"]["x_mm"], 0)
        self.assertGreater(by_number["2"]["x_mm"], 0)
        self.assertAlmostEqual(by_number["1"]["x_mm"], -by_number["2"]["x_mm"])
        self.assertEqual(by_number["1"]["y_mm"], 0.0)
        self.assertEqual(by_number["1"]["pad_type"], "smd")
        self.assertIsNone(by_number["1"]["drill_mm"])

    def test_002_pad_length_stays_inside_the_package_body(self):
        """TEST-001: the generated pad footprint must not exceed the
        package's own real length -- a pad wider than the body it's on
        would be a physically nonsensical layout."""
        pads = kw.generate_pad_layout("0805", ["1", "2"], {"length_mm": 2.0, "width_mm": 1.25, "height_mm": 0.6, "pitch_mm": 0})
        span = max(p["x_mm"] for p in pads) - min(p["x_mm"] for p in pads)
        pad_length = pads[0]["width_mm"]
        self.assertLess(span + pad_length, 2.0 * 1.01)  # small float-safety margin


class TestDualRowLayout(unittest.TestCase):

    def test_001_soic8_pin_count_and_sides(self):
        """TEST-001: SOIC-8's 8 pins split 4-and-4 across two columns,
        pins 1-4 on the left (negative x), 5-8 on the right (positive x)."""
        pin_numbers = [str(i) for i in range(1, 9)]
        pads = kw.generate_pad_layout("SOIC-8", pin_numbers, _SOIC8_DIMS)
        self.assertEqual(len(pads), 8)
        by_number = {p["number"]: p for p in pads}
        for n in range(1, 5):
            self.assertLess(by_number[str(n)]["x_mm"], 0, f"pin {n} should be on the left")
        for n in range(5, 9):
            self.assertGreater(by_number[str(n)]["x_mm"], 0, f"pin {n} should be on the right")

    def test_002_soic8_pin1_and_last_pin_share_a_row(self):
        """TEST-001: standard IC numbering -- pin 1 (top-left) and the
        last pin (top-right) are on the same row, matching a real
        datasheet's pinout, not an arbitrary assignment."""
        pin_numbers = [str(i) for i in range(1, 9)]
        pads = kw.generate_pad_layout("SOIC-8", pin_numbers, _SOIC8_DIMS)
        by_number = {p["number"]: p for p in pads}
        self.assertAlmostEqual(by_number["1"]["y_mm"], by_number["8"]["y_mm"])
        # The middle two pins (4, 5) are on the opposite row from pin 1.
        self.assertAlmostEqual(by_number["4"]["y_mm"], by_number["5"]["y_mm"])
        self.assertNotAlmostEqual(by_number["1"]["y_mm"], by_number["4"]["y_mm"])

    def test_003_positions_are_symmetric_about_the_package_center(self):
        """TEST-001: real footprints are centered on the origin -- the
        sum of every pad's x and y position should be ~0."""
        pin_numbers = [str(i) for i in range(1, 9)]
        pads = kw.generate_pad_layout("SOIC-8", pin_numbers, _SOIC8_DIMS)
        self.assertAlmostEqual(sum(p["x_mm"] for p in pads), 0.0)
        self.assertAlmostEqual(sum(p["y_mm"] for p in pads), 0.0)

    def test_004_dip8_is_through_hole_with_a_drill(self):
        """TEST-001: DIP packages are through-hole -- every pad must
        carry a real drill diameter, unlike SOIC's surface-mount pads."""
        pin_numbers = [str(i) for i in range(1, 9)]
        pads = kw.generate_pad_layout("DIP-8", pin_numbers, _DIP8_DIMS)
        self.assertEqual(len(pads), 8)
        for pad in pads:
            self.assertEqual(pad["pad_type"], "pth")
            self.assertIsNotNone(pad["drill_mm"])
            self.assertGreater(pad["drill_mm"], 0)

    def test_004b_dip8_row_spacing_is_the_real_standardized_0_3in_lead_spacing(self):
        """A real bug found by live user testing: DIP row spacing was
        previously derived from `package_dimensions["width_mm"]` (the
        package BODY width, ~6.35mm for this fixture) instead of the
        real, standardized 0.3in/7.62mm lead-to-lead spacing every
        "wide" DIP-8/DIP-14 actually has (confirmed against the real
        ATtiny85 datasheet's own PDIP-8 mechanical drawing: "eA 0.300
        BSC"). A footprint generated with the wrong row spacing would
        not physically fit a real part's leads."""
        pin_numbers = [str(i) for i in range(1, 9)]
        pads = kw.generate_pad_layout("DIP-8", pin_numbers, _DIP8_DIMS)
        by_number = {p["number"]: p for p in pads}
        row_spacing = by_number["8"]["x_mm"] - by_number["1"]["x_mm"]
        self.assertAlmostEqual(row_spacing, 7.62)

    def test_005_adjacent_pads_never_touch(self):
        """TEST-001: pad size along the row axis must stay strictly
        under the pitch, or adjacent pads on the same side would
        physically overlap."""
        pin_numbers = [str(i) for i in range(1, 15)]
        dims = {"length_mm": 8.7, "width_mm": 3.9, "height_mm": 1.75, "pitch_mm": 1.27}
        pads = kw.generate_pad_layout("SOIC-14", pin_numbers, dims)
        for pad in pads:
            self.assertLess(pad["height_mm"], dims["pitch_mm"])


class TestUnsupportedPackages(unittest.TestCase):

    def test_001_perimeter_packages_fail_closed(self):
        """TEST-001: TQFP/QFN's four-side perimeter numbering is a
        genuinely different geometry this module deliberately doesn't
        cover -- must raise, never guess a layout."""
        with self.assertRaises(kw.UnsupportedPackageError):
            kw.generate_pad_layout("TQFP-32", [str(i) for i in range(1, 33)], {"length_mm": 7, "width_mm": 7, "height_mm": 1.4, "pitch_mm": 0.8})

    def test_002_sot23_fails_closed(self):
        """TEST-001: SOT-23's irregular 3-pin layout isn't a clean
        dual-row or 2-pin case -- must raise."""
        with self.assertRaises(kw.UnsupportedPackageError):
            kw.generate_pad_layout("SOT-23", ["1", "2", "3"], {"length_mm": 2.9, "width_mm": 1.3, "height_mm": 1.1, "pitch_mm": 0.95})

    def test_003_non_contiguous_pin_numbers_fail_closed(self):
        """TEST-001: a schema whose pin numbers skip or duplicate isn't
        a layout this module can place safely."""
        with self.assertRaises(kw.UnsupportedPackageError):
            kw.generate_pad_layout("0603", ["1", "3"], _0603_DIMS)


_SOIC8_SCHEMA = {
    "part_number": "ATTINY85",
    "package": "SOIC-8",
    "pins": [{"number": str(i), "name": f"P{i}", "electrical_type": "passive"} for i in range(1, 9)],
    "package_dimensions": _SOIC8_DIMS,
    "courtyard": {"length_mm": 5.2, "width_mm": 4.2},
}

_DIP8_SCHEMA = {
    "part_number": "TEST-DIP8",
    "package": "DIP-8",
    "pins": [{"number": str(i), "name": f"P{i}", "electrical_type": "passive"} for i in range(1, 9)],
    "package_dimensions": _DIP8_DIMS,
    "courtyard": {"length_mm": 10.2, "width_mm": 7.0},
}


class TestBuildFootprintInstance(unittest.TestCase):
    """Pure object construction -- no live KiCad connection needed;
    only board.create_items (kicad_bridge's job, not kicad_write's)
    actually talks to a running KiCad."""

    def test_001_pad_count_and_numbers_match_the_layout(self):
        pads = kw.generate_pad_layout("SOIC-8", [p["number"] for p in _SOIC8_SCHEMA["pins"]], _SOIC8_DIMS)
        fi = kw.build_footprint_instance(_SOIC8_SCHEMA, pads, _SOIC8_SCHEMA["courtyard"])
        pad_items = [p for p in fi.definition.pads]
        self.assertEqual(len(pad_items), 8)
        self.assertEqual({p.number for p in pad_items}, {str(i) for i in range(1, 9)})

    def test_002_smd_pads_use_pt_smd_and_no_drill(self):
        from kipy.board_types import PadType

        pads = kw.generate_pad_layout("SOIC-8", [p["number"] for p in _SOIC8_SCHEMA["pins"]], _SOIC8_DIMS)
        fi = kw.build_footprint_instance(_SOIC8_SCHEMA, pads, _SOIC8_SCHEMA["courtyard"])
        for pad in fi.definition.pads:
            self.assertEqual(pad.pad_type, PadType.PT_SMD)

    def test_003_through_hole_pads_use_pt_pth_with_a_real_drill(self):
        from kipy.board_types import PadType

        pads = kw.generate_pad_layout("DIP-8", [p["number"] for p in _DIP8_SCHEMA["pins"]], _DIP8_DIMS)
        fi = kw.build_footprint_instance(_DIP8_SCHEMA, pads, _DIP8_SCHEMA["courtyard"])
        for pad in fi.definition.pads:
            self.assertEqual(pad.pad_type, PadType.PT_PTH)
            self.assertGreater(pad.padstack.drill.diameter.x, 0)

    def test_004_courtyard_rectangle_matches_the_schema(self):
        from kipy.board_types import BoardLayer

        pads = kw.generate_pad_layout("SOIC-8", [p["number"] for p in _SOIC8_SCHEMA["pins"]], _SOIC8_DIMS)
        fi = kw.build_footprint_instance(_SOIC8_SCHEMA, pads, _SOIC8_SCHEMA["courtyard"])
        courtyard_shapes = [s for s in fi.definition.shapes if s.layer == BoardLayer.BL_F_CrtYd]
        self.assertEqual(len(courtyard_shapes), 1)
        rect = courtyard_shapes[0]
        width_mm = (rect.bottom_right.x - rect.top_left.x) / 1e6
        self.assertAlmostEqual(width_mm, _SOIC8_SCHEMA["courtyard"]["length_mm"])

    def test_005_reference_and_value_fields_are_set(self):
        pads = kw.generate_pad_layout("SOIC-8", [p["number"] for p in _SOIC8_SCHEMA["pins"]], _SOIC8_DIMS)
        fi = kw.build_footprint_instance(_SOIC8_SCHEMA, pads, _SOIC8_SCHEMA["courtyard"])
        self.assertEqual(fi.value_field.text.value, "ATTINY85")


class TestRealKicadWrite(unittest.TestCase):
    """Real, non-mocked verification against whatever KiCad instance is
    actually running with a board open -- CLAUDE.md's 'verify for real'
    norm. Deliberately never calls board.push_commit or board.save: a
    developer running this suite may have a real board of their own
    open, and this test must never be able to mutate it on disk no
    matter what. Every real write here is created via begin_commit /
    create_items and always discarded via drop_commit, proven by
    re-checking get_footprints()'s count before and after. Skips itself
    cleanly when no live KiCad IPC socket is reachable, matching
    CTX-103.1/104.1 precedent."""

    def _get_board_or_skip(self):
        # A real connection attempt, not a socket-file existence check:
        # macOS doesn't reliably unlink the socket file when KiCad exits,
        # so a stale leftover file would make this test fail for real
        # instead of skipping cleanly.
        from kipy import KiCad
        from kipy.errors import ApiError
        from kipy.errors import ConnectionError as KiCadConnectionError

        try:
            return KiCad().get_board()
        except KiCadConnectionError as e:
            self.skipTest(
                f"No live KiCad IPC connection reachable: {e} Enable the IPC "
                "API (Preferences > Plugins), launch KiCad, and open a board "
                "in the PCB Editor to run this test for real."
            )
        except ApiError as e:
            self.skipTest(f"KiCad is running but no board is open in the PCB Editor: {e}")

    def test_001_a_real_footprint_can_be_created_and_is_always_discarded(self):
        board = self._get_board_or_skip()
        before = len(board.get_footprints())

        pads = kw.generate_pad_layout("SOIC-8", [p["number"] for p in _SOIC8_SCHEMA["pins"]], _SOIC8_DIMS)
        fi = kw.build_footprint_instance(_SOIC8_SCHEMA, pads, _SOIC8_SCHEMA["courtyard"])
        from kipy.geometry import Vector2
        fi.position = Vector2.from_xy_mm(100, 100)

        commit = board.begin_commit()
        try:
            created = board.create_items([fi])
            self.assertEqual(len(created), 1)
        finally:
            board.drop_commit(commit)

        after = len(board.get_footprints())
        self.assertEqual(before, after, "drop_commit must leave the board exactly as it was")

    def test_002_a_through_hole_footprint_can_be_created_and_is_always_discarded(self):
        board = self._get_board_or_skip()
        before = len(board.get_footprints())

        pads = kw.generate_pad_layout("DIP-8", [p["number"] for p in _DIP8_SCHEMA["pins"]], _DIP8_DIMS)
        fi = kw.build_footprint_instance(_DIP8_SCHEMA, pads, _DIP8_SCHEMA["courtyard"])
        from kipy.geometry import Vector2
        fi.position = Vector2.from_xy_mm(120, 100)

        commit = board.begin_commit()
        try:
            board.create_items([fi])
        finally:
            board.drop_commit(commit)

        after = len(board.get_footprints())
        self.assertEqual(before, after, "drop_commit must leave the board exactly as it was")


if __name__ == '__main__':
    unittest.main()


class TestPdipIsTheSamePackageAsDip(unittest.TestCase):
    """CTX-202.5: "Inject into open board" refused the tutorial's own ATtiny85.

    Not because KiCad was closed, and not because the part lacked
    measurements -- because its package is called PDIP-8, and this module
    accepted only DIP-8. The geometry is identical, and this module's own
    comments cite the ATtiny85's PDIP-8 mechanical drawing to justify the
    DIP row spacing.

    `component_pipeline.PACKAGE_REFERENCE` has aliased PDIP-N to DIP-N since
    a live test hit the same mismatch on the same family. This was the second
    list, disagreeing.
    """

    DIMS = {"length_mm": 9.81, "width_mm": 6.35, "pitch_mm": 2.54}

    def _pins(self, n):
        return [str(i) for i in range(1, n + 1)]

    def test_001_pdip8_produces_exactly_the_dip8_layout(self):
        """A true alias, not merely an accepted spelling: same pads, same
        positions, same drills."""
        self.assertEqual(
            kw.generate_pad_layout("PDIP-8", self._pins(8), self.DIMS),
            kw.generate_pad_layout("DIP-8", self._pins(8), self.DIMS),
        )

    def test_002_pdip14_too(self):
        self.assertEqual(
            kw.generate_pad_layout("PDIP-14", self._pins(14), self.DIMS),
            kw.generate_pad_layout("DIP-14", self._pins(14), self.DIMS),
        )

    def test_003_pdip_stays_through_hole(self):
        """A PDIP whose pads came out surface-mount would be a footprint you
        cannot solder the part into."""
        pads = kw.generate_pad_layout("PDIP-8", self._pins(8), self.DIMS)

        self.assertTrue(all(pad["drill_mm"] for pad in pads))
        self.assertIn("PDIP-8", kw.THROUGH_HOLE_PACKAGES)

    def test_004_the_aliases_are_generated_not_listed(self):
        """Every DIP this module supports has its PDIP spelling, now and
        after the next one is added. A hand-written second list is what
        produced this bug."""
        for package in kw.SUPPORTED_PACKAGES:
            if package.startswith("DIP-"):
                self.assertIn(f"P{package}", kw.SUPPORTED_PACKAGES)

    def test_005_extraction_and_injection_agree_about_dip_family_names(self):
        """The parity that was missing. Anything the extraction pipeline can
        name and this module can build must be spelled the same way in both."""
        import component_pipeline

        for package in component_pipeline.PACKAGE_REFERENCE:
            if not package.startswith(("DIP-", "PDIP-")):
                continue
            base = package[1:] if package.startswith("PDIP-") else package
            if base in kw.SUPPORTED_PACKAGES:
                self.assertIn(
                    package, kw.SUPPORTED_PACKAGES,
                    f"{package} is a known package whose geometry this module can build, "
                    f"but injection refuses the name",
                )

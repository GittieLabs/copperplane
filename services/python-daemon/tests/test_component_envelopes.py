"""SPEC-326: clearance envelopes for components with no 3D model.

The maintainer's own blinking-LED board is the motivating case: BT1's
footprint references a .step that does not exist, and KiCad's Battery
library ships 53 footprints against 29 models. Without an envelope the
enclosure cannot be sized for the tallest part on the board.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import daemon  # noqa: E402
import kicad_bridge  # noqa: E402

KI = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"


class TestCourtyardExtraction(unittest.TestCase):
    """Real footprints on disk, per CLAUDE.md's verify-against-the-real-thing
    norm. Skips cleanly where KiCad is not installed."""

    def setUp(self):
        if not os.path.isdir(KI):
            self.skipTest("KiCad footprint libraries not installed")

    def test_001_a_circle_courtyard_uses_centre_plus_radius(self):
        """The bug this pins: CP_Radial_D5.0mm's courtyard is a single
        FpCircle. Reading only the two points that define it gave
        2.75 x 0.00 mm -- a zero-height envelope for a 5.5mm part."""
        out = kicad_bridge.read_footprint_courtyard(
            f"{KI}/Capacitor_THT.pretty/CP_Radial_D5.0mm_P2.50mm.kicad_mod"
        )
        self.assertAlmostEqual(5.5, out["x_mm"], places=2)
        self.assertAlmostEqual(5.5, out["y_mm"], places=2)

    def test_002_an_arc_bulges_past_its_endpoints(self):
        """`mid` is load-bearing: without it this footprint measured
        32.90 x 17.00 instead of 32.90 x 21.40, understating the real
        keep-out by 4mm."""
        out = kicad_bridge.read_footprint_courtyard(
            f"{KI}/Battery.pretty/BatteryHolder_Keystone_1060_1x2032.kicad_mod"
        )
        self.assertAlmostEqual(32.9, out["x_mm"], places=1)
        self.assertGreater(out["y_mm"], 21.0)

    def test_003_a_missing_or_unreadable_footprint_is_none_not_zero(self):
        self.assertIsNone(kicad_bridge.read_footprint_courtyard("/nonexistent.kicad_mod"))


class TestComponentEnvelopes(unittest.TestCase):
    """SPEC-326 §2.3's ordered sources, and the counters that let a caller
    tell a measured volume from a stated one."""

    CRTYD = {"x_mm": 10.0, "y_mm": 5.0}

    def _component(self, **over):
        base = {"reference": "R1", "footprint": "Lib:Part", "courtyard": dict(self.CRTYD),
                "model_path": None}
        base.update(over)
        return base

    def test_004_a_real_model_is_read_not_merely_noted(self):
        """Reporting a component as measured while carrying no height would
        be a claim with nothing behind it."""
        with patch('daemon.freecad_bridge.get_step_bounding_box_mm',
                   return_value={"x_mm": 9.0, "y_mm": 4.0, "z_mm": 6.98}):
            out = daemon.component_envelopes([self._component(model_path="/m.step")])
        envelope = out["envelopes"][0]
        self.assertEqual("model", envelope["source"])
        self.assertAlmostEqual(6.98, envelope["z_mm"])
        self.assertEqual(1, out["measured"])

    def test_005_a_user_height_is_keyed_by_footprint_not_reference(self):
        """SPEC-326 §2.5: ten identical resistors are one decision, and it
        survives a schematic edit that renumbers references."""
        out = daemon.component_envelopes(
            [self._component(reference="R1"), self._component(reference="R7")],
            {"Lib:Part": 15.5},
        )
        self.assertEqual([15.5, 15.5], [e["z_mm"] for e in out["envelopes"]])
        self.assertEqual(2, out["stated"])

    def test_006_no_source_means_unknown_never_a_default(self):
        """§2.3 refuses a fifth option. A guessed height fails as a physical
        object that does not fit."""
        out = daemon.component_envelopes([self._component()])
        self.assertEqual("unknown", out["envelopes"][0]["source"])
        self.assertIsNone(out["envelopes"][0]["z_mm"])
        self.assertEqual(1, out["unknown"])

    def test_007_a_model_wins_over_a_user_height(self):
        with patch('daemon.freecad_bridge.get_step_bounding_box_mm',
                   return_value={"x_mm": 1, "y_mm": 1, "z_mm": 5.08}):
            out = daemon.component_envelopes([self._component(model_path="/m.step")], {"Lib:Part": 99.0})
        self.assertEqual("model", out["envelopes"][0]["source"])
        self.assertAlmostEqual(5.08, out["envelopes"][0]["z_mm"])

    def test_008_an_unreadable_model_falls_through_rather_than_failing(self):
        """A model that will not read is an ordinary state -- it must fall to
        the next source, not blank the whole envelope set."""
        with patch('daemon.freecad_bridge.get_step_bounding_box_mm',
                   side_effect=RuntimeError("freecadcmd exploded")):
            out = daemon.component_envelopes([self._component(model_path="/m.step")], {"Lib:Part": 12.0})
        self.assertEqual("user", out["envelopes"][0]["source"])
        self.assertAlmostEqual(12.0, out["envelopes"][0]["z_mm"])

    def test_009_a_footprint_with_no_courtyard_reports_no_xy_source(self):
        out = daemon.component_envelopes([self._component(courtyard=None)])
        envelope = out["envelopes"][0]
        self.assertIsNone(envelope["x_mm"])
        self.assertFalse(envelope["x_within_courtyard"])

    def test_010_counters_separate_measured_from_stated(self):
        """SPEC-326 §2.4: a user reading a clearance result must be able to
        tell which volumes were measured and which were stated."""
        with patch('daemon.freecad_bridge.get_step_bounding_box_mm',
                   return_value={"x_mm": 1, "y_mm": 1, "z_mm": 3.0}):
            out = daemon.component_envelopes(
                [self._component(reference="A", model_path="/m.step"),
                 self._component(reference="B", footprint="Lib:Other"),
                 self._component(reference="C", footprint="Lib:Third")],
                {"Lib:Other": 8.0},
            )
        self.assertEqual((1, 1, 1), (out["measured"], out["stated"], out["unknown"]))


if __name__ == "__main__":
    unittest.main()


class TestPlaceholdersForEnclosure(unittest.TestCase):
    """CTX-326.4 Phase 2: joining where a part is to how big it is.

    Three facts have to meet correctly and each comes from somewhere
    different -- position off the board, X/Y off the courtyard, Z from
    `SPEC-326` §2.3's ordered sources. Getting the join wrong produces a
    volume that renders perfectly somewhere it is not."""

    OUTLINE = {"x_mm": 100.0, "y_mm": 80.0, "width_mm": 50.0, "height_mm": 40.0}

    def _placeholders(self, components, envelopes, margin=2.5):
        import daemon
        return daemon.placeholders_for_enclosure(components, envelopes, self.OUTLINE, margin)

    def test_position_is_offset_by_the_same_mapping_standoffs_use(self):
        got = self._placeholders(
            [{"reference": "BT1", "pos_x_mm": 110.0, "pos_y_mm": 90.0, "rotation_deg": 0}],
            [{"reference": "BT1", "x_mm": 20.0, "y_mm": 20.0, "z_mm": 4.0, "source": "user"}],
        )

        # 110 - 100 + 2.5, and 90 - 80 + 2.5.
        self.assertEqual((got[0]["x_mm"], got[0]["y_mm"]), (12.5, 12.5))

    def test_courtyard_extents_become_width_and_depth_never_a_position(self):
        """The record this reads carries `pos_x_mm` (a position) and an
        envelope `x_mm` (a size). Two keys spelled almost the same, meaning
        different things, joined to place geometry -- so this pins which is
        which rather than trusting the naming to hold."""
        got = self._placeholders(
            [{"reference": "U1", "pos_x_mm": 130.0, "pos_y_mm": 100.0, "rotation_deg": 0}],
            [{"reference": "U1", "x_mm": 7.5, "y_mm": 3.25, "z_mm": 2.0, "source": "model"}],
        )

        self.assertEqual(got[0]["width_mm"], 7.5)
        self.assertEqual(got[0]["depth_mm"], 3.25)
        self.assertEqual(got[0]["x_mm"], 32.5)

    def test_a_component_with_no_height_is_omitted_not_defaulted(self):
        got = self._placeholders(
            [{"reference": "X1", "pos_x_mm": 110.0, "pos_y_mm": 90.0, "rotation_deg": 0}],
            [{"reference": "X1", "x_mm": 5.0, "y_mm": 5.0, "z_mm": None, "source": "unknown"}],
        )
        self.assertEqual(got, [])

    def test_a_component_with_no_courtyard_is_omitted(self):
        got = self._placeholders(
            [{"reference": "X1", "pos_x_mm": 110.0, "pos_y_mm": 90.0, "rotation_deg": 0}],
            [{"reference": "X1", "x_mm": None, "y_mm": None, "z_mm": 4.0, "source": "user"}],
        )
        self.assertEqual(got, [])

    def test_a_component_with_no_position_is_omitted_rather_than_put_at_the_origin(self):
        """A malformed `at` must not become (0, 0). A volume in the corner of
        the board looks deliberate and is not."""
        got = self._placeholders(
            [{"reference": "X1", "pos_x_mm": None, "pos_y_mm": None, "rotation_deg": 0}],
            [{"reference": "X1", "x_mm": 5.0, "y_mm": 5.0, "z_mm": 4.0, "source": "user"}],
        )
        self.assertEqual(got, [])

    def test_rotation_carries_through(self):
        got = self._placeholders(
            [{"reference": "SW1", "pos_x_mm": 110.0, "pos_y_mm": 90.0, "rotation_deg": 90}],
            [{"reference": "SW1", "x_mm": 6.0, "y_mm": 3.0, "z_mm": 5.0, "source": "user"}],
        )
        self.assertEqual(got[0]["rotation_deg"], 90)

    def test_an_envelope_with_no_matching_component_is_skipped_not_guessed(self):
        got = self._placeholders(
            [{"reference": "R1", "pos_x_mm": 110.0, "pos_y_mm": 90.0, "rotation_deg": 0}],
            [{"reference": "GONE", "x_mm": 5.0, "y_mm": 5.0, "z_mm": 4.0, "source": "user"}],
        )
        self.assertEqual(got, [])

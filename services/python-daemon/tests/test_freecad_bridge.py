import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import freecad_bridge
from freecad_bridge import (
    FreeCADBuildError,
    FreeCADCancelledError,
    FreeCADUnavailableError,
    export_enclosure,
    find_freecadcmd,
    generate_enclosure,
    get_step_bounding_box_mm,
)


class TestFreeCADBridge(unittest.TestCase):

    def setUp(self):
        # The path/output-dir overrides and last-glb/last-step trackers
        # are all module-level state; make sure no test leaks one into
        # another.
        freecad_bridge._path_override = None
        freecad_bridge._output_dir_override = None
        freecad_bridge._last_glb_path = None
        freecad_bridge._last_step_path = None
        freecad_bridge._last_lid_glb_path = None
        freecad_bridge._last_lid_step_path = None

    def tearDown(self):
        freecad_bridge._path_override = None
        freecad_bridge._output_dir_override = None
        freecad_bridge._last_glb_path = None
        freecad_bridge._last_step_path = None
        freecad_bridge._last_lid_glb_path = None
        freecad_bridge._last_lid_step_path = None

    @patch('freecad_bridge.glob.glob', return_value=[])
    @patch('freecad_bridge.shutil.which', return_value=None)
    def test_001_no_executable_found_raises_clean_error(self, mock_which, mock_glob):
        """TEST-001: `find_freecadcmd` raises a clean error when no
        executable is found on PATH or any known install location."""
        with self.assertRaises(FreeCADUnavailableError) as ctx:
            find_freecadcmd()

        self.assertIn("Could not find the freecadcmd executable", str(ctx.exception))

    @patch('freecad_bridge.subprocess.Popen')
    @patch('freecad_bridge.find_freecadcmd', return_value='/fake/freecadcmd')
    def test_002_nonzero_exit_raises_clean_error(self, mock_find, mock_popen):
        """TEST-002: A non-zero freecadcmd exit (build script failure) is
        caught and raised as a clean error, not a raw CalledProcessError."""
        mock_popen.return_value.communicate.return_value = ("", "Syntax error in script")
        mock_popen.return_value.returncode = 1

        with self.assertRaises(FreeCADBuildError) as ctx:
            generate_enclosure(width=50, depth=30, height=20)

        self.assertIn("exited with code 1", str(ctx.exception))
        self.assertIn("Syntax error in script", str(ctx.exception))

    @patch('freecad_bridge.time.monotonic')
    @patch('freecad_bridge.subprocess.Popen')
    @patch('freecad_bridge.find_freecadcmd', return_value='/fake/freecadcmd')
    def test_003_timeout_raises_clean_error(self, mock_find, mock_popen, mock_monotonic):
        """TEST-003: A freecadcmd subprocess that exceeds the timeout is
        raised as a clean, specific error."""

        def communicate_side_effect(timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired(cmd='freecadcmd', timeout=timeout)
            return ("", "")

        mock_popen.return_value.communicate.side_effect = communicate_side_effect
        # First call is _wait_with_cancellation's `start = time.monotonic()`;
        # the second is the elapsed-time check on the first poll iteration --
        # jumping straight past timeout_s avoids a real 30s sleep in this test.
        mock_monotonic.side_effect = [0, 31]

        with self.assertRaises(FreeCADBuildError) as ctx:
            generate_enclosure(width=50, depth=30, height=20, timeout_s=30.0)

        self.assertIn("did not finish within 30.0s", str(ctx.exception))
        mock_popen.return_value.kill.assert_called_once()

    def test_004_real_enclosure_round_trip(self):
        """TEST-004: `freecad.generate_enclosure` produces a real, valid
        `.glb` file end-to-end against a real, locally installed FreeCAD.
        Skips itself (rather than failing) when freecadcmd isn't found —
        e.g. in CI, where FreeCAD isn't installed at all."""
        try:
            find_freecadcmd()
        except FreeCADUnavailableError:
            self.skipTest(
                "No local freecadcmd found. Install FreeCAD 0.20+ to run this "
                "test for real."
            )

        result = generate_enclosure(width=50, depth=30, height=20)
        glb_path, step_path = result["glb_path"], result["step_path"]
        try:
            self.assertTrue(os.path.exists(glb_path))
            with open(glb_path, 'rb') as f:
                header = f.read(4)
            self.assertEqual(header, b'glTF', "output should be a real glTF binary, not just a renamed STL")

            # CTX-109.4: real, confirmed unit-scale bug -- this exact real
            # 50x30x20mm box's own .glb used to report a bounding box of
            # 50x30x20 *meters* (1000x too large relative to glTF's own
            # real-meter convention), confirmed live while investigating
            # whether a real board's own .glb (kicad-cli's, correctly
            # scaled) could ever be shown alongside this one. Real,
            # direct regression coverage: load the real output and check
            # its real bounding box against the real mm input, not just
            # that a glTF header exists.
            import trimesh
            mesh = trimesh.load(glb_path)
            extents_mm = mesh.extents * 1000
            for actual, expected in zip(sorted(extents_mm), sorted([50, 30, 20])):
                self.assertAlmostEqual(actual, expected, delta=0.5)
        finally:
            if os.path.exists(glb_path):
                os.remove(glb_path)
            if os.path.exists(step_path):
                os.remove(step_path)

    @patch('freecad_bridge.subprocess.Popen')
    @patch('freecad_bridge.find_freecadcmd', return_value='/fake/freecadcmd')
    def test_005_cancel_event_terminates_subprocess_early(self, mock_find, mock_popen):
        """TEST-005: setting `cancel_event` while `generate_enclosure` is
        waiting on freecadcmd kills the subprocess early (CTX-105.1),
        instead of running to completion or timing out."""
        cancel_event = threading.Event()
        cancel_event.set()

        def communicate_side_effect(timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired(cmd='freecadcmd', timeout=timeout)
            return ("", "")

        mock_popen.return_value.communicate.side_effect = communicate_side_effect

        with self.assertRaises(FreeCADCancelledError):
            generate_enclosure(width=50, depth=30, height=20, cancel_event=cancel_event)

        mock_popen.return_value.kill.assert_called_once()

    def test_006_configure_override_is_honored_when_path_exists(self):
        """TEST-005 (CTX-106.1): freecad_bridge.configure's path override
        is honored by find_freecadcmd when the path is a real file --
        a genuine filesystem check, not mocked, since that's cheap and
        real to do."""
        with tempfile.NamedTemporaryFile() as fake_freecadcmd:
            freecad_bridge.configure(path_override=fake_freecadcmd.name)
            self.assertEqual(find_freecadcmd(), fake_freecadcmd.name)

    def test_007_configure_override_raises_clean_error_when_path_missing(self):
        """TEST-005 (CTX-106.1): a configured-but-missing override path
        raises a clean, specific error instead of silently falling back
        to the PATH/glob search."""
        freecad_bridge.configure(path_override='/definitely/not/a/real/path/freecadcmd')

        with self.assertRaises(FreeCADUnavailableError) as ctx:
            find_freecadcmd()

        self.assertIn("Configured freecadcmd path override does not exist", str(ctx.exception))

    def test_008_output_dir_override_is_honored_for_real(self):
        """TEST-006 (CTX-301.1): generate_enclosure writes its .glb under
        a configured output_dir instead of the shared OS temp directory --
        verified for real against the actually-installed FreeCAD, same
        'verify for real' pattern as TEST-004. Skips itself cleanly when
        no freecadcmd is found, e.g. in CI."""
        try:
            find_freecadcmd()
        except FreeCADUnavailableError:
            self.skipTest(
                "No local freecadcmd found. Install FreeCAD 0.20+ to run this "
                "test for real."
            )

        with tempfile.TemporaryDirectory() as output_dir:
            freecad_bridge.configure(output_dir=output_dir)
            result = generate_enclosure(width=50, depth=30, height=20)

            self.assertEqual(os.path.dirname(result["glb_path"]), output_dir)
            self.assertEqual(os.path.dirname(result["step_path"]), output_dir)
            self.assertTrue(os.path.exists(result["glb_path"]))
            self.assertTrue(os.path.exists(result["step_path"]))

    def test_009_previous_glb_is_deleted_on_next_successful_generation(self):
        """TEST-006 (CTX-301.1): SPEC-301's flagged known debt -- nothing
        previously deleted a generated .glb, harmless in a self-cleaning
        OS temp dir, a real leak in a persistent output_dir. Generating a
        second enclosure deletes the first's .glb, bounding the leak to
        at most one extra file rather than unbounded growth. Verified for
        real; skips itself cleanly when no freecadcmd is found."""
        try:
            find_freecadcmd()
        except FreeCADUnavailableError:
            self.skipTest(
                "No local freecadcmd found. Install FreeCAD 0.20+ to run this "
                "test for real."
            )

        with tempfile.TemporaryDirectory() as output_dir:
            freecad_bridge.configure(output_dir=output_dir)

            first = generate_enclosure(width=50, depth=30, height=20)
            self.assertTrue(os.path.exists(first["glb_path"]))
            self.assertTrue(os.path.exists(first["step_path"]))

            second = generate_enclosure(width=60, depth=40, height=25)

            self.assertFalse(os.path.exists(first["glb_path"]), "the previous .glb should be cleaned up")
            self.assertFalse(os.path.exists(first["step_path"]), "the previous .step should be cleaned up")
            self.assertTrue(os.path.exists(second["glb_path"]))
            self.assertTrue(os.path.exists(second["step_path"]))

    def test_010_neither_board_outline_nor_width_and_depth_is_rejected(self):
        """SPEC-109 §2: exactly one real mode must be chosen -- a call
        with neither board_outline nor width/depth is a caller bug, not
        a silently-guessed zero-size enclosure."""
        with self.assertRaises(ValueError):
            generate_enclosure(height=20)

    def test_011_get_step_bounding_box_mm_real_round_trip(self):
        """CTX-311.1: `get_step_bounding_box_mm` against a real,
        `generate_enclosure`-produced `.step` file -- reuses this
        module's own real output as a real input, the same real
        50x30x20mm box `TEST-004` already verifies via `.glb`, this
        time reading the `.step` side directly. Skips itself cleanly
        when no freecadcmd is found, same convention as every other
        real test in this module."""
        try:
            find_freecadcmd()
        except FreeCADUnavailableError:
            self.skipTest(
                "No local freecadcmd found. Install FreeCAD 0.20+ to run this "
                "test for real."
            )

        result = generate_enclosure(width=50, depth=30, height=20)
        glb_path, step_path = result["glb_path"], result["step_path"]
        try:
            bbox = get_step_bounding_box_mm(step_path)
            self.assertAlmostEqual(bbox["x_mm"], 50, delta=0.01)
            self.assertAlmostEqual(bbox["y_mm"], 30, delta=0.01)
            self.assertAlmostEqual(bbox["z_mm"], 20, delta=0.01)
        finally:
            if os.path.exists(glb_path):
                os.remove(glb_path)
            if os.path.exists(step_path):
                os.remove(step_path)

    def test_012_a_missing_model_file_raises_a_clean_error(self):
        with self.assertRaises(FreeCADBuildError) as ctx:
            get_step_bounding_box_mm('/nonexistent/model.step')
        self.assertIn("does not exist", str(ctx.exception))

    def test_013_lid_requires_board_driven_mode(self):
        """CTX-311.2: manual mode's box has no open top for a lid to
        close -- a caller bug, not a silently-ignored parameter."""
        with self.assertRaises(ValueError) as ctx:
            generate_enclosure(height=20, width=50, depth=30, lid=True)
        self.assertIn("board-driven mode", str(ctx.exception))


_TEST_BOARD_OUTLINE = {"x_mm": 0.0, "y_mm": 0.0, "width_mm": 20.0, "height_mm": 15.0}


class TestBoardDrivenEnclosure(unittest.TestCase):
    """SPEC-109/CTX-109.1: real geometry verification against an actually
    installed FreeCAD (the same 'verify for real' pattern as
    TestFreeCADBridge's TEST-004/008/009) -- a hollow shell and standoff
    cylinders are real solid-modeling operations worth checking against
    the real thing, not just a script that ran without raising."""

    def setUp(self):
        freecad_bridge._path_override = None
        freecad_bridge._output_dir_override = None
        freecad_bridge._last_glb_path = None
        freecad_bridge._last_step_path = None
        freecad_bridge._last_lid_glb_path = None
        freecad_bridge._last_lid_step_path = None

    def tearDown(self):
        freecad_bridge._path_override = None
        freecad_bridge._output_dir_override = None
        freecad_bridge._last_glb_path = None
        freecad_bridge._last_step_path = None
        freecad_bridge._last_lid_glb_path = None
        freecad_bridge._last_lid_step_path = None

    def _skip_unless_freecad_available(self):
        try:
            find_freecadcmd()
        except FreeCADUnavailableError:
            self.skipTest(
                "No local freecadcmd found. Install FreeCAD 0.20+ to run this "
                "test for real."
            )

    def test_001_board_driven_mode_produces_a_real_hollow_shell(self):
        """TEST-004 (CTX-109.1): the result's real volume matches a real
        hollow shell (outer box minus inner cavity), not a solid box --
        fillet/standoffs disabled here so the expected volume is exact."""
        self._skip_unless_freecad_available()
        import trimesh

        result = generate_enclosure(
            height=10,
            board_outline=_TEST_BOARD_OUTLINE,
            wall_thickness_mm=2.0,
            clearance_mm=0.5,
            standoffs=[],
            fillet_radius_mm=0,
        )
        try:
            mesh = trimesh.load(result["glb_path"])
            # margin = clearance + wall = 2.5; outer 25x20x10; inner cavity
            # (clearance-only margin, 21x16) starts at z=wall=2 and runs to
            # z=height=10 (height - wall = 8 tall) -- a solid 2mm floor at
            # the bottom, open top. A real bug (CTX-109.2 Plan Drift, found
            # by live user testing): the first version cut the inner box
            # the *full* height starting at z=0, producing an open-both-ends
            # tube with no floor at all -- this expected volume is exact
            # only under the fixed geometry.
            expected_volume_mm3 = (25 * 20 * 10) - (21 * 16 * 8)
            # CTX-109.4: the real .glb is now correctly scaled to glTF's own
            # meter convention (`apply_scale(0.001)`, a real, live-confirmed
            # unit-scale bug fix -- see freecad_bridge.py's own comment) --
            # mesh.volume is therefore in real m^3, not the "mm numbers
            # embedded as bare floats" this test's own expected_volume_mm3
            # is computed in. Convert back to mm^3 to compare like with like.
            actual_volume_mm3 = mesh.volume * 1e9
            self.assertAlmostEqual(actual_volume_mm3, expected_volume_mm3, delta=expected_volume_mm3 * 0.01)
        finally:
            for path in (result["glb_path"], result["step_path"]):
                if os.path.exists(path):
                    os.remove(path)

    def test_002_a_standoff_adds_real_cylinder_volume(self):
        """TEST-005 (CTX-109.1): a standoff cylinder placed well inside
        the cavity (away from the walls, no overlap) adds its own real,
        computable volume to the result."""
        self._skip_unless_freecad_available()
        import trimesh

        standoff = {"x_mm": 10.0, "y_mm": 7.5, "diameter_mm": 3.2, "height_mm": 5.0}
        result = generate_enclosure(
            height=10,
            board_outline=_TEST_BOARD_OUTLINE,
            wall_thickness_mm=2.0,
            clearance_mm=0.5,
            standoffs=[standoff],
            fillet_radius_mm=0,
        )
        try:
            mesh = trimesh.load(result["glb_path"])
            shell_volume = (25 * 20 * 10) - (21 * 16 * 8)
            r = standoff["diameter_mm"] / 2
            import math
            standoff_volume = math.pi * (r ** 2) * standoff["height_mm"]
            expected_volume_mm3 = shell_volume + standoff_volume
            # CTX-109.4: mesh.volume is now real m^3 (see test_001's own
            # comment on the real unit-scale fix) -- convert back to mm^3.
            actual_volume_mm3 = mesh.volume * 1e9
            self.assertAlmostEqual(
                actual_volume_mm3, expected_volume_mm3, delta=expected_volume_mm3 * 0.02,
            )
        finally:
            for path in (result["glb_path"], result["step_path"]):
                if os.path.exists(path):
                    os.remove(path)

    def test_003_exports_a_real_non_empty_step_file(self):
        """TEST-006 (CTX-109.1): a real STEP file (ISO-10303-21 header),
        not an empty placeholder -- SPEC-109's own real mechanical-CAD
        interchange requirement."""
        self._skip_unless_freecad_available()

        result = generate_enclosure(
            height=10, board_outline=_TEST_BOARD_OUTLINE, standoffs=[], fillet_radius_mm=0,
        )
        try:
            self.assertTrue(os.path.exists(result["step_path"]))
            with open(result["step_path"], "r", encoding="utf-8", errors="ignore") as f:
                header = f.read(20)
            self.assertIn("ISO-10303-21", header)
        finally:
            for path in (result["glb_path"], result["step_path"]):
                if os.path.exists(path):
                    os.remove(path)

    def test_004_a_real_lid_matches_the_shells_own_outer_footprint(self):
        """CTX-311.2: the lid's own real bounding box matches the
        shell's outer footprint (board width/height plus clearance and
        wall margin on every side) in X/Y, and its own configured
        thickness in Z -- verified against a real freecadcmd, not just
        that a file was produced."""
        self._skip_unless_freecad_available()
        import trimesh

        result = generate_enclosure(
            height=10,
            board_outline=_TEST_BOARD_OUTLINE,
            wall_thickness_mm=2.0,
            clearance_mm=0.5,
            standoffs=[],
            fillet_radius_mm=0,
            lid=True,
            lid_thickness_mm=3.0,
        )
        try:
            self.assertIn("lid_glb_path", result)
            self.assertIn("lid_step_path", result)
            self.assertTrue(os.path.exists(result["lid_glb_path"]))
            self.assertTrue(os.path.exists(result["lid_step_path"]))

            margin = 0.5 + 2.0
            expected_w = _TEST_BOARD_OUTLINE["width_mm"] + 2 * margin
            expected_d = _TEST_BOARD_OUTLINE["height_mm"] + 2 * margin

            mesh = trimesh.load(result["lid_glb_path"])
            extents_mm = mesh.extents * 1000
            for actual, expected in zip(
                sorted(extents_mm), sorted([expected_w, expected_d, 3.0]),
            ):
                self.assertAlmostEqual(actual, expected, delta=0.01)
        finally:
            for key in ("glb_path", "step_path", "lid_glb_path", "lid_step_path"):
                if os.path.exists(result[key]):
                    os.remove(result[key])

    def test_005_lid_thickness_defaults_to_wall_thickness_when_not_given(self):
        self._skip_unless_freecad_available()
        import trimesh

        result = generate_enclosure(
            height=10,
            board_outline=_TEST_BOARD_OUTLINE,
            wall_thickness_mm=2.5,
            clearance_mm=0.5,
            standoffs=[],
            fillet_radius_mm=0,
            lid=True,
        )
        try:
            mesh = trimesh.load(result["lid_glb_path"])
            extents_mm = mesh.extents * 1000
            self.assertAlmostEqual(min(extents_mm), 2.5, delta=0.01)
        finally:
            for key in ("glb_path", "step_path", "lid_glb_path", "lid_step_path"):
                if os.path.exists(result[key]):
                    os.remove(result[key])

    def test_006_previous_lid_files_are_deleted_on_next_successful_generation(self):
        """Mirrors TestFreeCADBridge's own TEST-009 for the base shell --
        the same leak-bounded-to-one cleanup applies to the lid's own
        persistent output_dir files."""
        self._skip_unless_freecad_available()

        with tempfile.TemporaryDirectory() as tmp_dir:
            freecad_bridge.configure(output_dir=tmp_dir)
            result_1 = generate_enclosure(
                height=10, board_outline=_TEST_BOARD_OUTLINE, standoffs=[],
                fillet_radius_mm=0, lid=True,
            )
            first_lid_glb, first_lid_step = result_1["lid_glb_path"], result_1["lid_step_path"]
            self.assertTrue(os.path.exists(first_lid_glb))
            self.assertTrue(os.path.exists(first_lid_step))

            result_2 = generate_enclosure(
                height=12, board_outline=_TEST_BOARD_OUTLINE, standoffs=[],
                fillet_radius_mm=0, lid=True,
            )
            try:
                self.assertFalse(os.path.exists(first_lid_glb))
                self.assertFalse(os.path.exists(first_lid_step))
                self.assertTrue(os.path.exists(result_2["lid_glb_path"]))
                self.assertTrue(os.path.exists(result_2["lid_step_path"]))
            finally:
                for key in ("glb_path", "step_path", "lid_glb_path", "lid_step_path"):
                    if os.path.exists(result_2[key]):
                        os.remove(result_2[key])

    def test_007_a_real_lid_sits_on_top_of_the_shell_not_overlapping_its_floor(self):
        """CTX-311.5: real, confirmed bug found by live user testing --
        the lid's own Part.makeBox had no position vector, so it built
        at the origin, the exact same z-range as the shell's own solid
        floor, instead of atop the shell's real open top. This is a
        real, axis-aware position check (not just sorted extents, which
        test_004 already covers and which this exact bug passed) -- the
        real Y axis is height post-CTX-311.5's own axis fix (test_008
        below verifies that fix directly); this test checks the real
        gap between where the base's height ends and where the lid
        begins is ~0, not ~-height (fully overlapping from the bottom)."""
        self._skip_unless_freecad_available()
        import trimesh

        result = generate_enclosure(
            height=20, board_outline=_TEST_BOARD_OUTLINE, standoffs=[],
            fillet_radius_mm=0, lid=True, lid_thickness_mm=2.0,
        )
        try:
            base = trimesh.load(result["glb_path"])
            lid = trimesh.load(result["lid_glb_path"])

            base_top_y = base.bounds[1][1]
            lid_bottom_y = lid.bounds[0][1]
            self.assertAlmostEqual(lid_bottom_y - base_top_y, 0.0, delta=0.0005)

            lid_top_y = lid.bounds[1][1]
            self.assertAlmostEqual((lid_top_y - lid_bottom_y) * 1000, 2.0, delta=0.01)
        finally:
            for key in ("glb_path", "step_path", "lid_glb_path", "lid_step_path"):
                if os.path.exists(result[key]):
                    os.remove(result[key])

    def test_008_real_height_lands_on_the_y_axis_matching_gltfs_own_up_convention(self):
        """CTX-311.5: real, confirmed bug found by live user testing --
        `trimesh.load(stl_path); mesh.export(glb_path)` performs no axis
        remapping, so FreeCAD's own Z-up convention (`box.Height` is
        always the Z extent throughout this module's build scripts)
        stayed Z-up in the exported glTF, even though glTF's own spec
        convention -- and `EnclosureViewer.tsx`'s own camera math -- is
        Y-up. A real, axis-aware check: with a board deliberately much
        wider/deeper than tall, the real Y extent (not just any axis)
        must match the real height param."""
        self._skip_unless_freecad_available()
        import trimesh

        result = generate_enclosure(
            height=7, board_outline=_TEST_BOARD_OUTLINE, standoffs=[], fillet_radius_mm=0,
        )
        try:
            mesh = trimesh.load(result["glb_path"])
            y_extent_mm = mesh.extents[1] * 1000
            self.assertAlmostEqual(y_extent_mm, 7, delta=0.01)
            # The board outline (20x15mm) plus the default 2.5mm margin
            # on every side makes both X and Z visibly larger than the
            # real 7mm height -- a real, meaningful discriminator, not
            # a coincidence of similarly-sized dimensions.
            self.assertGreater(mesh.extents[0] * 1000, 7)
            self.assertGreater(mesh.extents[2] * 1000, 7)
        finally:
            for key in ("glb_path", "step_path"):
                if os.path.exists(result[key]):
                    os.remove(result[key])

    def test_009_real_base_and_lid_get_distinct_real_matte_materials(self):
        """CTX-311.7: real, confirmed bug found by live user testing --
        `Part.Shape.exportStl` writes plain, colorless geometry (STL has
        no material concept at all), and this module's own `.glb`
        export previously attached no material either. A mesh with no
        material in its own glTF file isn't blank or default-gray in
        any real glTF viewer: the glTF 2.0 spec's own default material
        (applied whenever a primitive omits one) is `metallicFactor: 1,
        roughnessFactor: 1` -- full metal, which renders near-black with
        no environment map to reflect, regardless of scene lighting.
        Verified directly here: the real exported `.glb` now carries a
        real, matte (`metallicFactor` 0) material, and the base shell
        and the lid get real, distinct real colors from each other.

        CTX-311.12: the base shell's own `.glb` is now a real, real
        two-geometry `Scene` (outer + inner cavity surfaces, see
        test_010 below), not a single mesh -- this test picks the base
        shell's *outer* geometry (the one whose own material's base
        color matches `_BODY_COLOR_RGB`) for the cross-part distinctness
        check below, so it keeps meaning the same real thing it always
        has: the base shell's outer surface and the lid are distinct
        colors from each other."""
        self._skip_unless_freecad_available()
        import trimesh

        result = generate_enclosure(
            height=10, board_outline=_TEST_BOARD_OUTLINE, standoffs=[],
            fillet_radius_mm=0, lid=True,
        )
        try:
            base_scene = trimesh.load(result["glb_path"])
            lid_scene = trimesh.load(result["lid_glb_path"])
            base_materials = [g.visual.material for g in base_scene.geometry.values()]
            lid_material = list(lid_scene.geometry.values())[0].visual.material
            base_outer_material = next(
                m for m in base_materials
                if tuple(m.baseColorFactor)[:3] == freecad_bridge._BODY_COLOR_RGB
            )

            for material in base_materials:
                self.assertEqual(material.metallicFactor, 0.0)
            self.assertEqual(lid_material.metallicFactor, 0.0)
            self.assertNotEqual(
                tuple(base_outer_material.baseColorFactor), tuple(lid_material.baseColorFactor),
            )
        finally:
            for key in ("glb_path", "step_path", "lid_glb_path", "lid_step_path"):
                if os.path.exists(result[key]):
                    os.remove(result[key])

    def test_010_real_cavity_walls_and_floor_get_a_distinct_brighter_color_from_the_outer_shell(self):
        """CTX-311.12: real user feedback across multiple click-through
        rounds ("can't see the inside corners," "hard to see where the
        edges of the floor meet the floor") -- even once the camera and
        lighting fixes (CTX-311.4 through CTX-311.11) made the cavity
        actually visible, a single uniform material gives no real color
        cue for where the floor and inner walls meet. This test verifies
        the real, direct fix: the base shell's own `.glb` now contains
        two real geometries with two real, distinct matte materials --
        one matching `_BODY_COLOR_RGB` (outer), one matching
        `_BODY_INNER_COLOR_RGB` (the cavity) -- and the inner one's own
        real vertices sit closer to the shell's horizontal center than
        the outer one's, a real, geometric sanity check that "inner"
        was classified correctly, not just that two colors exist."""
        self._skip_unless_freecad_available()
        import numpy as np
        import trimesh

        result = generate_enclosure(
            height=10, board_outline=_TEST_BOARD_OUTLINE, standoffs=[],
            fillet_radius_mm=0, lid=False,
        )
        try:
            base_scene = trimesh.load(result["glb_path"])
            geometries = list(base_scene.geometry.values())
            self.assertEqual(len(geometries), 2)

            colors = {tuple(g.visual.material.baseColorFactor)[:3] for g in geometries}
            self.assertEqual(
                colors, {freecad_bridge._BODY_COLOR_RGB, freecad_bridge._BODY_INNER_COLOR_RGB},
            )

            outer_mesh = next(
                g for g in geometries
                if tuple(g.visual.material.baseColorFactor)[:3] == freecad_bridge._BODY_COLOR_RGB
            )
            inner_mesh = next(
                g for g in geometries
                if tuple(g.visual.material.baseColorFactor)[:3] == freecad_bridge._BODY_INNER_COLOR_RGB
            )

            # Horizontal (X/Z, the glTF Y-up file's own footprint plane)
            # distance from the shell's own overall center -- the real
            # cavity's own walls/floor sit closer in than the real outer
            # shell's own walls/bottom do.
            center = base_scene.bounds.mean(axis=0)
            outer_radial = np.linalg.norm((outer_mesh.vertices - center)[:, [0, 2]], axis=1).mean()
            inner_radial = np.linalg.norm((inner_mesh.vertices - center)[:, [0, 2]], axis=1).mean()
            self.assertLess(inner_radial, outer_radial)
        finally:
            for key in ("glb_path", "step_path"):
                if os.path.exists(result[key]):
                    os.remove(result[key])

    def test_011_real_lid_stays_a_single_uniform_color_not_split(self):
        """CTX-311.12: the lid is a flat, solid slab -- convex, with no
        real cavity of its own -- so `_export_glb`'s inner/outer split
        is deliberately never applied to it (`inner_color_rgb` is only
        passed for the base shell's own call site). Verified directly:
        the lid's own `.glb` still contains exactly one real geometry,
        not two."""
        self._skip_unless_freecad_available()
        import trimesh

        result = generate_enclosure(
            height=10, board_outline=_TEST_BOARD_OUTLINE, standoffs=[],
            fillet_radius_mm=0, lid=True,
        )
        try:
            lid_scene = trimesh.load(result["lid_glb_path"])
            self.assertEqual(len(list(lid_scene.geometry.values())), 1)
        finally:
            for key in ("glb_path", "step_path", "lid_glb_path", "lid_step_path"):
                if os.path.exists(result[key]):
                    os.remove(result[key])


class TestExportEnclosureValidation(unittest.TestCase):
    """CTX-311.13: pure argument validation -- no real freecadcmd/trimesh
    work happens before these checks, so unlike every other test in this
    file they need no `_skip_unless_freecad_available` gate."""

    def test_001_unknown_parts_raises_a_clean_error(self):
        with self.assertRaises(ValueError) as ctx:
            export_enclosure("everything", "step", "/tmp/out.step", step_path="/tmp/e.step")
        self.assertIn("everything", str(ctx.exception))

    def test_002_unknown_format_raises_a_clean_error(self):
        with self.assertRaises(ValueError) as ctx:
            export_enclosure("body", "obj", "/tmp/out.obj", step_path="/tmp/e.step")
        self.assertIn("obj", str(ctx.exception))

    def test_003_lid_parts_without_a_lid_raises_a_clean_error_not_a_file_error(self):
        with self.assertRaises(ValueError) as ctx:
            export_enclosure("lid", "step", "/tmp/out.step", step_path="/tmp/e.step")
        self.assertIn("no lid was generated", str(ctx.exception))

    def test_004_combined_glb_without_a_lid_raises_a_clean_error(self):
        with self.assertRaises(ValueError) as ctx:
            export_enclosure("combined", "glb", "/tmp/out.glb", glb_path="/tmp/e.glb")
        self.assertIn("no lid was generated", str(ctx.exception))

    def test_005_fcstd_with_no_step_path_at_all_raises_a_clean_error(self):
        with self.assertRaises(ValueError):
            export_enclosure("combined", "fcstd", "/tmp/out.FCStd")


class TestFreecadBridgeExportEnclosure(unittest.TestCase):
    """CTX-311.13: `export_enclosure`'s own real geometry/subprocess
    behavior -- the `freecad.export_enclosure` daemon route only ever
    mocks this function in test_daemon.py, so every real freecadcmd/
    trimesh interaction (STEP/STL compound export, native FCStd via
    `doc.saveAs`, GLB copy/merge) is verified here against the actual
    installed FreeCAD, once per class rather than once per test --
    `generate_enclosure` itself is already verified exhaustively by
    TestBoardDrivenEnclosure above; re-running it for every export
    combination here would only add real freecadcmd cold-boot cost
    without adding real coverage."""

    @classmethod
    def setUpClass(cls):
        try:
            find_freecadcmd()
        except FreeCADUnavailableError:
            raise unittest.SkipTest(
                "No local freecadcmd found. Install FreeCAD 0.20+ to run this test for real."
            )
        cls._src_tmpdir = tempfile.TemporaryDirectory()
        freecad_bridge.configure(output_dir=cls._src_tmpdir.name)
        with_lid = generate_enclosure(
            height=10, board_outline=_TEST_BOARD_OUTLINE, standoffs=[],
            fillet_radius_mm=0, lid=True, lid_thickness_mm=2.0,
        )
        # Real, confirmed behavior (CTX-311.2 Deviation 1, hit directly by
        # this fixture, not just described): `generate_enclosure`'s own
        # leak-bounding cleanup deletes the *previous* successful glb/step
        # via simple module-level `_last_glb_path`/`_last_step_path`
        # pointers, regardless of `output_dir` -- a second real call below
        # would delete `with_lid`'s own files out from under this class-
        # level fixture. Copying them to independent, untracked paths
        # first is the same real fix a durable Export action gives a user:
        # once a file exists somewhere `generate_enclosure`'s own cleanup
        # doesn't know about, it's safe from the next regeneration.
        cls.with_lid = {
            key: shutil.copy(path, os.path.join(cls._src_tmpdir.name, f"safe_{os.path.basename(path)}"))
            for key, path in with_lid.items()
        }
        cls.no_lid = generate_enclosure(
            height=10, board_outline=_TEST_BOARD_OUTLINE, standoffs=[], fillet_radius_mm=0,
        )

    @classmethod
    def tearDownClass(cls):
        freecad_bridge.configure(output_dir=None)
        cls._src_tmpdir.cleanup()

    def setUp(self):
        self._dest_tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._dest_tmpdir.cleanup()

    def _dest(self, filename):
        return os.path.join(self._dest_tmpdir.name, filename)

    def test_001_step_single_part_matches_the_original_bounding_box(self):
        """A single-part STEP export is a real read-back-and-re-export of
        the existing file, not a copy -- confirmed here by real bounding-
        box equality (via the same `get_step_bounding_box_mm` this module
        already uses elsewhere for real verification) rather than trusting
        byte-for-byte identity, which a re-export through FreeCAD's own
        STEP writer is not guaranteed to produce."""
        dest = self._dest("body.step")
        export_enclosure("body", "step", dest, step_path=self.with_lid["step_path"])

        original_bbox = get_step_bounding_box_mm(self.with_lid["step_path"])
        exported_bbox = get_step_bounding_box_mm(dest)
        self.assertEqual(original_bbox, exported_bbox)

    def test_002_step_combined_bounding_box_spans_both_body_and_lid(self):
        """Real proof both shapes are actually present in one file, not
        just the body: the combined STEP's own Z extent (FreeCAD's native
        Z-up, pre-rotation) must cover the base shell's full height plus
        the real 2.0mm lid thickness `setUpClass` configured -- a single-
        shape export could never produce this Z extent."""
        dest = self._dest("combined.step")
        export_enclosure(
            "combined", "step", dest,
            step_path=self.with_lid["step_path"], lid_step_path=self.with_lid["lid_step_path"],
        )

        combined_bbox = get_step_bounding_box_mm(dest)
        body_bbox = get_step_bounding_box_mm(self.with_lid["step_path"])
        self.assertAlmostEqual(combined_bbox["z_mm"], body_bbox["z_mm"] + 2.0, delta=0.01)

    def test_003_stl_combined_has_real_geometry_from_both_parts(self):
        """The same real "more geometry than either part alone" proof as
        test_002, checked via a real mesh face count instead of a STEP
        bounding box -- STL has no bounding-box reader in this module, so
        this exercises the actual `Part.makeCompound` -> `exportStl` path
        directly, not just its STEP sibling."""
        import trimesh

        body_dest = self._dest("body.stl")
        lid_dest = self._dest("lid.stl")
        combined_dest = self._dest("combined.stl")
        export_enclosure("body", "stl", body_dest, step_path=self.with_lid["step_path"])
        export_enclosure("lid", "stl", lid_dest, lid_step_path=self.with_lid["lid_step_path"])
        export_enclosure(
            "combined", "stl", combined_dest,
            step_path=self.with_lid["step_path"], lid_step_path=self.with_lid["lid_step_path"],
        )

        body_faces = len(trimesh.load(body_dest).faces)
        lid_faces = len(trimesh.load(lid_dest).faces)
        combined_faces = len(trimesh.load(combined_dest).faces)
        self.assertEqual(combined_faces, body_faces + lid_faces)

    def test_004_glb_single_part_is_a_real_copy_of_the_existing_file(self):
        """No subprocess, no re-export -- a real byte-for-byte copy of the
        already-correct existing `.glb` (its real materials, CTX-311.7/
        .12, untouched)."""
        import filecmp

        dest = self._dest("body.glb")
        export_enclosure("body", "glb", dest, glb_path=self.with_lid["glb_path"])

        self.assertTrue(filecmp.cmp(dest, self.with_lid["glb_path"], shallow=False))

    def test_005_glb_combined_merges_both_real_geometries_with_their_own_colors(self):
        """Real proof the merged glTF Scene actually contains the body's
        own two real materials (CTX-311.12's outer/inner split) plus the
        lid's own, not a dropped or overwritten one -- three real
        geometries, three real distinct colors."""
        import trimesh

        dest = self._dest("combined.glb")
        export_enclosure(
            "combined", "glb", dest,
            glb_path=self.with_lid["glb_path"], lid_glb_path=self.with_lid["lid_glb_path"],
        )

        scene = trimesh.load(dest)
        colors = {
            tuple(g.visual.material.baseColorFactor)[:3] for g in scene.geometry.values()
        }
        self.assertEqual(len(scene.geometry), 3)
        self.assertEqual(
            colors,
            {
                freecad_bridge._BODY_COLOR_RGB,
                freecad_bridge._BODY_INNER_COLOR_RGB,
                freecad_bridge._LID_COLOR_RGB,
            },
        )

    def test_006_fcstd_combined_reloads_with_both_real_objects(self):
        """`doc.saveAs()` had never been used anywhere in this codebase
        before CTX-311.13 -- this re-opens the real saved `.FCStd` in a
        fresh `freecadcmd` process (not just checking the file exists) to
        confirm both real objects genuinely round-trip."""
        dest = self._dest("combined.FCStd")
        export_enclosure(
            "combined", "fcstd", dest,
            step_path=self.with_lid["step_path"], lid_step_path=self.with_lid["lid_step_path"],
        )

        object_count = self._real_fcstd_object_count(dest)
        self.assertEqual(object_count, 2)

    def test_007_fcstd_ignores_parts_and_always_includes_the_lid_when_one_exists(self):
        """CTX-311.13's own Plan Drift decision: `.FCStd` is always the
        whole design, never gated by `parts` -- requesting `parts='body'`
        must still produce a real two-object document when a lid was
        actually generated."""
        dest = self._dest("body_parts_but_still_combined.FCStd")
        export_enclosure(
            "body", "fcstd", dest,
            step_path=self.with_lid["step_path"], lid_step_path=self.with_lid["lid_step_path"],
        )

        self.assertEqual(self._real_fcstd_object_count(dest), 2)

    def test_008_fcstd_with_no_lid_generated_reloads_with_one_real_object(self):
        dest = self._dest("body_only.FCStd")
        export_enclosure("combined", "fcstd", dest, step_path=self.no_lid["step_path"])

        self.assertEqual(self._real_fcstd_object_count(dest), 1)

    def test_009_lid_parts_without_a_generated_lid_raises_a_clean_error(self):
        with self.assertRaises(ValueError):
            export_enclosure(
                "lid", "step", self._dest("x.step"), step_path=self.no_lid["step_path"],
            )

    def test_010_manual_mode_solid_box_still_exports_cleanly(self):
        """The solid, cavity-free box `_export_glb`'s inner/outer split
        (CTX-311.12) has to special-case doesn't touch `export_enclosure`
        at all -- STEP/STL/GLB export of a plain manual-mode box is a
        real, ordinary single-shape path, verified here so a future
        change to the split logic can't silently break this one."""
        result = generate_enclosure(height=10, width=20, depth=15, fillet_radius_mm=0)
        try:
            dest = self._dest("manual.step")
            export_enclosure("body", "step", dest, step_path=result["step_path"])
            self.assertTrue(os.path.exists(dest))
            self.assertGreater(os.path.getsize(dest), 0)
        finally:
            for key in ("glb_path", "step_path"):
                if os.path.exists(result[key]):
                    os.remove(result[key])

    def _real_fcstd_object_count(self, fcstd_path: str) -> int:
        """Not reused by `export_enclosure` itself -- a real, separate
        `freecadcmd` read-back purely for this test file's own
        verification, the same "read an existing file back, report one
        real fact" shape as `get_step_bounding_box_mm`."""
        script_path = self._dest("_count_objects.py")
        marker = "OBJECT_COUNT:"
        with open(script_path, "w") as f:
            f.write(
                "import FreeCAD\n"
                f"doc = FreeCAD.openDocument({fcstd_path!r})\n"
                f"print({marker!r} + str(len(doc.Objects)))\n"
            )
        proc = subprocess.run(
            [find_freecadcmd(), script_path],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for line in proc.stdout.splitlines():
            if line.startswith(marker):
                return int(line[len(marker):])
        raise AssertionError(f"freecadcmd did not report an object count: {proc.stderr}")


if __name__ == '__main__':
    unittest.main()

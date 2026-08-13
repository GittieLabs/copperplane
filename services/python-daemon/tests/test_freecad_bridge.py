import os
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
    find_freecadcmd,
    generate_enclosure,
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

    def tearDown(self):
        freecad_bridge._path_override = None
        freecad_bridge._output_dir_override = None
        freecad_bridge._last_glb_path = None
        freecad_bridge._last_step_path = None

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

    def tearDown(self):
        freecad_bridge._path_override = None
        freecad_bridge._output_dir_override = None
        freecad_bridge._last_glb_path = None
        freecad_bridge._last_step_path = None

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
            # margin = clearance + wall = 2.5; outer 25x20x10; inner
            # (clearance-only margin) 21x16x10 -- a real, exact shell volume.
            expected_volume = (25 * 20 * 10) - (21 * 16 * 10)
            self.assertAlmostEqual(mesh.volume, expected_volume, delta=expected_volume * 0.01)
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
            shell_volume = (25 * 20 * 10) - (21 * 16 * 10)
            r = standoff["diameter_mm"] / 2
            import math
            standoff_volume = math.pi * (r ** 2) * standoff["height_mm"]
            self.assertAlmostEqual(
                mesh.volume, shell_volume + standoff_volume, delta=(shell_volume + standoff_volume) * 0.02,
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


if __name__ == '__main__':
    unittest.main()

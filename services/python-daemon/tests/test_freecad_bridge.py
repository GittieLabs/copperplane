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
        # The path/output-dir overrides and last-glb tracker are all
        # module-level state; make sure no test leaks one into another.
        freecad_bridge._path_override = None
        freecad_bridge._output_dir_override = None
        freecad_bridge._last_glb_path = None

    def tearDown(self):
        freecad_bridge._path_override = None
        freecad_bridge._output_dir_override = None
        freecad_bridge._last_glb_path = None

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

        glb_path = generate_enclosure(width=50, depth=30, height=20)
        try:
            self.assertTrue(os.path.exists(glb_path))
            with open(glb_path, 'rb') as f:
                header = f.read(4)
            self.assertEqual(header, b'glTF', "output should be a real glTF binary, not just a renamed STL")
        finally:
            if os.path.exists(glb_path):
                os.remove(glb_path)

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
            glb_path = generate_enclosure(width=50, depth=30, height=20)

            self.assertEqual(os.path.dirname(glb_path), output_dir)
            self.assertTrue(os.path.exists(glb_path))

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

            first_glb = generate_enclosure(width=50, depth=30, height=20)
            self.assertTrue(os.path.exists(first_glb))

            second_glb = generate_enclosure(width=60, depth=40, height=25)

            self.assertFalse(os.path.exists(first_glb), "the previous .glb should be cleaned up")
            self.assertTrue(os.path.exists(second_glb))


if __name__ == '__main__':
    unittest.main()

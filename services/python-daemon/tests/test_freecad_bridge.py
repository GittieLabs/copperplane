import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import freecad_bridge
from freecad_bridge import FreeCADBuildError, FreeCADUnavailableError, find_freecadcmd, generate_enclosure


class TestFreeCADBridge(unittest.TestCase):

    @patch('freecad_bridge.glob.glob', return_value=[])
    @patch('freecad_bridge.shutil.which', return_value=None)
    def test_001_no_executable_found_raises_clean_error(self, mock_which, mock_glob):
        """TEST-001: `find_freecadcmd` raises a clean error when no
        executable is found on PATH or any known install location."""
        with self.assertRaises(FreeCADUnavailableError) as ctx:
            find_freecadcmd()

        self.assertIn("Could not find the freecadcmd executable", str(ctx.exception))

    @patch('freecad_bridge.subprocess.run')
    @patch('freecad_bridge.find_freecadcmd', return_value='/fake/freecadcmd')
    def test_002_nonzero_exit_raises_clean_error(self, mock_find, mock_run):
        """TEST-002: A non-zero freecadcmd exit (build script failure) is
        caught and raised as a clean error, not a raw CalledProcessError."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Syntax error in script")

        with self.assertRaises(FreeCADBuildError) as ctx:
            generate_enclosure(width=50, depth=30, height=20)

        self.assertIn("exited with code 1", str(ctx.exception))
        self.assertIn("Syntax error in script", str(ctx.exception))

    @patch('freecad_bridge.subprocess.run')
    @patch('freecad_bridge.find_freecadcmd', return_value='/fake/freecadcmd')
    def test_003_timeout_raises_clean_error(self, mock_find, mock_run):
        """TEST-003: A freecadcmd subprocess that exceeds the timeout is
        raised as a clean, specific error."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='freecadcmd', timeout=30.0)

        with self.assertRaises(FreeCADBuildError) as ctx:
            generate_enclosure(width=50, depth=30, height=20, timeout_s=30.0)

        self.assertIn("did not finish within 30.0s", str(ctx.exception))

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


if __name__ == '__main__':
    unittest.main()

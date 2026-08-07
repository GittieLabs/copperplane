import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import kicad_bridge
from kicad_bridge import KiCadUnavailableError, get_kicad_version
from kipy.errors import ConnectionError as KiCadConnectionError


class TestKiCadBridge(unittest.TestCase):

    def setUp(self):
        # The connection is module-level held-open state; make sure no
        # test leaks a stale/mocked client into another test.
        kicad_bridge._client = None

    def tearDown(self):
        kicad_bridge._client = None

    @patch('kicad_bridge.KiCad')
    def test_001_connection_refused_raises_clean_error(self, mock_kicad_cls):
        """TEST-001: Connection manager raises a clean, specific error
        (not a raw kipy traceback) when KiCad isn't running."""
        mock_client = MagicMock()
        mock_client.check_version.side_effect = KiCadConnectionError("Connection refused")
        mock_kicad_cls.return_value = mock_client

        with self.assertRaises(KiCadUnavailableError) as ctx:
            get_kicad_version()

        self.assertIn("Could not connect to KiCad", str(ctx.exception))
        self.assertIsInstance(ctx.exception.__cause__, KiCadConnectionError)

    def test_002_real_kicad_version_round_trip(self):
        """TEST-002: `kicad.get_version` returns KiCad's real version
        end-to-end against a live, locally running KiCad instance.
        Skips itself (rather than failing) when no KiCad is running —
        e.g. in CI, where KiCad isn't installed at all."""
        socket_path = '/tmp/kicad/api.sock'
        if not os.path.exists(socket_path):
            self.skipTest(
                f"No live KiCad IPC socket at {socket_path}. Enable the IPC API "
                "(Preferences > Plugins) and launch KiCad to run this test for real."
            )

        result = get_kicad_version()

        self.assertIsInstance(result["full_version"], str)
        self.assertIsInstance(result["major"], int)
        self.assertGreaterEqual(result["major"], 9, "SPEC-103 requires KiCad 9+")

    @patch('kicad_bridge.KiCad')
    def test_003_broken_pipe_mid_call_resets_connection(self, mock_kicad_cls):
        """TEST-003: A connection that breaks mid-call (State Desync —
        e.g. the user closes KiCad) is caught and raised as a clean
        error, and the stale client is dropped so the next call
        reconnects from scratch instead of reusing a dead socket."""
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_client.get_version.side_effect = KiCadConnectionError("Broken pipe")
        mock_kicad_cls.return_value = mock_client

        with self.assertRaises(KiCadUnavailableError) as ctx:
            get_kicad_version()

        self.assertIn("Lost connection to KiCad mid-request", str(ctx.exception))
        self.assertIsNone(
            kicad_bridge._client,
            "the dead client must be dropped so the next call reconnects",
        )


if __name__ == '__main__':
    unittest.main()

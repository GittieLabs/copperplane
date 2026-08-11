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
        # test leaks a stale/mocked client or config override into another.
        kicad_bridge._client = None
        kicad_bridge._socket_path_override = None
        kicad_bridge._timeout_ms_override = None

    def tearDown(self):
        kicad_bridge._client = None
        kicad_bridge._socket_path_override = None
        kicad_bridge._timeout_ms_override = None

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

    @patch('kicad_bridge.KiCad')
    def test_004_configure_resets_client_and_applies_overrides(self, mock_kicad_cls):
        """TEST-004 (CTX-106.1): kicad_bridge.configure resets the held
        client, and the next connection attempt constructs KiCad with the
        configured socket_path/timeout_ms -- a live socket on a *custom*
        path isn't available to test for real on this machine, only the
        default path TEST-002 already verifies, so this is mocked at the
        KiCad constructor call itself."""
        mock_client = MagicMock()
        mock_kicad_cls.return_value = mock_client

        # Establish a held-open client under the default (no override) config.
        kicad_bridge.get_client()
        self.assertIsNotNone(kicad_bridge._client)

        kicad_bridge.configure(socket_path='/custom/kicad.sock', timeout_ms=9000)
        self.assertIsNone(kicad_bridge._client, "configure should drop the stale client immediately")

        kicad_bridge.get_client()
        mock_kicad_cls.assert_called_with(socket_path='/custom/kicad.sock', timeout_ms=9000)


_SOIC8_SCHEMA = {
    "part_number": "ATTINY85",
    "package": "SOIC-8",
    "pins": [{"number": str(i), "name": f"P{i}", "electrical_type": "passive"} for i in range(1, 9)],
    "package_dimensions": {"length_mm": 4.9, "width_mm": 3.9, "height_mm": 1.75, "pitch_mm": 1.27},
    "courtyard": {"length_mm": 5.2, "width_mm": 4.2},
}


class TestInjectComponent(unittest.TestCase):
    """Mocked orchestration coverage for kicad_bridge.inject_component
    (TEST-005 (CTX-108.1)): does the real, live-verified write path
    (see test_kicad_write.py's TestRealKicadWrite) call push_commit +
    save on success, and drop_commit -- never push_commit or save --
    on any failure. board.save() must never run in an automated test
    against a real board a developer might have open, so this is the
    only place inject_component's own control flow is exercised
    end-to-end."""

    def setUp(self):
        kicad_bridge._client = None

    def tearDown(self):
        kicad_bridge._client = None

    @patch('kicad_bridge.KiCad')
    def test_001_success_commits_and_saves(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_board = MagicMock()
        mock_client.get_board.return_value = mock_board
        mock_kicad_cls.return_value = mock_client

        commit_sentinel = object()
        mock_board.begin_commit.return_value = commit_sentinel

        result = kicad_bridge.inject_component(_SOIC8_SCHEMA, (50, 50))

        mock_board.create_items.assert_called_once()
        mock_board.push_commit.assert_called_once_with(commit_sentinel, "Add ATTINY85")
        mock_board.drop_commit.assert_not_called()
        mock_board.save.assert_called_once()
        self.assertEqual(result, {"part_number": "ATTINY85", "package": "SOIC-8", "pins": 8})

    @patch('kicad_bridge.KiCad')
    def test_002_create_items_failure_drops_the_commit_and_never_saves(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_board = MagicMock()
        mock_client.get_board.return_value = mock_board
        mock_kicad_cls.return_value = mock_client

        commit_sentinel = object()
        mock_board.begin_commit.return_value = commit_sentinel
        mock_board.create_items.side_effect = RuntimeError("KiCad rejected the item")

        with self.assertRaises(kicad_bridge.KiCadWriteError) as ctx:
            kicad_bridge.inject_component(_SOIC8_SCHEMA, (50, 50))

        self.assertIn("ATTINY85", str(ctx.exception))
        mock_board.drop_commit.assert_called_once_with(commit_sentinel)
        mock_board.push_commit.assert_not_called()
        mock_board.save.assert_not_called()

    @patch('kicad_bridge.KiCad')
    def test_003_unrecognized_package_never_touches_the_board(self, mock_kicad_cls):
        """An unsupported package must fail before begin_commit is ever
        called -- kicad_write.UnsupportedPackageError, not a half-open
        transaction against the board."""
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_board = MagicMock()
        mock_client.get_board.return_value = mock_board
        mock_kicad_cls.return_value = mock_client

        schema = dict(_SOIC8_SCHEMA, package="TQFP-32")

        with self.assertRaises(kicad_bridge.KiCadWriteError):
            kicad_bridge.inject_component(schema, (50, 50))

        mock_board.begin_commit.assert_not_called()

    @patch('kicad_bridge.KiCad')
    def test_004_save_failure_is_reported_distinctly(self, mock_kicad_cls):
        """A save failure happens *after* the commit already succeeded --
        the component exists in the live KiCad session even though the
        file wasn't persisted. Must not attempt drop_commit against an
        already-pushed commit."""
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_board = MagicMock()
        mock_client.get_board.return_value = mock_board
        mock_kicad_cls.return_value = mock_client

        mock_board.save.side_effect = RuntimeError("disk full")

        with self.assertRaises(kicad_bridge.KiCadWriteError) as ctx:
            kicad_bridge.inject_component(_SOIC8_SCHEMA, (50, 50))

        self.assertIn("could not be saved", str(ctx.exception))
        mock_board.push_commit.assert_called_once()
        mock_board.drop_commit.assert_not_called()


if __name__ == '__main__':
    unittest.main()

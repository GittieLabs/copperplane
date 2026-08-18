import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import kicad_bridge
from kicad_bridge import KiCadUnavailableError, get_kicad_version
from kipy.board_types import PadType
from kipy.errors import ApiError, ConnectionError as KiCadConnectionError
from kipy.geometry import Box2, Vector2
from kipy.util.board_layer import BoardLayer


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
        try:
            kicad_bridge.get_client()
        except KiCadUnavailableError as e:
            # A live connection attempt, not a socket-file existence check:
            # macOS doesn't reliably unlink the socket file when KiCad
            # exits, so os.path.exists() can report a stale file as if
            # KiCad were still reachable and fail this test for real
            # instead of skipping it.
            self.skipTest(
                f"No live KiCad IPC connection reachable: {e} Enable the IPC "
                "API (Preferences > Plugins) and launch KiCad to run this "
                "test for real."
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

    @patch('kicad_bridge.KiCad')
    def test_005_a_cached_client_that_fails_its_health_check_ping_is_transparently_replaced(self, mock_kicad_cls):
        """Real, live-discovered bug: the held-open connection can go
        silently stale (SPEC-103 §3's own documented state-desync risk)
        without ever raising on its own -- confirmed live in an actual
        dev session, where only a full daemon restart recovered it.
        get_client() must now validate a cached client with a real ping
        before reusing it, and transparently reconnect if that fails,
        rather than handing back a connection nothing has verified is
        still alive."""
        stale_client = MagicMock()
        stale_client.ping.side_effect = KiCadConnectionError("stale, no longer responds")
        kicad_bridge._client = stale_client

        fresh_client = MagicMock()
        mock_kicad_cls.return_value = fresh_client

        result = kicad_bridge.get_client()

        stale_client.ping.assert_called_once()
        self.assertIs(result, fresh_client, "a failed ping must trigger a real reconnect, not reuse the dead client")
        self.assertIs(kicad_bridge._client, fresh_client)

    @patch('kicad_bridge.KiCad')
    def test_006_a_cached_client_that_passes_its_health_check_ping_is_reused_not_reconnected(self, mock_kicad_cls):
        healthy_client = MagicMock()
        kicad_bridge._client = healthy_client

        result = kicad_bridge.get_client()

        healthy_client.ping.assert_called_once()
        self.assertIs(result, healthy_client)
        mock_kicad_cls.assert_not_called()


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


def _mm_box(x_mm, y_mm, w_mm, h_mm) -> Box2:
    return Box2.from_pos_size(Vector2.from_xy_mm(x_mm, y_mm), Vector2.from_xy_mm(w_mm, h_mm))


class _FakeShape:
    """A real kipy concrete shape's `bounding_box()` is a real, callable
    method (verified against a live KiCad connection -- not a property,
    despite its name) returning a self-contained Box2 value. No need to
    mock the whole shape hierarchy, just the two attributes
    get_board_outline actually reads."""

    def __init__(self, layer, bounding_box):
        self.layer = layer
        self._bounding_box = bounding_box

    def bounding_box(self):
        return self._bounding_box


class TestListOpenBoards(unittest.TestCase):
    """SPEC-309/CTX-309.3: the PCB-path auto-resolution DRC's route
    relies on. Renamed from the original CTX-309.1 get_open_board_path
    (single, silently-narrowed result) to a real list -- confirmed live
    against a real running KiCad 10.0.3 instance during CTX-309.3's own
    investigation that the zero-open-boards case is a real ApiError, not
    an empty list, the way SPEC-309's original research assumed."""

    def setUp(self):
        kicad_bridge._client = None

    def tearDown(self):
        kicad_bridge._client = None

    @patch('kicad_bridge.KiCad')
    def test_001_resolves_project_path_plus_board_filename(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.board_filename = "Arduino_Pro_Mini.kicad_pcb"
        mock_doc.project.path = "/Users/dev/boards/arduino"
        mock_client.get_open_documents.return_value = [mock_doc]
        mock_kicad_cls.return_value = mock_client

        paths = kicad_bridge.list_open_boards()

        self.assertEqual(paths, [os.path.join("/Users/dev/boards/arduino", "Arduino_Pro_Mini.kicad_pcb")])

    @patch('kicad_bridge.KiCad')
    def test_002_nothing_open_returns_an_empty_list_not_an_error(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_client.get_open_documents.return_value = []
        mock_kicad_cls.return_value = mock_client

        self.assertEqual(kicad_bridge.list_open_boards(), [])

    @patch('kicad_bridge.KiCad')
    def test_003_a_broken_connection_mid_call_resets_and_raises_clean(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_client.get_open_documents.side_effect = KiCadConnectionError("gone")
        mock_kicad_cls.return_value = mock_client
        kicad_bridge._client = mock_client

        with self.assertRaises(KiCadUnavailableError):
            kicad_bridge.list_open_boards()

        self.assertIsNone(kicad_bridge._client)

    @patch('kicad_bridge.KiCad')
    def test_004_no_handler_available_api_error_is_treated_as_nothing_open(self, mock_kicad_cls):
        """CTX-309.3's own real, live-discovered finding: when no PCB
        Editor window is open at all, get_open_documents raises a real
        ApiError containing "no handler available" -- a normal, expected
        "nothing open" state, not a connection failure. Must NOT reset
        the connection or raise KiCadUnavailableError."""
        mock_client = MagicMock()
        mock_client.get_open_documents.side_effect = ApiError(
            "KiCad returned error: no handler available for request of type "
            "kiapi.common.commands.GetOpenDocuments"
        )
        mock_kicad_cls.return_value = mock_client
        kicad_bridge._client = mock_client

        self.assertEqual(kicad_bridge.list_open_boards(), [])
        self.assertIs(kicad_bridge._client, mock_client, "a real 'nothing open' state must not reset the connection")

    @patch('kicad_bridge.KiCad')
    def test_005_a_different_api_error_still_resets_and_raises_clean(self, mock_kicad_cls):
        """Only the specific "no handler available" ApiError is treated
        as "nothing open" -- any other real ApiError is still a genuine
        failure."""
        mock_client = MagicMock()
        mock_client.get_open_documents.side_effect = ApiError("KiCad returned error: something else entirely")
        mock_kicad_cls.return_value = mock_client
        kicad_bridge._client = mock_client

        with self.assertRaises(KiCadUnavailableError):
            kicad_bridge.list_open_boards()

        self.assertIsNone(kicad_bridge._client)

    @patch('kicad_bridge.KiCad')
    def test_006_multiple_open_boards_are_all_returned_not_narrowed_to_one(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_doc_a = MagicMock()
        mock_doc_a.board_filename = "board_a.kicad_pcb"
        mock_doc_a.project.path = "/Users/dev/boards/a"
        mock_doc_b = MagicMock()
        mock_doc_b.board_filename = "board_b.kicad_pcb"
        mock_doc_b.project.path = "/Users/dev/boards/b"
        mock_client.get_open_documents.return_value = [mock_doc_a, mock_doc_b]
        mock_kicad_cls.return_value = mock_client

        paths = kicad_bridge.list_open_boards()

        self.assertEqual(paths, [
            os.path.join("/Users/dev/boards/a", "board_a.kicad_pcb"),
            os.path.join("/Users/dev/boards/b", "board_b.kicad_pcb"),
        ])

    def test_007_real_round_trip_against_a_live_kicad_instance(self):
        """Skips itself cleanly when no live KiCad is running, same
        convention as test_002_real_kicad_version_round_trip above."""
        try:
            kicad_bridge.get_client()
        except KiCadUnavailableError as e:
            # Same real-connection-attempt reasoning as
            # test_002_real_kicad_version_round_trip above: a stale
            # leftover socket file must not be mistaken for a live KiCad.
            self.skipTest(
                f"No live KiCad IPC connection reachable: {e} Enable the IPC "
                "API (Preferences > Plugins) and launch KiCad to run this "
                "test for real."
            )

        paths = kicad_bridge.list_open_boards()

        # An empty list (nothing open, or the real "no handler available"
        # state) or a list of real, well-formed .kicad_pcb paths are both
        # legitimate real outcomes -- this test only proves the real IPC
        # call itself succeeds without raising, not that a board happens
        # to be open on whatever machine runs this.
        for path in paths:
            self.assertTrue(path.endswith(".kicad_pcb"))


class TestListProjectSchematics(unittest.TestCase):
    """Real user feedback: why can't Schematic checking list candidates
    the way Board checking does? KiCad's IPC has no handler for listing
    open schematics at all, confirmed live -- so this derives each open
    board's own project's root schematic path instead, keeping only
    ones that actually exist on disk."""

    def setUp(self):
        kicad_bridge._client = None

    def tearDown(self):
        kicad_bridge._client = None

    @patch('kicad_bridge.os.path.exists')
    @patch('kicad_bridge.KiCad')
    def test_001_derives_the_schematic_path_from_the_open_boards_own_project_name(self, mock_kicad_cls, mock_exists):
        mock_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.board_filename = "weirdly_renamed_board.kicad_pcb"
        mock_doc.project.path = "/Users/dev/boards/arduino"
        mock_doc.project.name = "Arduino_Pro_Mini"
        mock_client.get_open_documents.return_value = [mock_doc]
        mock_kicad_cls.return_value = mock_client
        mock_exists.return_value = True

        paths = kicad_bridge.list_project_schematics()

        self.assertEqual(paths, [os.path.join("/Users/dev/boards/arduino", "Arduino_Pro_Mini.kicad_sch")])

    @patch('kicad_bridge.os.path.exists')
    @patch('kicad_bridge.KiCad')
    def test_002_a_derived_path_that_does_not_exist_on_disk_is_never_returned(self, mock_kicad_cls, mock_exists):
        mock_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.board_filename = "board.kicad_pcb"
        mock_doc.project.path = "/Users/dev/boards/orphan"
        mock_doc.project.name = "orphan"
        mock_client.get_open_documents.return_value = [mock_doc]
        mock_kicad_cls.return_value = mock_client
        mock_exists.return_value = False

        self.assertEqual(kicad_bridge.list_project_schematics(), [])

    @patch('kicad_bridge.os.path.exists')
    @patch('kicad_bridge.KiCad')
    def test_003_two_open_boards_from_the_same_project_dedupe_to_one_schematic(self, mock_kicad_cls, mock_exists):
        mock_client = MagicMock()
        mock_doc_a = MagicMock()
        mock_doc_a.board_filename = "top.kicad_pcb"
        mock_doc_a.project.path = "/Users/dev/boards/multi"
        mock_doc_a.project.name = "multi"
        mock_doc_b = MagicMock()
        mock_doc_b.board_filename = "bottom.kicad_pcb"
        mock_doc_b.project.path = "/Users/dev/boards/multi"
        mock_doc_b.project.name = "multi"
        mock_client.get_open_documents.return_value = [mock_doc_a, mock_doc_b]
        mock_kicad_cls.return_value = mock_client
        mock_exists.return_value = True

        self.assertEqual(kicad_bridge.list_project_schematics(), [os.path.join("/Users/dev/boards/multi", "multi.kicad_sch")])

    @patch('kicad_bridge.KiCad')
    def test_004_nothing_open_returns_an_empty_list_not_an_error(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_client.get_open_documents.return_value = []
        mock_kicad_cls.return_value = mock_client

        self.assertEqual(kicad_bridge.list_project_schematics(), [])

    @patch('kicad_bridge.KiCad')
    def test_005_no_handler_available_api_error_is_treated_as_nothing_derivable(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_client.get_open_documents.side_effect = ApiError(
            "KiCad returned error: no handler available for request of type "
            "kiapi.common.commands.GetOpenDocuments"
        )
        mock_kicad_cls.return_value = mock_client
        kicad_bridge._client = mock_client

        self.assertEqual(kicad_bridge.list_project_schematics(), [])
        self.assertIs(kicad_bridge._client, mock_client, "a real 'nothing open' state must not reset the connection")

    @patch('kicad_bridge.KiCad')
    def test_006_a_broken_connection_mid_call_resets_and_raises_clean(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_client.get_open_documents.side_effect = KiCadConnectionError("gone")
        mock_kicad_cls.return_value = mock_client
        kicad_bridge._client = mock_client

        with self.assertRaises(KiCadUnavailableError):
            kicad_bridge.list_project_schematics()

        self.assertIsNone(kicad_bridge._client)

    def test_007_real_round_trip_against_a_live_kicad_instance(self):
        """Skips itself cleanly when no live KiCad is running, same
        convention as list_open_boards's own real round trip."""
        socket_path = '/tmp/kicad/api.sock'
        if not os.path.exists(socket_path):
            self.skipTest(
                f"No live KiCad IPC socket at {socket_path}. Enable the IPC API "
                "(Preferences > Plugins) and launch KiCad to run this test for real."
            )

        paths = kicad_bridge.list_project_schematics()

        for path in paths:
            self.assertTrue(path.endswith(".kicad_sch"))
            self.assertTrue(os.path.exists(path), "must never return a derived path that doesn't actually exist")


class TestGetBoardOutline(unittest.TestCase):

    def setUp(self):
        kicad_bridge._client = None

    def tearDown(self):
        kicad_bridge._client = None

    @patch('kicad_bridge.KiCad')
    def test_001_unions_every_edge_cuts_shape_into_one_real_bounding_box(self, mock_kicad_cls):
        """TEST-001 (CTX-109.1): a bounding box is the real, sufficient
        outline data for SPEC-109's fixed-rectangular-enclosure scope --
        non-Edge.Cuts shapes (e.g. silkscreen) must not affect it."""
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_board = MagicMock()
        mock_client.get_board.return_value = mock_board
        mock_kicad_cls.return_value = mock_client

        mock_board.get_shapes.return_value = [
            _FakeShape(BoardLayer.BL_Edge_Cuts, _mm_box(0, 0, 10, 10)),
            _FakeShape(BoardLayer.BL_Edge_Cuts, _mm_box(5, 5, 10, 10)),
            _FakeShape(BoardLayer.BL_F_SilkS, _mm_box(-100, -100, 1, 1)),
        ]

        outline = kicad_bridge.get_board_outline()

        self.assertAlmostEqual(outline["x_mm"], 0)
        self.assertAlmostEqual(outline["y_mm"], 0)
        self.assertAlmostEqual(outline["width_mm"], 15)
        self.assertAlmostEqual(outline["height_mm"], 15)

    @patch('kicad_bridge.KiCad')
    def test_002_no_edge_cuts_shapes_raises_board_outline_missing_error(self, mock_kicad_cls):
        """TEST-002 (CTX-109.1): SPEC-109 §3 -- a board with no drawn
        Edge.Cuts must fail clearly, never guess a silent zero-size
        outline."""
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_board = MagicMock()
        mock_client.get_board.return_value = mock_board
        mock_kicad_cls.return_value = mock_client

        mock_board.get_shapes.return_value = [_FakeShape(BoardLayer.BL_F_SilkS, _mm_box(0, 0, 1, 1))]

        with self.assertRaises(kicad_bridge.BoardOutlineMissingError):
            kicad_bridge.get_board_outline()


class _FakePad:
    def __init__(self, pad_type, drill_diameter_mm):
        self.pad_type = pad_type
        self.padstack = MagicMock()
        self.padstack.drill.diameter = Vector2.from_xy_mm(drill_diameter_mm, drill_diameter_mm)


class _FakeFootprintInstance:
    """Mirrors just the real attribute chain get_mounting_holes reads: a
    FootprintInstance's own absolute .position, its .definition.id.library
    (the LibraryIdentifier), and its .definition.pads (the template pads,
    each carrying a real drill diameter regardless of instance
    placement)."""

    def __init__(self, x_mm, y_mm, library, reference, pads):
        self.position = Vector2.from_xy_mm(x_mm, y_mm)
        self.definition = MagicMock()
        self.definition.id.library = library
        self.definition.pads = pads
        self.reference_field = MagicMock()
        self.reference_field.text.value = reference


class TestGetMountingHoles(unittest.TestCase):

    def setUp(self):
        kicad_bridge._client = None

    def tearDown(self):
        kicad_bridge._client = None

    @patch('kicad_bridge.KiCad')
    def test_001_a_mountinghole_library_footprint_is_recognized(self, mock_kicad_cls):
        """TEST-003 (CTX-109.1): a recognized mounting hole reports its
        real absolute position and drill diameter in mm."""
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_board = MagicMock()
        mock_client.get_board.return_value = mock_board
        mock_kicad_cls.return_value = mock_client

        mock_board.get_footprints.return_value = [
            _FakeFootprintInstance(10, 20, "MountingHole", "H1", [_FakePad(PadType.PT_NPTH, 3.2)]),
        ]

        holes = kicad_bridge.get_mounting_holes()

        self.assertEqual(len(holes), 1)
        self.assertAlmostEqual(holes[0]["x_mm"], 10)
        self.assertAlmostEqual(holes[0]["y_mm"], 20)
        self.assertAlmostEqual(holes[0]["diameter_mm"], 3.2)
        self.assertTrue(holes[0]["recognized"])

    @patch('kicad_bridge.KiCad')
    def test_002_the_h_digits_reference_convention_is_also_recognized(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_board = MagicMock()
        mock_client.get_board.return_value = mock_board
        mock_kicad_cls.return_value = mock_client

        mock_board.get_footprints.return_value = [
            _FakeFootprintInstance(0, 0, "Some_Custom_Lib", "H3", [_FakePad(PadType.PT_NPTH, 3.2)]),
        ]

        holes = kicad_bridge.get_mounting_holes()

        self.assertTrue(holes[0]["recognized"])

    @patch('kicad_bridge.KiCad')
    def test_003_an_npth_on_an_unrecognized_footprint_is_still_returned_but_flagged(self, mock_kicad_cls):
        """TEST-003 (CTX-109.1): SPEC-109 §3 -- ambiguous data stays
        inspectable, the calling route decides whether to fail closed."""
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_board = MagicMock()
        mock_client.get_board.return_value = mock_board
        mock_kicad_cls.return_value = mock_client

        mock_board.get_footprints.return_value = [
            _FakeFootprintInstance(5, 5, "Some_Custom_Lib", "TP1", [_FakePad(PadType.PT_NPTH, 1.0)]),
        ]

        holes = kicad_bridge.get_mounting_holes()

        self.assertEqual(len(holes), 1)
        self.assertFalse(holes[0]["recognized"])

    @patch('kicad_bridge.KiCad')
    def test_004_plated_through_hole_pads_are_never_returned(self, mock_kicad_cls):
        mock_client = MagicMock()
        mock_client.check_version.return_value = True
        mock_board = MagicMock()
        mock_client.get_board.return_value = mock_board
        mock_kicad_cls.return_value = mock_client

        mock_board.get_footprints.return_value = [
            _FakeFootprintInstance(0, 0, "MountingHole", "H1", [_FakePad(PadType.PT_PTH, 1.0)]),
        ]

        holes = kicad_bridge.get_mounting_holes()

        self.assertEqual(holes, [])


if __name__ == '__main__':
    unittest.main()

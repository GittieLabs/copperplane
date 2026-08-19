import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import library_store as store


_VALID_PROVENANCE = {
    field: {"source": "datasheet_pdf", "model": None, "confidence": 1.0}
    for field in store.PART_PROVENANCE_REQUIRED_FIELDS
}


class LibraryStoreTestCase(unittest.TestCase):
    """Every test gets a real, isolated temp directory -- configure() is
    called directly, the same way _apply_env_config() calls it in
    production, per CLAUDE.md's 'verify against the real thing' norm:
    this is real file I/O against a real filesystem, not mocked."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        store.configure(storage_root=self._tmpdir.name)

    def tearDown(self):
        store.configure(storage_root=None)
        self._tmpdir.cleanup()


class TestStorageRootUnconfigured(unittest.TestCase):

    def test_001_reading_before_configure_raises_a_clean_error(self):
        store.configure(storage_root=None)
        with self.assertRaises(store.StorageRootUnconfiguredError):
            store.list_parts()


class TestCurrentStorageRoot(unittest.TestCase):
    """SPEC-110: unlike _root(), current_storage_root() never raises --
    daemon.get_capabilities calls it to report the real path (or None)
    without needing to catch StorageRootUnconfiguredError itself."""

    def test_001_returns_none_before_configure(self):
        store.configure(storage_root=None)
        self.assertIsNone(store.current_storage_root())

    def test_002_returns_the_real_configured_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store.configure(storage_root=tmpdir)
            try:
                self.assertEqual(store.current_storage_root(), tmpdir)
            finally:
                store.configure(storage_root=None)


class TestPart(LibraryStoreTestCase):

    def test_001_save_and_load_round_trip(self):
        part = {
            "part_id": "ATtiny85",
            "manufacturer": "Microchip",
            "package": "SOIC-8",
            "pins": [],
            "datasheet_url": "https://example.com/ATtiny85.pdf",
            "footprint_id": None,
            "provenance": _VALID_PROVENANCE,
        }
        saved = store.save_part(part)
        self.assertEqual(saved["schema_version"], 1)

        loaded = store.load_part("ATtiny85")
        self.assertEqual(loaded["manufacturer"], "Microchip")
        self.assertIsNone(loaded["footprint_id"])

    def test_002_missing_part_id_is_rejected(self):
        with self.assertRaises(store.SchemaValidationError):
            store.save_part({"manufacturer": "Microchip", "provenance": _VALID_PROVENANCE})

    def test_003_missing_provenance_entirely_is_rejected(self):
        with self.assertRaises(store.SchemaValidationError) as ctx:
            store.save_part({"part_id": "X", "manufacturer": "Microchip"})
        self.assertIn("provenance", str(ctx.exception))

    def test_004_provenance_missing_a_required_field_is_rejected(self):
        """TEST: SPEC-300 §2.2's 'must reject', not merely document --
        every required field needs its own provenance entry, not just
        one blanket provenance blob for the whole record."""
        incomplete = dict(_VALID_PROVENANCE)
        del incomplete["package"]
        with self.assertRaises(store.SchemaValidationError) as ctx:
            store.save_part({
                "part_id": "X",
                "manufacturer": "Microchip",
                "package": "SOIC-8",
                "pins": [],
                "datasheet_url": "https://example.com/x.pdf",
                "provenance": incomplete,
            })
        self.assertIn("package", str(ctx.exception))

    def test_005_list_parts_returns_every_saved_part_id_sorted(self):
        for part_id in ("Zeta", "Alpha", "Mid"):
            store.save_part({
                "part_id": part_id,
                "manufacturer": "Test",
                "package": "SOIC-8",
                "pins": [],
                "datasheet_url": "https://example.com/x.pdf",
                "provenance": _VALID_PROVENANCE,
            })

        self.assertEqual(store.list_parts(), ["Alpha", "Mid", "Zeta"])

    def test_006_a_part_with_no_footprint_yet_is_still_valid(self):
        """TEST: SPEC-300 §2.1 -- a Part with pins and a datasheet is
        useful before any Footprint exists."""
        store.save_part({
            "part_id": "NoFootprintYet",
            "manufacturer": "Test",
            "package": "SOIC-8",
            "pins": [{"number": "1", "name": "VCC"}],
            "datasheet_url": "https://example.com/x.pdf",
            "footprint_id": None,
            "provenance": _VALID_PROVENANCE,
        })
        loaded = store.load_part("NoFootprintYet")
        self.assertIsNone(loaded["footprint_id"])


class TestSymbolAndFootprint(LibraryStoreTestCase):

    def test_001_save_and_load_symbol(self):
        store.save_symbol({"symbol_id": "ATtiny85-sym", "pins": []})
        loaded = store.load_symbol("ATtiny85-sym")
        self.assertEqual(loaded["symbol_id"], "ATtiny85-sym")

    def test_002_missing_symbol_id_is_rejected(self):
        with self.assertRaises(store.SchemaValidationError):
            store.save_symbol({"pins": []})

    def test_003_save_and_load_footprint(self):
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})
        loaded = store.load_footprint("SOIC-8")
        self.assertEqual(loaded["footprint_id"], "SOIC-8")

    def test_004_missing_footprint_id_is_rejected(self):
        with self.assertRaises(store.SchemaValidationError):
            store.save_footprint({"pads": []})

    def test_005_one_footprint_record_is_not_duplicated_per_part(self):
        """TEST: SPEC-300 §2.1's explicit cardinality call -- SOIC-8 is
        one Footprint record regardless of how many Parts reference it."""
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})
        store.save_part({
            "part_id": "PartA", "manufacturer": "X", "package": "SOIC-8", "pins": [],
            "datasheet_url": "https://example.com/a.pdf", "footprint_id": "SOIC-8",
            "provenance": _VALID_PROVENANCE,
        })
        store.save_part({
            "part_id": "PartB", "manufacturer": "X", "package": "SOIC-8", "pins": [],
            "datasheet_url": "https://example.com/b.pdf", "footprint_id": "SOIC-8",
            "provenance": _VALID_PROVENANCE,
        })

        footprints_dir = os.path.join(self._tmpdir.name, "library", "footprints")
        self.assertEqual(os.listdir(footprints_dir), ["SOIC-8.json"])
        self.assertEqual(store.load_part("PartA")["footprint_id"], "SOIC-8")
        self.assertEqual(store.load_part("PartB")["footprint_id"], "SOIC-8")

    def test_006_list_footprints_returns_every_saved_id_sorted(self):
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})
        store.save_footprint({"footprint_id": "DIP-8", "pads": []})

        self.assertEqual(store.list_footprints(), ["DIP-8", "SOIC-8"])

    def test_007_search_footprints_matches_on_footprint_name(self):
        store.save_footprint({
            "footprint_id": "MyPCBLibs__MP1584EN_5V_Module",
            "library": "MyPCBLibs", "footprint_name": "MP1584EN_5V_Module",
        })
        store.save_footprint({"footprint_id": "DIP-8", "pads": []})

        results = store.search_footprints("MP1584")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["footprint_id"], "MyPCBLibs__MP1584EN_5V_Module")

    def test_008_search_footprints_falls_back_to_footprint_id_when_name_is_missing(self):
        """TEST-002: a real, already-possible shape -- this file's own
        test_003/test_005 above save footprints with no footprint_name
        at all. Search must still find them, by footprint_id."""
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})

        results = store.search_footprints("SOIC")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["footprint_id"], "SOIC-8")

    def test_009_search_footprints_no_match_returns_an_empty_list(self):
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})

        self.assertEqual(store.search_footprints("definitely_not_present"), [])


class TestProject(LibraryStoreTestCase):

    def test_001_save_and_load_round_trip(self):
        store.save_project({"name": "weather-pcb", "component_refs": []})
        loaded = store.load_project("weather-pcb")
        self.assertEqual(loaded["name"], "weather-pcb")
        self.assertEqual(loaded["schema_version"], 1)

    def test_002_missing_name_is_rejected(self):
        with self.assertRaises(store.SchemaValidationError):
            store.save_project({"component_refs": []})

    def test_003_list_projects_returns_only_real_projects_sorted(self):
        store.save_project({"name": "weather-pcb"})
        store.save_project({"name": "doorbell"})

        self.assertEqual(store.list_projects(), ["doorbell", "weather-pcb"])

    def test_004_renaming_the_folder_on_disk_does_not_leave_a_stale_name(self):
        """CTX-110.1/task #53: the folder name is the real identity (per
        list_projects()); project.json's own `name` field must never be
        allowed to silently disagree with it after a user renames the
        folder outside the app."""
        store.save_project({"name": "weather-pcb", "component_refs": []})
        old_dir = store._project_dir("weather-pcb")
        new_dir = os.path.join(os.path.dirname(old_dir), "weather-station")
        os.rename(old_dir, new_dir)

        self.assertEqual(store.list_projects(), ["weather-station"])
        loaded = store.load_project("weather-station")
        self.assertEqual(loaded["name"], "weather-station")
        self.assertEqual(loaded["component_refs"], [])


class TestProjectDirectoryLink(LibraryStoreTestCase):
    """CTX-312.1: SPEC-304 §2.1 already described a Project as holding "a
    link to a KiCad project directory on disk" -- these tests cover the
    real directory-aware routing that finally builds it, and the
    guarantee that an unlinked project's behavior is untouched."""

    def setUp(self):
        super().setUp()
        self._real_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._real_dir.cleanup()
        super().tearDown()

    def test_001_a_directory_linked_project_writes_its_real_manifest_there(self):
        store.save_project({
            "name": "weather-pcb", "directory": self._real_dir.name, "wall_thickness_mm": 2,
        })

        state_path = os.path.join(
            self._real_dir.name, store._PROJECT_STATE_SUBDIR, "project.json",
        )
        self.assertTrue(os.path.isfile(state_path))

    def test_002_a_directory_linked_project_round_trips_through_the_real_directory(self):
        store.save_project({
            "name": "weather-pcb", "directory": self._real_dir.name, "wall_thickness_mm": 2,
        })

        loaded = store.load_project("weather-pcb")

        self.assertEqual(loaded["wall_thickness_mm"], 2)
        self.assertEqual(loaded["directory"], self._real_dir.name)

    def test_003_an_unlinked_project_still_behaves_exactly_as_before_ctx_312_1(self):
        store.save_project({"name": "weather-pcb", "component_refs": []})

        loaded = store.load_project("weather-pcb")

        self.assertEqual(loaded, {"name": "weather-pcb", "schema_version": 1, "component_refs": []})
        self.assertNotIn("directory", loaded)

    def test_004_a_moved_or_deleted_linked_directory_raises_a_clean_error_not_a_bare_one(self):
        store.save_project({"name": "weather-pcb", "directory": self._real_dir.name})
        self._real_dir.cleanup()

        with self.assertRaises(store.ProjectDirectoryMissingError) as ctx:
            store.load_project("weather-pcb")
        self.assertIn("weather-pcb", str(ctx.exception))
        self.assertIn(self._real_dir.name, str(ctx.exception))

    def test_005_project_directory_returns_the_real_link_once_set(self):
        store.save_project({"name": "weather-pcb", "directory": self._real_dir.name})

        self.assertEqual(store.project_directory("weather-pcb"), self._real_dir.name)

    def test_006_project_directory_falls_back_to_storage_root_when_unlinked(self):
        store.save_project({"name": "weather-pcb"})

        self.assertEqual(store.project_directory("weather-pcb"), store._project_dir("weather-pcb"))

    def test_007_list_projects_still_finds_a_directory_linked_project(self):
        store.save_project({"name": "weather-pcb", "directory": self._real_dir.name})

        self.assertEqual(store.list_projects(), ["weather-pcb"])


class TestOpenProjectFromDirectory(LibraryStoreTestCase):
    """CTX-312.3: the real reverse of TestProjectDirectoryLink above --
    given a real folder (as if copied from another machine), restores it
    as a known project on this one. The actual payoff of CTX-312.1's own
    portability work, and the real backend for the native menu's own
    "Open Project…" action."""

    def setUp(self):
        super().setUp()
        self._real_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._real_dir.cleanup()
        super().tearDown()

    def test_001_a_real_linked_folder_is_restored_as_a_known_project(self):
        # Simulates a folder that already carries real project state --
        # e.g. handed over from another machine -- written directly, not
        # via this test's own storage-root-configured save_project (that
        # would already register the pointer, defeating the point of
        # this test).
        state_dir = os.path.join(self._real_dir.name, store._PROJECT_STATE_SUBDIR)
        os.makedirs(state_dir)
        with open(os.path.join(state_dir, "project.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "weather-pcb", "wall_thickness_mm": 2}, f)

        result = store.open_project_from_directory(self._real_dir.name)

        self.assertEqual(result["name"], "weather-pcb")
        self.assertEqual(result["wall_thickness_mm"], 2)
        self.assertEqual(result["directory"], self._real_dir.name)

    def test_002_restoring_a_project_makes_it_discoverable_via_list_projects(self):
        state_dir = os.path.join(self._real_dir.name, store._PROJECT_STATE_SUBDIR)
        os.makedirs(state_dir)
        with open(os.path.join(state_dir, "project.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "weather-pcb"}, f)

        store.open_project_from_directory(self._real_dir.name)

        self.assertEqual(store.list_projects(), ["weather-pcb"])

    def test_003_a_folder_with_no_real_state_file_raises_a_clean_error(self):
        with self.assertRaises(store.ProjectNotLinkedError) as ctx:
            store.open_project_from_directory(self._real_dir.name)
        self.assertIn(self._real_dir.name, str(ctx.exception))

    def test_004_never_silently_creates_a_new_project_from_the_folder_name(self):
        """The real, deliberate design decision named in this function's
        own docstring: no state file means a clean error, not a guessed
        new project -- avoids a real name-collision risk against an
        existing, unrelated storage_root/projects/<basename>/."""
        with self.assertRaises(store.ProjectNotLinkedError):
            store.open_project_from_directory(self._real_dir.name)

        self.assertEqual(store.list_projects(), [])


class TestArtifact(LibraryStoreTestCase):

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})

    def test_001_save_and_load_a_non_enclosure_artifact(self):
        store.save_artifact("weather-pcb", {"artifact_id": "report-1", "kind": "advisor_report"})
        loaded = store.load_artifact("weather-pcb", "report-1")
        self.assertEqual(loaded["kind"], "advisor_report")

    def test_002_enclosure_artifact_without_board_revision_is_rejected(self):
        """TEST: the one real gap the SPEC-304 ID-collision resolution
        carried forward (ROADMAP.md §3.3) -- enforced, not just named."""
        with self.assertRaises(store.SchemaValidationError) as ctx:
            store.save_artifact("weather-pcb", {"artifact_id": "enc-1", "kind": "enclosure"})
        self.assertIn("board_revision", str(ctx.exception))

    def test_003_enclosure_artifact_with_board_revision_succeeds(self):
        store.save_artifact(
            "weather-pcb",
            {"artifact_id": "enc-1", "kind": "enclosure", "board_revision": "a1b2c3d"},
        )
        loaded = store.load_artifact("weather-pcb", "enc-1")
        self.assertEqual(loaded["board_revision"], "a1b2c3d")

    def test_004_list_artifacts_returns_every_saved_artifact_id_sorted(self):
        store.save_artifact("weather-pcb", {"artifact_id": "b", "kind": "advisor_report"})
        store.save_artifact("weather-pcb", {"artifact_id": "a", "kind": "advisor_report"})

        self.assertEqual(store.list_artifacts("weather-pcb"), ["a", "b"])


class TestConversation(LibraryStoreTestCase):

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})

    def test_001_load_conversation_is_empty_before_any_turn_is_appended(self):
        self.assertEqual(store.load_conversation("weather-pcb"), [])

    def test_002_append_and_load_round_trip_in_order(self):
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "hello"})
        store.append_conversation_turn("weather-pcb", {"role": "assistant", "content": "hi"})

        turns = store.load_conversation("weather-pcb")
        self.assertEqual([t["role"] for t in turns], ["user", "assistant"])

    def test_003_conversation_is_append_only_not_rewritten(self):
        """TEST: SPEC-300 §2.1 -- a JSONL file, not one record rewritten
        on every turn. Confirmed by checking the file grows one line at a
        time rather than being replaced."""
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "one"})
        path = store._conversation_path("weather-pcb")
        with open(path) as f:
            after_first = f.read()

        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "two"})
        with open(path) as f:
            after_second = f.read()

        self.assertTrue(after_second.startswith(after_first))


class _OneShotServer:
    """A real, local HTTP server for cache_datasheet's tests -- a genuine
    socket round trip and a genuine urllib fetch, per CLAUDE.md's 'verify
    against the real thing' norm, without depending on outside internet
    access for a repo test."""

    def __init__(self, status: int, body: bytes, content_type: str = "application/pdf"):
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}/datasheet.pdf"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()


class _StallingServer:
    """Accepts the connection and sends headers, then blocks forever
    before writing any body -- reproduces the real bug found by real
    network testing: a timeout that happens during `response.read()`
    (the connection succeeded; the body never arrives) raises a bare
    TimeoutError, not urllib.error.URLError, so a handler that only
    catches URLError lets it escape uncaught."""

    def __init__(self):
        release = threading.Event()
        self._release = release

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.end_headers()
                self.wfile.flush()
                release.wait(timeout=10)

            def log_message(self, *args):
                pass

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}/datasheet.pdf"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self._release.set()
        self._server.shutdown()
        self._server.server_close()


class TestCacheDatasheet(LibraryStoreTestCase):

    def test_001_a_successful_fetch_writes_the_real_bytes_and_returns_the_real_path(self):
        server = _OneShotServer(200, b"%PDF-1.4 fake datasheet bytes")
        try:
            path = store.cache_datasheet("ATtiny85", server.url)
        finally:
            server.stop()

        self.assertTrue(path.endswith(os.path.join("library", "datasheets", "ATtiny85.pdf")))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"%PDF-1.4 fake datasheet bytes")

    def test_002_a_non_200_response_raises_and_writes_nothing(self):
        server = _OneShotServer(404, b"not found")
        try:
            with self.assertRaises(store.DatasheetFetchError):
                store.cache_datasheet("ATtiny85", server.url)
        finally:
            server.stop()

        self.assertFalse(os.path.exists(os.path.join(store._datasheets_dir(), "ATtiny85.pdf")))

    def test_003_an_unreachable_host_raises_a_clean_error(self):
        with self.assertRaises(store.DatasheetFetchError):
            store.cache_datasheet("ATtiny85", "http://127.0.0.1:1/nope.pdf")

    def test_004_a_part_number_with_a_path_separator_is_rejected_before_any_fetch(self):
        with self.assertRaises(store.DatasheetFetchError):
            store.cache_datasheet("../../etc/passwd", "http://127.0.0.1:1/nope.pdf")

    def test_005_a_real_https_fetch_passes_real_tls_certificate_verification(self):
        """Real end-to-end verification of the Components tab found this:
        this Python build's own default SSL context fails closed with
        CERTIFICATE_VERIFY_FAILED on every real HTTPS host, because its
        baked-in default cert path is a path from the build's own CI
        runner, not a real path on any actual machine. The _OneShotServer
        tests above are plain HTTP and can never catch this -- only a
        real HTTPS fetch exercises certificate verification at all. Skips
        cleanly on a genuine network-level failure (no internet access),
        but a certificate error is a real regression, not something to
        skip past."""
        try:
            path = store.cache_datasheet("test-tls-part", "https://www.python.org/robots.txt")
        except store.DatasheetFetchError as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                raise
            self.skipTest(f"No real network access for this test: {e}")

        with open(path, "rb") as f:
            self.assertTrue(f.read())

    def test_006_a_stalled_read_after_a_successful_connection_raises_a_clean_error(self):
        """The real bug this test exists to catch: found running a real
        search+cache loop against real search-agent output where one
        candidate's URL connected fine but stalled reading the body.
        Before this fix, that raised a bare TimeoutError that escaped
        cache_datasheet entirely -- crashing the route instead of
        surfacing a clean DatasheetFetchError."""
        original_timeout = store._DATASHEET_FETCH_TIMEOUT_S
        store._DATASHEET_FETCH_TIMEOUT_S = 0.3
        server = _StallingServer()
        try:
            with self.assertRaises(store.DatasheetFetchError):
                store.cache_datasheet("ATtiny85", server.url)
        finally:
            store._DATASHEET_FETCH_TIMEOUT_S = original_timeout
            server.stop()


def _find_kicad_cli():
    """Same shutil.which-first, real-known-path-fallback convention
    freecad_bridge.py already uses for freecadcmd. Test-only -- locating
    kicad-cli robustly for *production* use is SPEC-309's own named open
    question, not this context's job to solve."""
    on_path = shutil.which("kicad-cli")
    if on_path:
        return on_path
    macos_path = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
    if os.path.exists(macos_path):
        return macos_path
    return None


_ATTINY85_PINS = [
    {"number": "1", "name": "RESET", "electrical_type": "bidirectional"},
    {"number": "2", "name": "PB3", "electrical_type": "input"},
    {"number": "3", "name": "PB4", "electrical_type": "output"},
    {"number": "4", "name": "GND", "electrical_type": "ground"},
    {"number": "5", "name": "PB0", "electrical_type": "bidirectional"},
    {"number": "6", "name": "PB1", "electrical_type": "bidirectional"},
    {"number": "7", "name": "PB2", "electrical_type": "bidirectional"},
    {"number": "8", "name": "VCC", "electrical_type": "power"},
]


class TestLayoutPins(unittest.TestCase):

    def test_001_splits_pins_evenly_left_and_right(self):
        layout = store._layout_pins(_ATTINY85_PINS)
        left = [p for p in layout["pins"] if p["angle"] == 0]
        right = [p for p in layout["pins"] if p["angle"] == 180]
        self.assertEqual(len(left), 4)
        self.assertEqual(len(right), 4)

    def test_002_left_pins_are_negative_x_right_pins_are_positive_x(self):
        """Matches real KiCad convention confirmed by reading actual
        .kicad_sym files: angle 0 on the left (negative x), angle 180 on
        the right (positive x)."""
        layout = store._layout_pins(_ATTINY85_PINS)
        for pin in layout["pins"]:
            if pin["angle"] == 0:
                self.assertLess(pin["x"], 0)
            else:
                self.assertGreater(pin["x"], 0)

    def test_003_pins_on_one_side_are_stacked_on_the_real_2_54mm_grid(self):
        layout = store._layout_pins(_ATTINY85_PINS)
        left_ys = sorted(p["y"] for p in layout["pins"] if p["angle"] == 0)
        gaps = [round(b - a, 4) for a, b in zip(left_ys, left_ys[1:])]
        self.assertTrue(all(gap == store._KICAD_PIN_PITCH_MM for gap in gaps))

    def test_004_an_odd_pin_count_puts_the_extra_pin_on_the_left(self):
        layout = store._layout_pins(_ATTINY85_PINS[:5])
        left = [p for p in layout["pins"] if p["angle"] == 0]
        right = [p for p in layout["pins"] if p["angle"] == 180]
        self.assertEqual(len(left), 3)
        self.assertEqual(len(right), 2)


class TestExportSymbolKicadSym(LibraryStoreTestCase):

    def test_001_writes_a_real_file_to_the_symbols_directory(self):
        store.save_symbol({"symbol_id": "SOIC-8_8pin", "reference_prefix": "U", "pins": _ATTINY85_PINS})
        path = store.export_symbol_kicad_sym("SOIC-8_8pin")
        self.assertTrue(path.endswith(os.path.join("library", "symbols", "SOIC-8_8pin.kicad_sym")))
        with open(path) as f:
            text = f.read()
        self.assertIn('(kicad_symbol_lib', text)
        self.assertIn('"SOIC-8_8pin"', text)

    def test_002_a_real_kicad_cli_parses_and_renders_the_exported_file(self):
        """The real bar SPEC-307 §2 itself names: a file KiCad's own
        parser accepts and can render, not just plausible-looking text.
        Skips cleanly if kicad-cli isn't found on this machine, same
        convention every other real-tool test in this repo uses."""
        kicad_cli = _find_kicad_cli()
        if not kicad_cli:
            self.skipTest("kicad-cli not found on this machine.")

        store.save_symbol({"symbol_id": "SOIC-8_8pin", "reference_prefix": "U", "pins": _ATTINY85_PINS})
        path = store.export_symbol_kicad_sym("SOIC-8_8pin")

        with tempfile.TemporaryDirectory() as svg_dir:
            result = subprocess.run(
                [kicad_cli, "sym", "export", "svg", "-o", svg_dir, path],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            svgs = [f for f in os.listdir(svg_dir) if f.endswith(".svg")]
            self.assertEqual(len(svgs), 1)

    def test_003_escapes_a_pin_name_containing_a_double_quote(self):
        """A malformed .kicad_sym from an unescaped quote is a real,
        not hypothetical, risk -- pin names come from an LLM extraction
        (SPEC-202), which never guarantees clean input."""
        pins = [{"number": "1", "name": 'weird"name', "electrical_type": "passive"}]
        store.save_symbol({"symbol_id": "weird_1pin", "reference_prefix": "U", "pins": pins})
        path = store.export_symbol_kicad_sym("weird_1pin")
        with open(path) as f:
            text = f.read()
        self.assertIn('weird\\"name', text)


_SOIC8_PADS = [
    {"number": str(i), "x_mm": -2.0 if i <= 4 else 2.0, "y_mm": (i - 2.5) * 1.27 if i <= 4 else (6.5 - i) * 1.27,
     "width_mm": 1.5, "height_mm": 0.6, "pad_type": "smd", "drill_mm": None}
    for i in range(1, 9)
]
_SOIC8_COURTYARD = {"length_mm": 5.4, "width_mm": 4.4}


class TestExportFootprintKicadMod(LibraryStoreTestCase):
    """CTX-308.6: SPEC-308 §1's "export it to a real .pretty library" --
    only meaningful for a footprint with real pad geometry, which today
    only a CTX-308.5-generated footprint has."""

    def test_001_writes_a_real_file_to_a_real_pretty_directory(self):
        """KiCad's own convention: a footprint library is a directory
        named *.pretty/, unlike a symbol library's single .kicad_sym
        file -- confirmed by reading real footprint libraries on this
        machine before writing this, not assumed."""
        store.save_footprint({
            "footprint_id": "generated__ATtiny85", "pads": _SOIC8_PADS, "courtyard": _SOIC8_COURTYARD,
        })
        path = store.export_footprint_kicad_mod("generated__ATtiny85")
        self.assertTrue(
            path.endswith(os.path.join("library", "footprints.pretty", "generated__ATtiny85.kicad_mod"))
        )
        with open(path) as f:
            text = f.read()
        self.assertIn('(footprint "generated__ATtiny85"', text)
        self.assertEqual(text.count('(pad '), 8)

    def test_002_a_real_kicad_cli_parses_and_renders_the_exported_file(self):
        """The real bar this repo holds itself to: a file KiCad's own
        parser accepts and can render, not just plausible-looking text.
        kicad-cli fp export svg (unlike sym export svg) takes the
        containing .pretty directory plus --footprint, not the file
        path directly -- confirmed by actually running it before writing
        this assertion, not assumed from the --help text alone. Skips
        cleanly if kicad-cli isn't found, same convention as symbol
        export's own test."""
        kicad_cli = _find_kicad_cli()
        if not kicad_cli:
            self.skipTest("kicad-cli not found on this machine.")

        store.save_footprint({
            "footprint_id": "generated__ATtiny85", "pads": _SOIC8_PADS, "courtyard": _SOIC8_COURTYARD,
        })
        path = store.export_footprint_kicad_mod("generated__ATtiny85")
        pretty_dir = os.path.dirname(path)

        with tempfile.TemporaryDirectory() as svg_dir:
            result = subprocess.run(
                [kicad_cli, "fp", "export", "svg", "-o", svg_dir, "--footprint", "generated__ATtiny85", pretty_dir],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            svgs = [f for f in os.listdir(svg_dir) if f.endswith(".svg")]
            self.assertEqual(len(svgs), 1)

    def test_003_a_thru_hole_pad_round_trips_through_real_kicad_cli_too(self):
        """Real, not hypothetical: DIP packages (kicad_write.
        THROUGH_HOLE_PACKAGES) produce pth pads with a real drill --
        the smd-only test above doesn't exercise that branch."""
        kicad_cli = _find_kicad_cli()
        if not kicad_cli:
            self.skipTest("kicad-cli not found on this machine.")

        pads = [
            {"number": "1", "x_mm": -1.27, "y_mm": -3.81, "width_mm": 1.6, "height_mm": 1.6,
             "pad_type": "pth", "drill_mm": 0.8},
        ]
        store.save_footprint({
            "footprint_id": "generated__DIPTest", "pads": pads, "courtyard": {"length_mm": 10.0, "width_mm": 8.0},
        })
        path = store.export_footprint_kicad_mod("generated__DIPTest")
        pretty_dir = os.path.dirname(path)

        with open(path) as f:
            text = f.read()
        self.assertIn("thru_hole", text)
        self.assertIn("(drill 0.8)", text)

        with tempfile.TemporaryDirectory() as svg_dir:
            result = subprocess.run(
                [kicad_cli, "fp", "export", "svg", "-o", svg_dir, "--footprint", "generated__DIPTest", pretty_dir],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_004_a_footprint_with_no_pad_geometry_fails_closed_not_a_meaningless_file(self):
        """A footprint attached via CTX-308.2's own find flow
        ({footprint_id, library, footprint_name}, no pads at all) has
        nothing real to export -- it's already a real .kicad_mod
        sitting in the user's own KiCad library. Must raise, not write
        an empty/meaningless file."""
        store.save_footprint({"footprint_id": "MyPCBLibs__MP1584EN_5V_Module", "library": "MyPCBLibs",
                               "footprint_name": "MP1584EN_5V_Module"})
        with self.assertRaises(store.SchemaValidationError):
            store.export_footprint_kicad_mod("MyPCBLibs__MP1584EN_5V_Module")

    # Deliberately no "footprint_id containing a double quote" test here,
    # unlike TestExportSymbolKicadSym.test_003: footprint_id doubles as
    # this file's own on-disk filename (unlike a symbol's pin *name*,
    # which is just text inside the file) -- a literal `"` is invalid on
    # Windows, the same class of bug CTX-308.4 already found and fixed
    # for `:`. footprint_id is already required to be filesystem-safe by
    # that established convention, so this isn't a realistic input to
    # defend against here. _sexpr_str's own escaping is already covered
    # by the symbol export test above (same shared helper).


if __name__ == '__main__':
    unittest.main()

import http.server
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


if __name__ == '__main__':
    unittest.main()

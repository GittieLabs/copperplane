import io
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the parent directory to sys.path so we can import daemon
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import daemon
from daemon import handle_request

class TestJSONRPCDaemon(unittest.TestCase):

    def test_001_valid_routing(self):
        """TEST-001: Validates valid JSON-RPC parsing and routing. Uses a
        synthetic route (not a real business one) so this stays a pure
        routing/parsing check -- kicad.generate_component is now a real,
        async-dispatched pipeline (SPEC-202) with its own dedicated,
        real/skip-clean tests in test_component_pipeline.py, and running
        it here would trigger an uncontrolled real LLM call."""
        daemon.ROUTES['test.echo_query'] = lambda query: {"received": query.upper()}
        try:
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "test.echo_query",
                "params": {"query": "esp32"},
                "id": "req_100"
            })

            response_str = handle_request(request)
            response = json.loads(response_str)

            self.assertEqual(response.get("jsonrpc"), "2.0")
            self.assertEqual(response.get("id"), "req_100")
            self.assertIn("result", response)
            self.assertNotIn("error", response)
            self.assertEqual(response["result"]["received"], "ESP32")
        finally:
            daemon.ROUTES.pop('test.echo_query', None)

    def test_002_malformed_json(self):
        """TEST-002: Handles malformed JSON input without crashing"""
        request = "THIS IS NOT VALID JSON"
        
        response_str = handle_request(request)
        response = json.loads(response_str)
        
        self.assertEqual(response.get("jsonrpc"), "2.0")
        self.assertIsNone(response.get("id"))
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32700)
        self.assertEqual(response["error"]["message"], "Parse error")

    def test_003_method_not_found(self):
        """TEST-003: Returns Method Not Found for unknown routes"""
        request = json.dumps({
            "jsonrpc": "2.0",
            "method": "fake.route.does_not_exist",
            "params": {},
            "id": "req_404"
        })
        
        response_str = handle_request(request)
        response = json.loads(response_str)
        
        self.assertEqual(response.get("jsonrpc"), "2.0")
        self.assertEqual(response.get("id"), "req_404")
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32601)
        self.assertIn("Method not found", response["error"]["message"])

    def test_004_async_route_returns_job_id_immediately(self):
        """TEST-004 (CTX-105.1): An async-flagged route returns
        {"job_id": ...} immediately; the route function itself runs on a
        worker thread, not the calling thread."""
        calling_thread = threading.current_thread()
        release = threading.Event()
        seen_thread = {}

        def slow_route():
            seen_thread['thread'] = threading.current_thread()
            release.wait(timeout=5)
            return {"done": True}

        original_write_line = daemon._write_line
        daemon._write_line = lambda text: None  # job.progress/completed noise isn't under test here
        daemon.ROUTES['test.slow'] = slow_route
        daemon.ASYNC_ROUTES.add('test.slow')
        try:
            request = json.dumps({
                "jsonrpc": "2.0", "method": "test.slow", "params": {}, "id": "req_async"
            })

            start = time.monotonic()
            response = json.loads(handle_request(request))
            elapsed = time.monotonic() - start

            self.assertLess(elapsed, 1.0, "handle_request should return immediately, not block on the route")
            self.assertNotIn("error", response)
            self.assertIn("job_id", response.get("result", {}))
        finally:
            release.set()
            time.sleep(0.2)  # let the worker thread actually run before asserting on it
            daemon.ROUTES.pop('test.slow', None)
            daemon.ASYNC_ROUTES.discard('test.slow')
            daemon._write_line = original_write_line

        self.assertIn('thread', seen_thread, "the route should have run on a worker thread")
        self.assertNotEqual(seen_thread['thread'], calling_thread, "route ran on the calling thread, not a worker")

    def test_005_invalid_params_returns_dash32602(self):
        """TEST-005 (CTX-105.1): A route call with a missing required
        parameter or an unexpected keyword returns -32602 Invalid params,
        not the previous opaque -32000."""

        def strict_route(required_field):
            return {"received": required_field}

        daemon.ROUTES['test.strict'] = strict_route
        try:
            missing_request = json.dumps({
                "jsonrpc": "2.0", "method": "test.strict", "params": {}, "id": "req_missing"
            })
            missing_response = json.loads(handle_request(missing_request))
            self.assertEqual(missing_response["error"]["code"], -32602)
            self.assertIn("Missing required parameter", missing_response["error"]["message"])

            unexpected_request = json.dumps({
                "jsonrpc": "2.0",
                "method": "test.strict",
                "params": {"required_field": "x", "typo_field": "y"},
                "id": "req_unexpected",
            })
            unexpected_response = json.loads(handle_request(unexpected_request))
            self.assertEqual(unexpected_response["error"]["code"], -32602)
            self.assertIn("Unexpected parameter", unexpected_response["error"]["message"])
        finally:
            daemon.ROUTES.pop('test.strict', None)

    def test_006_daemon_configure_merges_secrets_into_config(self):
        """TEST-004 (CTX-106.1): daemon.configure, dispatched through
        handle_request like any other route, merges its secrets param
        into the in-memory CONFIG and returns {"configured": true}."""
        original_secrets = daemon.CONFIG.get("secrets")
        try:
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "daemon.configure",
                "params": {"secrets": {"llm_api_key": "sk-test-123"}},
                "id": "req_configure",
            })
            response = json.loads(handle_request(request))

            self.assertNotIn("error", response)
            self.assertEqual(response["result"], {"configured": True})
            self.assertEqual(daemon.CONFIG["secrets"], {"llm_api_key": "sk-test-123"})
        finally:
            daemon.CONFIG["secrets"] = original_secrets


class TestStartupHandshakeAndDiagnostics(unittest.TestCase):
    """CTX-107.1: daemon.ready capability detection and the daemon.heartbeat
    signal Rust's macOS crash-detection path relies on."""

    def test_001_detect_capabilities_matches_find_freecadcmd_for_real(self):
        """TEST-001: a real, non-mocked check -- freecad_available agrees
        with whatever find_freecadcmd itself finds on this machine.
        Deliberately not a hardcoded True/False, so this test is honest on
        both a dev machine with FreeCAD installed and a CI runner without
        one (same 'verify for real, without assuming an environment'
        pattern as CTX-104.1's own TEST-004)."""
        try:
            daemon.freecad_bridge.find_freecadcmd()
            expected = True
        except daemon.freecad_bridge.FreeCADUnavailableError:
            expected = False

        caps = daemon._detect_capabilities()
        self.assertEqual(caps["freecad_available"], expected)
        self.assertIn("kicad_available", caps)
        self.assertIn("llm_providers", caps)

    @patch('daemon.freecad_bridge.find_freecadcmd')
    def test_002_detect_capabilities_reports_freecad_unavailable_on_error(self, mock_find):
        """TEST-001: freecad_available is False when find_freecadcmd raises."""
        mock_find.side_effect = daemon.freecad_bridge.FreeCADUnavailableError("not found")
        caps = daemon._detect_capabilities()
        self.assertFalse(caps["freecad_available"])

    def test_002b_detect_capabilities_matches_find_kicad_cli_for_real(self):
        """CTX-309.1: same real, non-hardcoded pattern as test_001 above,
        for kicad_cli_available."""
        try:
            daemon.kicad_cli.find_kicad_cli()
            expected = True
        except daemon.kicad_cli.KicadCliUnavailableError:
            expected = False

        caps = daemon._detect_capabilities()
        self.assertEqual(caps["kicad_cli_available"], expected)

    @patch('daemon.kicad_cli.find_kicad_cli')
    def test_002c_detect_capabilities_reports_kicad_cli_unavailable_on_error(self, mock_find):
        mock_find.side_effect = daemon.kicad_cli.KicadCliUnavailableError("not found")
        caps = daemon._detect_capabilities()
        self.assertFalse(caps["kicad_cli_available"])

    def test_002d_detect_capabilities_reports_suppliers_unconfigured_by_default(self):
        """SPEC-203 (CTX-203.1): no credentials configured -- CLAUDE.md's
        norm applied here means these must default to False, not silently
        True, since no real supplier client exists to have verified
        anything against yet."""
        caps = daemon._detect_capabilities()
        self.assertFalse(caps["digikey_available"])
        self.assertFalse(caps["mouser_available"])
        self.assertFalse(caps["octopart_available"])

    def test_002e_digikey_available_requires_both_real_secrets_not_just_one(self):
        """DigiKey's real OAuth2 client-credentials flow needs both an ID
        and a secret -- a lone digikey_client_id can't actually
        authenticate, so it must not report as configured."""
        original_secrets = daemon.CONFIG.get("secrets", {})
        daemon.CONFIG["secrets"] = {"digikey_client_id": "abc"}
        try:
            caps = daemon._detect_capabilities()
            self.assertFalse(caps["digikey_available"])

            daemon.CONFIG["secrets"] = {"digikey_client_id": "abc", "digikey_client_secret": "xyz"}
            caps = daemon._detect_capabilities()
            self.assertTrue(caps["digikey_available"])
        finally:
            daemon.CONFIG["secrets"] = original_secrets

    def test_002f_mouser_and_octopart_each_need_only_their_own_single_key(self):
        original_secrets = daemon.CONFIG.get("secrets", {})
        daemon.CONFIG["secrets"] = {"mouser_api_key": "m-key", "octopart_api_key": "o-key"}
        try:
            caps = daemon._detect_capabilities()
            self.assertTrue(caps["mouser_available"])
            self.assertTrue(caps["octopart_available"])
            self.assertFalse(caps["digikey_available"])
        finally:
            daemon.CONFIG["secrets"] = original_secrets

    @patch('daemon.os.path.exists', return_value=True)
    def test_003_detect_capabilities_reports_kicad_available_when_socket_present(self, mock_exists):
        """TEST-001: kicad_available reflects whether the IPC socket path exists."""
        caps = daemon._detect_capabilities()
        self.assertTrue(caps["kicad_available"])

    def test_004_main_emits_daemon_ready_before_reading_any_input(self):
        """TEST-002: main() emits daemon.ready -- reporting detected
        capabilities -- before (and regardless of) anything arriving on
        stdin. Feeding it an immediately-EOF stdin proves this: main()
        only returns after emitting daemon.ready, not because a request
        was ever read."""
        captured = []
        original_write_line = daemon._write_line
        original_stdin = sys.stdin
        daemon._write_line = lambda text: captured.append(json.loads(text))
        sys.stdin = io.StringIO("")
        try:
            daemon.main()
        finally:
            daemon._write_line = original_write_line
            sys.stdin = original_stdin

        ready_notifications = [n for n in captured if n.get("method") == "daemon.ready"]
        self.assertEqual(len(ready_notifications), 1)
        self.assertIn("kicad_available", ready_notifications[0]["params"])
        self.assertIn("freecad_available", ready_notifications[0]["params"])

    def test_005_emit_heartbeat_writes_a_daemon_heartbeat_notification(self):
        """TEST-003: _emit_heartbeat (the body of the background heartbeat
        loop) writes exactly one daemon.heartbeat notification -- tested
        directly rather than running the real infinite loop, which sleeps
        forever between beats."""
        captured = []
        original_write_line = daemon._write_line
        daemon._write_line = lambda text: captured.append(json.loads(text))
        try:
            daemon._emit_heartbeat()
        finally:
            daemon._write_line = original_write_line

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["method"], "daemon.heartbeat")
        self.assertNotIn("id", captured[0])

    def test_006_build_routes_omits_kicad_route_when_import_failed(self):
        """TEST-004: if kicad_bridge's import had failed (get_kicad_version
        would be None), _build_routes omits kicad.get_version but keeps
        every other route -- a broken kipy install doesn't take down the
        daemon's ability to serve FreeCAD/job/config requests."""
        original = daemon.get_kicad_version
        daemon.get_kicad_version = None
        try:
            routes = daemon._build_routes()
            self.assertNotIn("kicad.get_version", routes)
            self.assertIn("kicad.generate_component", routes)
            self.assertIn("job.cancel", routes)
            self.assertIn("daemon.configure", routes)
        finally:
            daemon.get_kicad_version = original

    def test_007_build_routes_omits_library_routes_when_import_failed(self):
        """TEST-004 (CTX-304.1): mirrors test_006 for library_store --
        a broken import there shouldn't take down anything else."""
        original = daemon.library_store
        daemon.library_store = None
        try:
            routes = daemon._build_routes()
            self.assertNotIn("library.save_part", routes)
            self.assertNotIn("project.save", routes)
            self.assertNotIn("component.cache_datasheet", routes)
            self.assertIn("job.cancel", routes)
        finally:
            daemon.library_store = original

    def test_008_build_routes_omits_component_search_when_import_failed(self):
        """TEST-004 (CTX-306.1): mirrors test_006/007 for component.search
        -- a broken component_pipeline import shouldn't take down
        anything else, and kicad.generate_component/component.search
        share the same gate since both depend on that module."""
        original = daemon.component_pipeline
        daemon.component_pipeline = None
        try:
            routes = daemon._build_routes()
            self.assertNotIn("kicad.generate_component", routes)
            self.assertNotIn("component.search", routes)
            self.assertIn("job.cancel", routes)
        finally:
            daemon.component_pipeline = original

    def test_009_component_search_and_cache_datasheet_are_registered_as_async(self):
        """TEST-004 (CTX-306.1): both are real, multi-second calls (an
        LLM search, a network fetch) -- the read loop must never block on
        either, same reasoning kicad.generate_component/
        freecad.generate_enclosure already established."""
        self.assertIn("component.search", daemon.ASYNC_ROUTES)
        self.assertIn("component.cache_datasheet", daemon.ASYNC_ROUTES)


class TestLibraryRoutes(unittest.TestCase):
    """CTX-304.1: library.*/project.* routes, dispatched through
    handle_request like any other route -- real file I/O against a real
    temp directory, not mocked, per CLAUDE.md's 'verify for real' norm."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        daemon.library_store.configure(storage_root=self._tmpdir.name)

    def tearDown(self):
        daemon.library_store.configure(storage_root=None)
        self._tmpdir.cleanup()

    def _dispatch(self, method, params):
        request = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": "req"})
        return json.loads(handle_request(request))

    def test_001_library_save_part_and_load_part_round_trip(self):
        provenance = {
            field: {"source": "datasheet_pdf"}
            for field in daemon.library_store.PART_PROVENANCE_REQUIRED_FIELDS
        }
        part = {
            "part_id": "ATtiny85",
            "manufacturer": "Microchip",
            "package": "SOIC-8",
            "pins": [],
            "datasheet_url": "https://example.com/x.pdf",
            "provenance": provenance,
        }

        save_response = self._dispatch("library.save_part", {"part": part})
        self.assertNotIn("error", save_response)

        load_response = self._dispatch("library.load_part", {"part_id": "ATtiny85"})
        self.assertNotIn("error", load_response)
        self.assertEqual(load_response["result"]["manufacturer"], "Microchip")

    def test_002_project_save_and_project_list_round_trip(self):
        save_response = self._dispatch("project.save", {"project": {"name": "weather-pcb"}})
        self.assertNotIn("error", save_response)

        list_response = self._dispatch("project.list", {})
        self.assertEqual(list_response["result"], ["weather-pcb"])

    def test_003_a_schema_validation_error_surfaces_as_a_clean_route_error(self):
        """A missing-provenance Part must not crash the daemon or leak a
        raw traceback -- same handle_request error-mapping every other
        route already gets."""
        response = self._dispatch("library.save_part", {"part": {"part_id": "X"}})
        self.assertIn("error", response)

    def test_004_save_confirmed_part_builds_provenance_from_the_candidate_and_extraction(self):
        """CTX-307.1 (SPEC-307): manufacturer/datasheet_url provenance
        comes from the SPEC-306 search candidate; package/pins
        provenance comes from this route's own extraction call. The
        result must pass CTX-304.1's own _validate_part_provenance
        check for real, not just look right."""
        candidate = {
            "part_number": "ATtiny85",
            "manufacturer": "Microchip",
            "package": "DIP-8",
            "datasheet_url": "https://example.com/attiny85.pdf",
            "confidence": "high",
            "rationale": "Exact match.",
        }
        extraction = {
            "part_number": "ATtiny85",
            "package": "SOIC-8",
            "pins": [
                {"number": "1", "name": "RESET", "electrical_type": "bidirectional"},
                {"number": "2", "name": "GND", "electrical_type": "ground"},
            ],
            "package_dimensions": {"length_mm": 4.9, "width_mm": 3.9, "height_mm": 1.75, "pitch_mm": 1.27},
            "courtyard": {"length_mm": 5.4, "width_mm": 4.4},
        }

        original_config = dict(daemon.CONFIG)
        daemon.CONFIG["llm_provider"] = "google"
        daemon.CONFIG["llm_model"] = "gemini-flash"
        try:
            response = self._dispatch(
                "library.save_confirmed_part", {"candidate": candidate, "extraction": extraction},
            )
        finally:
            daemon.CONFIG.clear()
            daemon.CONFIG.update(original_config)
        self.assertNotIn("error", response)

        part = daemon.library_store.load_part("ATtiny85")
        self.assertEqual(part["manufacturer"], "Microchip")
        self.assertEqual(part["package"], "SOIC-8")
        self.assertEqual(part["provenance"]["manufacturer"]["source"], "search")
        self.assertEqual(part["provenance"]["manufacturer"]["confidence"], "high")
        self.assertEqual(part["provenance"]["package"]["source"], "llm_extraction")
        self.assertEqual(part["provenance"]["package"]["model"], "gemini-flash")
        # CTX-308.5: package_dimensions/courtyard were previously dropped
        # by this route even though the extraction call already returns
        # them -- required for SPEC-308's datasheet-generated footprint
        # source, which reuses these fields with no second LLM call.
        self.assertEqual(part["package_dimensions"], extraction["package_dimensions"])
        self.assertEqual(part["courtyard"], extraction["courtyard"])
        self.assertEqual(part["provenance"]["package_dimensions"]["source"], "llm_extraction")
        self.assertEqual(part["provenance"]["courtyard"]["source"], "llm_extraction")

        symbol = daemon.library_store.load_symbol(part["symbol_id"])
        self.assertEqual(len(symbol["pins"]), 2)

    def test_005_save_confirmed_part_reuses_the_same_symbol_for_an_identical_pinout(self):
        """SPEC-307 §3's own named gotcha: symbol_id is a package+pin-count
        signature, not a random id, so a second Part with the same
        package/pin-count converges on one Symbol record."""
        candidate_1 = {"part_number": "ATtiny85", "manufacturer": "Microchip", "confidence": "high"}
        candidate_2 = {"part_number": "ATtiny45", "manufacturer": "Microchip", "confidence": "high"}
        extraction = {
            "part_number": "X",
            "package": "SOIC-8",
            "pins": [{"number": str(i), "name": f"P{i}", "electrical_type": "passive"} for i in range(1, 9)],
        }

        r1 = self._dispatch(
            "library.save_confirmed_part", {"candidate": candidate_1, "extraction": {**extraction, "part_number": "ATtiny85"}},
        )
        r2 = self._dispatch(
            "library.save_confirmed_part", {"candidate": candidate_2, "extraction": {**extraction, "part_number": "ATtiny45"}},
        )

        self.assertEqual(r1["result"]["symbol"]["symbol_id"], r2["result"]["symbol"]["symbol_id"])

    def test_006_export_symbol_dispatches_and_returns_a_real_path(self):
        candidate = {
            "part_number": "ATtiny85", "manufacturer": "Microchip",
            "datasheet_url": "https://example.com/x.pdf", "confidence": "high",
        }
        extraction = {
            "part_number": "ATtiny85", "package": "SOIC-8",
            "pins": [{"number": "1", "name": "P1", "electrical_type": "passive"}],
        }
        saved = self._dispatch("library.save_confirmed_part", {"candidate": candidate, "extraction": extraction})
        symbol_id = saved["result"]["symbol"]["symbol_id"]

        response = self._dispatch("library.export_symbol", {"symbol_id": symbol_id})
        self.assertNotIn("error", response)
        self.assertTrue(response["result"]["path"].endswith(".kicad_sym"))
        self.assertTrue(os.path.exists(response["result"]["path"]))

    def test_007_export_footprint_dispatches_and_returns_a_real_path(self):
        """CTX-308.6: the full real chain -- save a Part with real
        dimensions (CTX-308.5's own fix), generate a real Footprint from
        them, then export it to a real .kicad_mod file -- through
        handle_request end to end, not calling library_store directly."""
        candidate = {
            "part_number": "ATtiny85", "manufacturer": "Microchip",
            "datasheet_url": "https://example.com/attiny85.pdf", "confidence": "high",
        }
        extraction = {
            "part_number": "ATtiny85",
            "package": "SOIC-8",
            "pins": [{"number": str(i), "name": f"P{i}", "electrical_type": "passive"} for i in range(1, 9)],
            "package_dimensions": {"length_mm": 4.9, "width_mm": 3.9, "height_mm": 1.75, "pitch_mm": 1.27},
            "courtyard": {"length_mm": 5.4, "width_mm": 4.4},
        }
        saved = self._dispatch(
            "library.save_confirmed_part", {"candidate": candidate, "extraction": extraction},
        )
        self.assertNotIn("error", saved)
        generated = self._dispatch("kicad.generate_footprint_from_part", {"part_id": "ATtiny85"})
        self.assertNotIn("error", generated)
        footprint_id = generated["result"]["footprint_id"]

        response = self._dispatch("library.export_footprint", {"footprint_id": footprint_id})
        self.assertNotIn("error", response)
        self.assertTrue(response["result"]["path"].endswith(".kicad_mod"))
        self.assertTrue(os.path.exists(response["result"]["path"]))

    def test_008_export_footprint_on_a_found_not_generated_footprint_fails_closed(self):
        """A footprint from CTX-308.2's own attach flow has no pads at
        all -- the real route error, not a crash, surfaced through
        handle_request the same way every other library_store
        SchemaValidationError already is."""
        saved = self._dispatch("library.save_footprint", {
            "footprint": {"footprint_id": "MyPCBLibs__X", "library": "MyPCBLibs", "footprint_name": "X"},
        })
        self.assertNotIn("error", saved)

        response = self._dispatch("library.export_footprint", {"footprint_id": "MyPCBLibs__X"})
        self.assertIn("error", response)
        self.assertIn("no pad geometry", response["error"]["message"])


class TestLlmChatProviderFallback(unittest.TestCase):
    """CTX-302.1: llm_chat's provider resolution -- found by actually
    running the real chat surface against a real, never-configured
    install (no config.json exists anywhere on this machine, and
    SPEC-303's settings UI doesn't exist yet to create one): the old
    behavior raised LLMProviderError outright, which meant the chat
    surface's plain-chat fallback could never work at all on a fresh
    install. Mocked -- llm_providers.chat is a real, already-verified
    function (test_llm_providers.py); this only checks what daemon.py
    resolves before calling it."""

    def setUp(self):
        self._original_config = dict(daemon.CONFIG)

    def tearDown(self):
        daemon.CONFIG.clear()
        daemon.CONFIG.update(self._original_config)

    @patch('daemon.llm_providers.chat')
    def test_001_falls_back_to_the_default_provider_when_nothing_is_configured(self, mock_chat):
        daemon.CONFIG['llm_provider'] = None
        mock_chat.return_value = "ok"

        daemon.llm_chat("hello")

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs['provider'], daemon.llm_providers._DEFAULT_PROVIDER)

    @patch('daemon.llm_providers.chat')
    def test_002_an_explicit_provider_still_wins_over_the_default(self, mock_chat):
        daemon.CONFIG['llm_provider'] = None
        mock_chat.return_value = "ok"

        daemon.llm_chat("hello", provider="google")

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs['provider'], "google")

    @patch('daemon.llm_providers.chat')
    def test_003_a_configured_provider_still_wins_over_the_default(self, mock_chat):
        daemon.CONFIG['llm_provider'] = "perplexity"
        mock_chat.return_value = "ok"

        daemon.llm_chat("hello")

        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs['provider'], "perplexity")


class TestConfigureDaemonLiveUpdates(unittest.TestCase):
    """CTX-303.1: daemon.configure's SPEC-303 extension -- llm_provider/
    llm_model can now be updated live, the same way secrets already were,
    without regressing the secrets-only call Rust's spawn_daemon makes."""

    def setUp(self):
        self._original_config = dict(daemon.CONFIG)

    def tearDown(self):
        daemon.CONFIG.clear()
        daemon.CONFIG.update(self._original_config)

    def test_001_secrets_only_call_leaves_provider_and_model_untouched(self):
        """TEST-005: Rust's spawn-time call passes only secrets -- must not
        regress into clearing llm_provider/llm_model as a side effect."""
        daemon.CONFIG['llm_provider'] = "anthropic"
        daemon.CONFIG['llm_model'] = "claude-sonnet"

        daemon.configure_daemon(secrets={"anthropic_api_key": "sk-test"})

        self.assertEqual(daemon.CONFIG['llm_provider'], "anthropic")
        self.assertEqual(daemon.CONFIG['llm_model'], "claude-sonnet")
        self.assertEqual(daemon.CONFIG['secrets'], {"anthropic_api_key": "sk-test"})

    def test_002_passing_llm_provider_and_model_updates_them_live(self):
        """TEST-005: a Settings-UI-style call updates CONFIG immediately,
        with no daemon restart, the same live-update guarantee secrets
        already had."""
        daemon.CONFIG['llm_provider'] = None
        daemon.CONFIG['llm_model'] = None

        result = daemon.configure_daemon(llm_provider="google", llm_model="gemini-pro")

        self.assertEqual(result, {"configured": True})
        self.assertEqual(daemon.CONFIG['llm_provider'], "google")
        self.assertEqual(daemon.CONFIG['llm_model'], "gemini-pro")

    def test_003_omitting_secrets_leaves_the_existing_secrets_untouched(self):
        """TEST-005: a provider/model-only call must not wipe secrets that
        were configured by an earlier call."""
        daemon.CONFIG['secrets'] = {"anthropic_api_key": "sk-existing"}

        daemon.configure_daemon(llm_provider="anthropic")

        self.assertEqual(daemon.CONFIG['secrets'], {"anthropic_api_key": "sk-existing"})


class TestDaemonCapabilities(unittest.TestCase):
    """CTX-303.1: daemon.get_capabilities (on-demand) and _detect_capabilities's
    llm_providers field (fixed from a hardcoded [])."""

    def setUp(self):
        self._original_config = dict(daemon.CONFIG)

    def tearDown(self):
        daemon.CONFIG.clear()
        daemon.CONFIG.update(self._original_config)

    def test_001_llm_providers_reflects_configured_secrets(self):
        """TEST-004: only providers with a real configured key are
        reported, not the old hardcoded empty list."""
        daemon.CONFIG['secrets'] = {
            "anthropic_api_key": "sk-1",
            "perplexity_api_key": "sk-2",
        }

        caps = daemon._detect_capabilities()

        self.assertEqual(sorted(caps['llm_providers']), ["anthropic", "perplexity"])

    def test_002_llm_providers_is_empty_when_nothing_is_configured(self):
        """TEST-004: the honest, un-configured state -- distinct from the
        old behavior, which reported [] unconditionally regardless of
        CONFIG, for the wrong reason."""
        daemon.CONFIG['secrets'] = {}

        caps = daemon._detect_capabilities()

        self.assertEqual(caps['llm_providers'], [])

    def test_004_reports_the_real_resolved_log_path(self):
        """CTX-303.3: log_path matches whatever _configure_logging actually
        resolved for this real process -- not asserting a specific path
        (that's per-OS), just that the two agree."""
        caps = daemon._detect_capabilities()
        self.assertEqual(caps['log_path'], daemon._LOG_FILE_PATH)

    def test_005_reports_the_real_python_version(self):
        """CTX-303.3."""
        import platform as _platform

        caps = daemon._detect_capabilities()
        self.assertEqual(caps['python_version'], _platform.python_version())

    def test_003_get_daemon_capabilities_route_returns_the_same_shape_on_demand(self):
        """TEST-004: dispatched through handle_request like any other
        route -- proves it's really wired into ROUTES, not just callable
        as a bare function."""
        daemon.CONFIG['secrets'] = {"google_api_key": "sk-1"}

        request = json.dumps({
            "jsonrpc": "2.0", "method": "daemon.get_capabilities", "params": {}, "id": "req_caps",
        })
        response = json.loads(handle_request(request))

        self.assertNotIn("error", response)
        self.assertIn("kicad_available", response["result"])
        self.assertIn("freecad_available", response["result"])
        self.assertEqual(response["result"]["llm_providers"], ["google"])
        self.assertIn("log_path", response["result"])
        self.assertIn("python_version", response["result"])

    def test_006_reports_the_real_currently_configured_storage_root(self):
        """SPEC-110: storage_root reflects library_store's own real,
        currently-active root (the Rust-computed value spawn_daemon
        injected), so Settings can display it without config.json ever
        needing to hold it."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            original_root = daemon.library_store._storage_root_override
            daemon.library_store.configure(storage_root=tmpdir)
            try:
                caps = daemon._detect_capabilities()
                self.assertEqual(caps['storage_root'], tmpdir)
            finally:
                daemon.library_store.configure(storage_root=original_root)

    def test_007_reports_none_when_library_store_failed_to_import(self):
        original = daemon.library_store
        daemon.library_store = None
        try:
            caps = daemon._detect_capabilities()
            self.assertIsNone(caps['storage_root'])
        finally:
            daemon.library_store = original


class TestKicadGenerateComponentProviderOverride(unittest.TestCase):
    """CTX-303.2: kicad_generate_component used to always run
    component_extraction.prompt.md's hardcoded provider, completely
    ignoring CONFIG["llm_provider"]/["llm_model"] -- found only by real
    end-to-end verification of SPEC-303's Settings UI (CTX-303.1 Plan
    Drift Deviation 2). Fixed to resolve the same way llm_chat already
    does."""

    def setUp(self):
        self._original_config = dict(daemon.CONFIG)

    def tearDown(self):
        daemon.CONFIG.clear()
        daemon.CONFIG.update(self._original_config)

    @patch('daemon.component_pipeline.generate_component')
    def test_001_passes_the_configured_provider_and_model_through(self, mock_generate):
        daemon.CONFIG['llm_provider'] = "google"
        daemon.CONFIG['llm_model'] = "gemini-flash"
        daemon.CONFIG['secrets'] = {"google_api_key": "fake"}
        mock_generate.return_value = {"part_number": "ATtiny85"}

        daemon.kicad_generate_component("ATtiny85")

        _, kwargs = mock_generate.call_args
        self.assertEqual(kwargs['provider'], "google")
        self.assertEqual(kwargs['model'], "gemini-flash")
        self.assertEqual(kwargs['secrets'], {"google_api_key": "fake"})

    @patch('daemon.component_pipeline.generate_component')
    def test_002_nothing_configured_passes_none_through_not_a_forced_default(self, mock_generate):
        """Leaves the extraction agent's own prompt-file default intact
        on a fresh install -- must not regress that by forcing some other
        default here."""
        daemon.CONFIG['llm_provider'] = None
        daemon.CONFIG['llm_model'] = None
        mock_generate.return_value = {"part_number": "ATtiny85"}

        daemon.kicad_generate_component("ATtiny85")

        _, kwargs = mock_generate.call_args
        self.assertIsNone(kwargs['provider'])
        self.assertIsNone(kwargs['model'])


class TestComponentSearchAndCacheDatasheetRoutes(unittest.TestCase):
    """CTX-306.1: component.search threads CONFIG's provider/model
    through exactly like kicad_generate_component does (mirrors
    TestKicadGenerateComponentProviderOverride); component.cache_datasheet
    is a thin, one-line delegation to library_store, matching every
    other library.*/project.* wrapper's own shape."""

    def setUp(self):
        self._original_config = dict(daemon.CONFIG)

    def tearDown(self):
        daemon.CONFIG.clear()
        daemon.CONFIG.update(self._original_config)

    @patch('daemon.component_pipeline.search_components')
    def test_001_component_search_passes_the_configured_provider_and_model_through(self, mock_search):
        daemon.CONFIG['llm_provider'] = "google"
        daemon.CONFIG['llm_model'] = "gemini-flash"
        daemon.CONFIG['secrets'] = {"google_api_key": "fake"}
        mock_search.return_value = [{"part_number": "ATtiny85"}]

        daemon.component_search("atiny85")

        args, kwargs = mock_search.call_args
        self.assertEqual(args[0], "atiny85")
        self.assertEqual(kwargs['provider'], "google")
        self.assertEqual(kwargs['model'], "gemini-flash")
        self.assertEqual(kwargs['secrets'], {"google_api_key": "fake"})

    @patch('daemon.component_pipeline.search_components')
    def test_002_nothing_configured_passes_none_through_not_a_forced_default(self, mock_search):
        daemon.CONFIG['llm_provider'] = None
        daemon.CONFIG['llm_model'] = None
        mock_search.return_value = [{"part_number": "ATtiny85"}]

        daemon.component_search("atiny85")

        _, kwargs = mock_search.call_args
        self.assertIsNone(kwargs['provider'])
        self.assertIsNone(kwargs['model'])

    @patch('daemon.library_store.cache_datasheet')
    def test_003_cache_datasheet_delegates_and_wraps_the_path_in_a_result_dict(self, mock_cache):
        mock_cache.return_value = "/fake/library/datasheets/ATtiny85.pdf"

        result = daemon.component_cache_datasheet("ATtiny85", "https://example.com/x.pdf")

        mock_cache.assert_called_once_with("ATtiny85", "https://example.com/x.pdf")
        self.assertEqual(result, {"path": "/fake/library/datasheets/ATtiny85.pdf"})


class TestKicadSearchFootprintsRoute(unittest.TestCase):
    """CTX-308.1/CTX-308.4: kicad.search_footprints is real filesystem
    I/O (fp-lib-table + a user's own saved library, no kipy IPC call
    involved at all), deliberately NOT in ASYNC_ROUTES, unlike every
    other kicad.*/freecad.* route."""

    @patch('daemon.library_store.search_footprints')
    @patch('daemon.fp_lib_table.search_footprints')
    def test_001_dispatched_through_handle_request_returns_synchronously_not_as_a_job(self, mock_kicad_search, mock_saved_search):
        mock_kicad_search.return_value = [{"library": "MyPCBLibs", "footprint_name": "MP1584EN_5V_Module"}]
        mock_saved_search.return_value = []

        request = json.dumps({"jsonrpc": "2.0", "method": "kicad.search_footprints", "params": {"query": "MP1584"}, "id": "req_1"})
        response = json.loads(handle_request(request))

        mock_kicad_search.assert_called_once_with("MP1584")
        self.assertNotIn("job_id", response.get("result", {}))
        self.assertEqual(response["result"], [
            {"library": "MyPCBLibs", "footprint_name": "MP1584EN_5V_Module", "source": "kicad_library"},
        ])

    @patch('daemon.library_store.search_footprints')
    @patch('daemon.fp_lib_table.search_footprints')
    def test_003_merges_both_sources_kicad_installed_first(self, mock_kicad_search, mock_saved_search):
        """TEST-003: real merge of both real sources, KiCad-installed
        results first per PRODUCT-PLAN.md's own stated ranking, each
        tagged with a real source field."""
        mock_kicad_search.return_value = [{"library": "Battery", "footprint_name": "BatteryHolder_X"}]
        mock_saved_search.return_value = [
            {"footprint_id": "MyPCBLibs__MP1584EN_5V_Module", "library": "MyPCBLibs", "footprint_name": "MP1584EN_5V_Module"},
        ]

        result = daemon.kicad_search_footprints("battery")

        self.assertEqual(result, [
            {"library": "Battery", "footprint_name": "BatteryHolder_X", "source": "kicad_library"},
            {"library": "MyPCBLibs", "footprint_name": "MP1584EN_5V_Module", "source": "your_library"},
        ])

    @patch('daemon.fp_lib_table.search_footprints')
    def test_003b_missing_library_store_degrades_to_kicad_only_results(self, mock_kicad_search):
        """TEST-003: library_store failing to import must not take down
        kicad.search_footprints entirely -- mirrors every other route's
        own graceful-degradation pattern in this file."""
        mock_kicad_search.return_value = [{"library": "Battery", "footprint_name": "BatteryHolder_X"}]
        original = daemon.library_store
        daemon.library_store = None
        try:
            result = daemon.kicad_search_footprints("battery")
        finally:
            daemon.library_store = original

        self.assertEqual(result, [{"library": "Battery", "footprint_name": "BatteryHolder_X", "source": "kicad_library"}])

    def test_002_build_routes_omits_it_when_fp_lib_table_import_failed(self):
        original = daemon.fp_lib_table
        daemon.fp_lib_table = None
        try:
            routes = daemon._build_routes()
            self.assertNotIn("kicad.search_footprints", routes)
            self.assertIn("job.cancel", routes)
        finally:
            daemon.fp_lib_table = original


class TestKicadGenerateFootprintFromPartRoute(unittest.TestCase):
    """CTX-308.5: PRODUCT-PLAN.md §8 item 3's third footprint source
    (datasheet generation). No mocking of the geometry itself -- this
    reuses kicad_write.generate_pad_layout, a pure function with no kipy
    live-connection dependency, so real file I/O against a real temp
    storage_root is the honest verification, matching TestLibraryRoutes'
    own pattern rather than mocking what's actually cheap to run for
    real."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        daemon.library_store.configure(storage_root=self._tmpdir.name)

    def tearDown(self):
        daemon.library_store.configure(storage_root=None)
        self._tmpdir.cleanup()

    def _dispatch(self, method, params):
        request = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": "req"})
        return json.loads(handle_request(request))

    def test_001_generates_real_pads_matching_kicad_write_directly(self):
        """A saved Part (with CTX-308.5's now-persisted package_dimensions/
        courtyard) round-trips through the real route to a real Footprint
        record whose pads exactly match calling kicad_write.generate_pad_layout
        directly -- no second, possibly-drifted computation."""
        candidate = {
            "part_number": "ATtiny85", "manufacturer": "Microchip",
            "datasheet_url": "https://example.com/attiny85.pdf", "confidence": "high",
        }
        extraction = {
            "part_number": "ATtiny85",
            "package": "SOIC-8",
            "pins": [{"number": str(i), "name": f"P{i}", "electrical_type": "passive"} for i in range(1, 9)],
            "package_dimensions": {"length_mm": 4.9, "width_mm": 3.9, "height_mm": 1.75, "pitch_mm": 1.27},
            "courtyard": {"length_mm": 5.4, "width_mm": 4.4},
        }
        saved = self._dispatch(
            "library.save_confirmed_part", {"candidate": candidate, "extraction": extraction},
        )
        self.assertNotIn("error", saved)

        response = self._dispatch("kicad.generate_footprint_from_part", {"part_id": "ATtiny85"})
        self.assertNotIn("error", response)
        footprint = response["result"]

        expected_pads = daemon.kicad_write.generate_pad_layout(
            "SOIC-8", [str(i) for i in range(1, 9)], extraction["package_dimensions"],
        )
        self.assertEqual(footprint["footprint_id"], "generated__ATtiny85")
        self.assertEqual(footprint["pads"], expected_pads)
        self.assertEqual(footprint["courtyard"], extraction["courtyard"])
        self.assertEqual(footprint["provenance"]["source"], "datasheet_generation")
        self.assertEqual(footprint["provenance"]["generated_from_part_id"], "ATtiny85")
        self.assertFalse(footprint["provenance"]["verified"])

        # Immediately reusable through source two's own search (CTX-308.4) --
        # a generated footprint isn't a dead end, it's real saved-library content.
        found = daemon.library_store.search_footprints("SOIC-8")
        self.assertEqual([f["footprint_id"] for f in found], ["generated__ATtiny85"])

    def test_002_a_part_missing_datasheet_dimensions_fails_closed_not_a_crash(self):
        """A Part saved before CTX-308.5 (or any other way package_dimensions
        ends up falsy) must return a clean route error naming the real
        reason, not a raw KeyError from deep inside generate_pad_layout."""
        provenance = {
            field: {"source": "manual"} for field in daemon.library_store.PART_PROVENANCE_REQUIRED_FIELDS
        }
        part = {
            "part_id": "OldPart", "manufacturer": "Acme", "package": "SOIC-8",
            "pins": [{"number": "1", "name": "P1", "electrical_type": "passive"}],
            "datasheet_url": "https://example.com/x.pdf",
            "package_dimensions": None, "courtyard": None,
            "provenance": provenance,
        }
        saved = self._dispatch("library.save_part", {"part": part})
        self.assertNotIn("error", saved)

        response = self._dispatch("kicad.generate_footprint_from_part", {"part_id": "OldPart"})
        self.assertIn("error", response)
        self.assertIn("package_dimensions", response["error"]["message"])

    def test_003_an_unsupported_package_fails_closed_not_a_silent_guess(self):
        """TQFP-32 is real (in component_pipeline.PACKAGE_REFERENCE) but
        outside kicad_write.SUPPORTED_PACKAGES -- must surface as a clean
        route error, the same fail-closed choice generate_pad_layout
        already makes internally."""
        candidate = {
            "part_number": "STM32F103", "manufacturer": "ST",
            "datasheet_url": "https://example.com/stm32.pdf", "confidence": "high",
        }
        extraction = {
            "part_number": "STM32F103",
            "package": "TQFP-32",
            "pins": [{"number": str(i), "name": f"P{i}", "electrical_type": "passive"} for i in range(1, 33)],
            "package_dimensions": {"length_mm": 7.0, "width_mm": 7.0, "height_mm": 1.4, "pitch_mm": 0.8},
            "courtyard": {"length_mm": 7.5, "width_mm": 7.5},
        }
        saved = self._dispatch(
            "library.save_confirmed_part", {"candidate": candidate, "extraction": extraction},
        )
        self.assertNotIn("error", saved)

        response = self._dispatch("kicad.generate_footprint_from_part", {"part_id": "STM32F103"})
        self.assertIn("error", response)
        self.assertIn("No pad-layout generator", response["error"]["message"])

    def test_004_build_routes_omits_it_when_kicad_write_import_failed(self):
        original = daemon.kicad_write
        daemon.kicad_write = None
        try:
            routes = daemon._build_routes()
            self.assertNotIn("kicad.generate_footprint_from_part", routes)
            self.assertIn("job.cancel", routes)
        finally:
            daemon.kicad_write = original


class TestKicadGenerateConnectionGuidanceRoute(unittest.TestCase):
    """CTX-308.7: SPEC-308's third named concern (decoupling, protection,
    power). A real LLM call, so the pipeline call itself is mocked here
    (matching TestKicadGenerateComponentProviderOverride's own
    precedent) -- component_pipeline.TestRealGenerateConnectionGuidance
    is where the real, non-mocked model call is verified. What this
    class verifies is the daemon-level wiring: real part loading and
    real provider/model/secrets threading."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        daemon.library_store.configure(storage_root=self._tmpdir.name)
        self._original_config = dict(daemon.CONFIG)

    def tearDown(self):
        daemon.library_store.configure(storage_root=None)
        self._tmpdir.cleanup()
        daemon.CONFIG.clear()
        daemon.CONFIG.update(self._original_config)

    @patch('daemon.component_pipeline.generate_connection_guidance')
    def test_001_loads_the_real_part_and_passes_its_real_fields_through(self, mock_guidance):
        pins = [{"number": "8", "name": "VCC", "electrical_type": "power"}]
        daemon.library_store.save_part({
            "part_id": "ATtiny85", "manufacturer": "Microchip", "package": "SOIC-8", "pins": pins,
            "datasheet_url": "https://example.com/x.pdf", "package_dimensions": {}, "courtyard": {},
            "provenance": {f: {"source": "test"} for f in daemon.library_store.PART_PROVENANCE_REQUIRED_FIELDS},
        })
        daemon.CONFIG['llm_provider'] = "google"
        daemon.CONFIG['llm_model'] = "gemini-flash"
        daemon.CONFIG['secrets'] = {"google_api_key": "fake"}
        mock_guidance.return_value = {"pin_guidance": [], "general_notes": ""}

        daemon.kicad_generate_connection_guidance("ATtiny85")

        args, kwargs = mock_guidance.call_args
        self.assertEqual(args, ("ATtiny85", "SOIC-8", pins))
        self.assertEqual(kwargs['provider'], "google")
        self.assertEqual(kwargs['model'], "gemini-flash")
        self.assertEqual(kwargs['secrets'], {"google_api_key": "fake"})

    def test_002_build_routes_omits_it_when_component_pipeline_import_failed(self):
        original = daemon.component_pipeline
        daemon.component_pipeline = None
        try:
            routes = daemon._build_routes()
            self.assertNotIn("kicad.generate_connection_guidance", routes)
            self.assertIn("job.cancel", routes)
        finally:
            daemon.component_pipeline = original

    def test_003_registered_as_an_async_route(self):
        self.assertIn("kicad.generate_connection_guidance", daemon.ASYNC_ROUTES)


_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
_EMPTY_BOARD_FIXTURE = os.path.join(_FIXTURES_DIR, 'empty_board.kicad_pcb')
_EMPTY_SCHEMATIC_FIXTURE = os.path.join(_FIXTURES_DIR, 'empty_schematic.kicad_sch')


class TestKicadCheckBoardRoute(unittest.TestCase):
    """CTX-309.1: SPEC-309's DRC route."""

    def test_001_no_path_given_and_nothing_open_raises_a_clean_error(self):
        with patch('daemon.kicad_bridge.get_open_board_path', return_value=None):
            with self.assertRaises(daemon.kicad_cli.KicadCliError) as ctx:
                daemon.kicad_check_board()
            self.assertIn("No board is currently open", str(ctx.exception))

    def test_002_no_path_given_auto_resolves_the_currently_open_board(self):
        """Routing only -- kicad_cli.run_drc/component_pipeline.
        explain_violations are both mocked here; TestRealKicadCheckBoardRoute
        below is the real, non-mocked end-to-end version."""
        with patch('daemon.kicad_bridge.get_open_board_path', return_value='/real/open/board.kicad_pcb'), \
             patch('daemon.kicad_cli.run_drc', return_value={"violations": []}) as mock_run_drc, \
             patch('daemon.component_pipeline.explain_violations', return_value={"violations": [], "summary": "clean", "truncated_count": 0}):
            result = daemon.kicad_check_board()

        mock_run_drc.assert_called_once_with('/real/open/board.kicad_pcb')
        self.assertEqual(result["source_path"], '/real/open/board.kicad_pcb')

    def test_003_an_explicit_path_skips_auto_resolution_entirely(self):
        with patch('daemon.kicad_bridge.get_open_board_path') as mock_get_open, \
             patch('daemon.kicad_cli.run_drc', return_value={"violations": []}), \
             patch('daemon.component_pipeline.explain_violations', return_value={"violations": [], "summary": "clean", "truncated_count": 0}):
            daemon.kicad_check_board(pcb_path='/explicit/path.kicad_pcb')

        mock_get_open.assert_not_called()

    def test_004_build_routes_omits_it_when_kicad_bridge_import_failed(self):
        original = daemon.kicad_bridge
        daemon.kicad_bridge = None
        try:
            routes = daemon._build_routes()
            self.assertNotIn("kicad.check_board", routes)
            self.assertIn("kicad.check_schematic", routes, "no auto-resolution dependency on kicad_bridge")
        finally:
            daemon.kicad_bridge = original

    def test_005_build_routes_omits_both_when_kicad_cli_import_failed(self):
        original = daemon.kicad_cli
        daemon.kicad_cli = None
        try:
            routes = daemon._build_routes()
            self.assertNotIn("kicad.check_board", routes)
            self.assertNotIn("kicad.check_schematic", routes)
        finally:
            daemon.kicad_cli = original

    def test_006_both_registered_as_async_routes(self):
        self.assertIn("kicad.check_board", daemon.ASYNC_ROUTES)
        self.assertIn("kicad.check_schematic", daemon.ASYNC_ROUTES)


class TestKicadCheckSchematicRoute(unittest.TestCase):
    """CTX-309.1: SPEC-309's ERC route -- always an explicit path, no
    auto-resolution (SPEC-309 §2's own confirmed, real IPC limitation)."""

    def test_001_flattens_violations_across_sheets_tagged_with_their_real_sheet_path(self):
        fake_report = {
            "sheets": [
                {"path": "/", "violations": [{"description": "v1", "severity": "error", "type": "t1"}]},
                {"path": "/sub", "violations": [{"description": "v2", "severity": "warning", "type": "t2"}]},
            ],
        }
        with patch('daemon.kicad_cli.run_erc', return_value=fake_report) as mock_run_erc, \
             patch('daemon.component_pipeline.explain_violations') as mock_explain:
            mock_explain.return_value = {"violations": [], "summary": "s", "truncated_count": 0}
            daemon.kicad_check_schematic('/real/board.kicad_sch')

        mock_run_erc.assert_called_once_with('/real/board.kicad_sch')
        flattened = mock_explain.call_args[0][0]
        self.assertEqual(len(flattened), 2)
        self.assertEqual(flattened[0]["sheet_path"], "/")
        self.assertEqual(flattened[1]["sheet_path"], "/sub")

    def test_002_real_end_to_end_against_the_committed_clean_fixture(self):
        """Real kicad_cli.run_erc, real explain_violations short-circuit
        (0 violations, TestExplainViolations.test_000 already covers
        that this never calls an LLM) -- no ANTHROPIC_API_KEY needed for
        this particular real path. Skips cleanly if kicad-cli isn't on
        this machine."""
        if not daemon.kicad_cli:
            self.skipTest("kicad_cli module unavailable.")
        try:
            daemon.kicad_cli.find_kicad_cli()
        except daemon.kicad_cli.KicadCliUnavailableError:
            self.skipTest("kicad-cli not found on this machine.")

        result = daemon.kicad_check_schematic(_EMPTY_SCHEMATIC_FIXTURE)

        self.assertEqual(result["violations"], [])
        self.assertEqual(result["source_path"], _EMPTY_SCHEMATIC_FIXTURE)


class TestRealKicadCheckBoardRoute(unittest.TestCase):
    """Real, non-mocked end-to-end: real kicad-cli DRC against the
    committed empty_board.kicad_pcb fixture (a real, deterministic
    invalid_outline violation), then a real LLM call to explain it."""

    def test_001_real_drc_plus_real_explanation_for_the_real_committed_fixture(self):
        if not daemon.kicad_cli:
            self.skipTest("kicad_cli module unavailable.")
        try:
            daemon.kicad_cli.find_kicad_cli()
        except daemon.kicad_cli.KicadCliUnavailableError:
            self.skipTest("kicad-cli not found on this machine.")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        original_config = dict(daemon.CONFIG)
        daemon.CONFIG["secrets"] = {"anthropic_api_key": api_key}
        try:
            result = daemon.kicad_check_board(pcb_path=_EMPTY_BOARD_FIXTURE)
        finally:
            daemon.CONFIG.clear()
            daemon.CONFIG.update(original_config)

        self.assertEqual(result["source_path"], _EMPTY_BOARD_FIXTURE)
        self.assertEqual(len(result["violations"]), 1)
        self.assertEqual(result["violations"][0]["type"], "invalid_outline")
        self.assertTrue(result["violations"][0]["explanation"])
        self.assertTrue(result["violations"][0]["suggested_fix"])


_FAKE_OUTLINE = {"x_mm": 0.0, "y_mm": 0.0, "width_mm": 20.0, "height_mm": 15.0}
_FAKE_HOLES = [
    {"x_mm": 2.0, "y_mm": 2.0, "diameter_mm": 3.2, "recognized": True},
    {"x_mm": 18.0, "y_mm": 13.0, "diameter_mm": 1.0, "recognized": False},
]


class TestFreecadGenerateEnclosureRoute(unittest.TestCase):
    """CTX-109.1: freecad_generate_enclosure composes kicad_bridge's
    board-read functions with freecad_bridge.generate_enclosure's real
    geometry -- these tests cover the composition/routing logic itself
    (mode selection, recognized-holes filtering, artifact persistence);
    the real geometry those calls produce is already verified against a
    real freecadcmd in TestBoardDrivenEnclosure (test_freecad_bridge.py)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        daemon.library_store.configure(storage_root=self._tmpdir.name)

    def tearDown(self):
        daemon.library_store.configure(storage_root=None)
        self._tmpdir.cleanup()

    @patch('daemon.generate_enclosure')
    @patch('daemon.kicad_bridge.get_board_outline')
    def test_001_manual_dims_never_touch_kicad_bridge_even_with_a_live_connection(
        self, mock_get_outline, mock_generate,
    ):
        """TEST-010: a caller who explicitly supplied width/depth is
        never silently overridden with board data -- mode selection is
        explicit, not connection-sniffed."""
        mock_generate.return_value = {"glb_path": "/tmp/e.glb", "step_path": "/tmp/e.step"}

        daemon.freecad_generate_enclosure(height=20, width=50, depth=30)

        mock_get_outline.assert_not_called()
        _, kwargs = mock_generate.call_args
        self.assertIsNone(kwargs["board_outline"])
        self.assertEqual(kwargs["width"], 50)
        self.assertEqual(kwargs["depth"], 30)

    @patch('daemon.generate_enclosure')
    @patch('daemon.kicad_bridge.get_mounting_holes', return_value=_FAKE_HOLES)
    @patch('daemon.kicad_bridge.get_board_outline', return_value=_FAKE_OUTLINE)
    def test_002_omitting_width_and_depth_reads_real_board_data(
        self, mock_get_outline, mock_get_holes, mock_generate,
    ):
        """TEST-008: omitting width/depth is the real, explicit signal to
        read a live board -- SPEC-109 §2's board-driven mode."""
        mock_generate.return_value = {"glb_path": "/tmp/e.glb", "step_path": "/tmp/e.step"}

        daemon.freecad_generate_enclosure(height=20)

        mock_get_outline.assert_called_once()
        mock_get_holes.assert_called_once()
        _, kwargs = mock_generate.call_args
        self.assertEqual(kwargs["board_outline"], _FAKE_OUTLINE)

    @patch('daemon.generate_enclosure')
    @patch('daemon.kicad_bridge.get_mounting_holes', return_value=_FAKE_HOLES)
    @patch('daemon.kicad_bridge.get_board_outline', return_value=_FAKE_OUTLINE)
    def test_003_only_recognized_holes_become_real_standoffs_but_unrecognized_ones_are_still_reported(
        self, mock_get_outline, mock_get_holes, mock_generate,
    ):
        """TEST-009: the unrecognized hole in _FAKE_HOLES must not become
        a standoff (the real physical risk SPEC-109 §3 names), but must
        not be silently dropped either -- the whole build must not fail
        over it."""
        mock_generate.return_value = {"glb_path": "/tmp/e.glb", "step_path": "/tmp/e.step"}

        result = daemon.freecad_generate_enclosure(height=20)

        _, kwargs = mock_generate.call_args
        self.assertEqual(len(kwargs["standoffs"]), 1)
        self.assertEqual(kwargs["standoffs"][0]["x_mm"], 2.0)
        self.assertEqual(result["unrecognized_holes"], [_FAKE_HOLES[1]])

    @patch('daemon.generate_enclosure')
    @patch('daemon.kicad_bridge.get_mounting_holes', return_value=_FAKE_HOLES)
    @patch('daemon.kicad_bridge.get_board_outline', return_value=_FAKE_OUTLINE)
    def test_004_project_name_saves_a_real_enclosure_artifact_with_a_real_board_revision(
        self, mock_get_outline, mock_get_holes, mock_generate,
    ):
        """TEST-008: for the first time, an enclosure Artifact is
        actually saved -- closing the board_revision requirement
        library_store.py has enforced since CTX-304.1 but nothing has
        ever called save_artifact against, for real (a real tmpdir
        storage root, not mocked)."""
        mock_generate.return_value = {"glb_path": "/tmp/e.glb", "step_path": "/tmp/e.step"}
        daemon.library_store.save_project({"name": "weather-pcb"})

        result = daemon.freecad_generate_enclosure(height=20, project_name="weather-pcb")

        self.assertIn("artifact_id", result)
        artifacts = daemon.library_store.list_artifacts("weather-pcb")
        self.assertEqual(artifacts, [result["artifact_id"]])
        loaded = daemon.library_store.load_artifact("weather-pcb", result["artifact_id"])
        self.assertEqual(loaded["kind"], "enclosure")
        self.assertTrue(loaded["board_revision"])

    @patch('daemon.generate_enclosure')
    @patch('daemon.kicad_bridge.get_mounting_holes', return_value=_FAKE_HOLES)
    @patch('daemon.kicad_bridge.get_board_outline', return_value=_FAKE_OUTLINE)
    def test_005_no_project_name_never_saves_an_artifact_matching_todays_frontend(
        self, mock_get_outline, mock_get_holes, mock_generate,
    ):
        """Today's App.tsx dims object never sends project_name -- this
        must keep working exactly as before, with no artifact saved."""
        mock_generate.return_value = {"glb_path": "/tmp/e.glb", "step_path": "/tmp/e.step"}

        result = daemon.freecad_generate_enclosure(height=20)

        self.assertNotIn("artifact_id", result)

    @patch('daemon.generate_enclosure')
    def test_006_manual_mode_board_revision_is_a_real_honest_sentinel(self, mock_generate):
        """The no-board-data fallback has no real board to hash -- the
        sentinel must say so honestly, not fabricate a hash implying real
        board data was read."""
        mock_generate.return_value = {"glb_path": "/tmp/e.glb", "step_path": "/tmp/e.step"}
        daemon.library_store.save_project({"name": "weather-pcb"})

        result = daemon.freecad_generate_enclosure(
            height=20, width=50, depth=30, project_name="weather-pcb",
        )

        loaded = daemon.library_store.load_artifact("weather-pcb", result["artifact_id"])
        self.assertEqual(loaded["board_revision"], "manual:50x30x20")


class TestFreecadGenerateEnclosurePcbPathMode(unittest.TestCase):
    """CTX-310.1: the file-based mode SPEC-310 adds -- composes
    kicad_pcb_import's file-based outline/hole extraction the same way
    TestFreecadGenerateEnclosureRoute's live-mode tests already cover
    kicad_bridge; the real DXF/Excellon parsing itself is already
    verified for real in test_kicad_pcb_import.py."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        daemon.library_store.configure(storage_root=self._tmpdir.name)

    def tearDown(self):
        daemon.library_store.configure(storage_root=None)
        self._tmpdir.cleanup()

    @patch('daemon.generate_enclosure')
    @patch('daemon.kicad_pcb_import.extract_mounting_holes', return_value=_FAKE_HOLES)
    @patch('daemon.kicad_pcb_import.extract_board_outline', return_value=_FAKE_OUTLINE)
    @patch('daemon.kicad_bridge.get_board_outline')
    def test_001_pcb_path_reads_the_file_never_touches_kicad_bridge(
        self, mock_bridge_outline, mock_extract_outline, mock_extract_holes, mock_generate,
    ):
        """Mode selection is explicit (daemon.py's own fixed priority
        order, manual > file > live) -- a caller who passed pcb_path
        must never fall through to a live connection, even if one is
        open."""
        mock_generate.return_value = {"glb_path": "/tmp/e.glb", "step_path": "/tmp/e.step"}

        daemon.freecad_generate_enclosure(height=20, pcb_path='/real/board.kicad_pcb')

        mock_extract_outline.assert_called_once_with('/real/board.kicad_pcb')
        mock_extract_holes.assert_called_once_with('/real/board.kicad_pcb')
        mock_bridge_outline.assert_not_called()
        _, kwargs = mock_generate.call_args
        self.assertEqual(kwargs["board_outline"], _FAKE_OUTLINE)

    @patch('daemon.generate_enclosure')
    @patch('daemon.kicad_pcb_import.extract_mounting_holes', return_value=_FAKE_HOLES)
    @patch('daemon.kicad_pcb_import.extract_board_outline', return_value=_FAKE_OUTLINE)
    def test_002_every_file_mode_hole_becomes_a_standoff_none_are_unrecognized(
        self, mock_extract_outline, mock_extract_holes, mock_generate,
    ):
        """SPEC-310 §2's own real, accepted tradeoff: a drill file has no
        recognized/unrecognized signal at all, so file mode must never
        report an unrecognized hole -- unlike live mode's _FAKE_HOLES
        fixture, which has one."""
        mock_generate.return_value = {"glb_path": "/tmp/e.glb", "step_path": "/tmp/e.step"}

        result = daemon.freecad_generate_enclosure(height=20, pcb_path='/real/board.kicad_pcb')

        _, kwargs = mock_generate.call_args
        self.assertEqual(len(kwargs["standoffs"]), len(_FAKE_HOLES))
        self.assertEqual(result["unrecognized_holes"], [])

    @patch('daemon.generate_enclosure')
    @patch('daemon.kicad_pcb_import.extract_mounting_holes', return_value=_FAKE_HOLES)
    @patch('daemon.kicad_pcb_import.extract_board_outline', return_value=_FAKE_OUTLINE)
    def test_003_pcb_path_wins_over_a_live_connection_when_both_could_apply(
        self, mock_extract_outline, mock_extract_holes, mock_generate,
    ):
        mock_generate.return_value = {"glb_path": "/tmp/e.glb", "step_path": "/tmp/e.step"}
        daemon.library_store.save_project({"name": "weather-pcb"})

        result = daemon.freecad_generate_enclosure(
            height=20, pcb_path='/real/board.kicad_pcb', project_name="weather-pcb",
        )

        loaded = daemon.library_store.load_artifact("weather-pcb", result["artifact_id"])
        self.assertTrue(loaded["board_revision"].startswith("file:/real/board.kicad_pcb:"))

    def test_004_kicad_pcb_import_import_failure_raises_a_clean_error(self):
        original = daemon.kicad_pcb_import
        daemon.kicad_pcb_import = None
        try:
            with self.assertRaises(RuntimeError) as ctx:
                daemon.freecad_generate_enclosure(height=20, pcb_path='/real/board.kicad_pcb')
            self.assertIn("kicad_pcb_import", str(ctx.exception))
        finally:
            daemon.kicad_pcb_import = original


if __name__ == '__main__':
    unittest.main()
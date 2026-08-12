import io
import json
import threading
import time
import unittest
from unittest.mock import patch
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


if __name__ == '__main__':
    unittest.main()
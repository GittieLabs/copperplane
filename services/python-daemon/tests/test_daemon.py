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

    @patch('daemon.time.sleep', return_value=None)
    def test_001_valid_routing(self, mock_sleep):
        """TEST-001: Validates valid JSON-RPC parsing and routing"""
        request = json.dumps({
            "jsonrpc": "2.0",
            "method": "kicad.generate_component",
            "params": {"query": "esp32"},
            "id": "req_100"
        })
        
        response_str = handle_request(request)
        response = json.loads(response_str)
        
        self.assertEqual(response.get("jsonrpc"), "2.0")
        self.assertEqual(response.get("id"), "req_100")
        self.assertIn("result", response)
        self.assertNotIn("error", response)
        
        result = response["result"]
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["symbol_created"], "ESP32_symbol.kicad_sym")
        
        # Verify our mock sleep was actually called (to ensure route logic ran)
        mock_sleep.assert_called_once_with(1.5)

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

if __name__ == '__main__':
    unittest.main()
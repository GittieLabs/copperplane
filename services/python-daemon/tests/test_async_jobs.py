import json
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import daemon
from freecad_bridge import FreeCADUnavailableError, find_freecadcmd


class _RaceProneStdout:
    """A fake stdout whose write() splits its input in half and sleeps in
    between -- a real race window that would expose two threads
    interleaving their halves if daemon.emit() didn't hold a lock across
    the *entire* write+flush, not just each individual write() call."""

    def __init__(self):
        self.buffer = ""

    def write(self, s):
        if not s:
            return
        mid = len(s) // 2
        self.buffer += s[:mid]
        time.sleep(0.001)
        self.buffer += s[mid:]

    def flush(self):
        pass


class TestAsyncJobAtomicity(unittest.TestCase):

    def test_001_concurrent_emit_never_interleaves(self):
        """TEST-003: many threads calling emit() concurrently never
        interleave -- every line captured on stdout parses as exactly one
        complete JSON object."""
        fake_stdout = _RaceProneStdout()
        original_stdout = sys.stdout
        sys.stdout = fake_stdout
        try:
            def worker(n):
                daemon.emit({"jsonrpc": "2.0", "method": "test.notify", "params": {"n": n}})

            threads = [threading.Thread(target=worker, args=(n,)) for n in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        finally:
            sys.stdout = original_stdout

        lines = [line for line in fake_stdout.buffer.split("\n") if line]
        self.assertEqual(len(lines), 20, "expected exactly one uncorrupted line per thread")

        seen_ns = set()
        for line in lines:
            parsed = json.loads(line)  # raises ValueError if a line was interleaved/corrupted
            seen_ns.add(parsed["params"]["n"])
        self.assertEqual(seen_ns, set(range(20)))


class TestAsyncJobLifecycle(unittest.TestCase):

    def test_001_progress_then_completed_with_matching_job_id(self):
        """TEST-004: a full async job lifecycle through handle_request
        emits job.progress then job.completed, both carrying the same
        job_id."""
        captured = []
        original_write_line = daemon._write_line
        daemon._write_line = lambda text: captured.append(json.loads(text))

        daemon.ROUTES['test.echo'] = lambda value: {"echoed": value}
        daemon.ASYNC_ROUTES.add('test.echo')
        try:
            request = json.dumps({
                "jsonrpc": "2.0", "method": "test.echo", "params": {"value": "hi"}, "id": "req_1"
            })
            response = json.loads(daemon.handle_request(request))
            job_id = response["result"]["job_id"]

            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                methods = [
                    n.get("method") for n in captured
                    if n.get("params", {}).get("job_id") == job_id
                ]
                if "job.completed" in methods:
                    break
                time.sleep(0.01)
        finally:
            daemon._write_line = original_write_line
            daemon.ROUTES.pop('test.echo', None)
            daemon.ASYNC_ROUTES.discard('test.echo')

        job_notifications = [n for n in captured if n.get("params", {}).get("job_id") == job_id]
        methods_in_order = [n["method"] for n in job_notifications]
        self.assertEqual(methods_in_order, ["job.progress", "job.completed"])
        self.assertEqual(job_notifications[-1]["params"]["result"], {"echoed": "hi"})


class TestRealCancellation(unittest.TestCase):

    def test_001_cancelling_a_real_job_reports_job_cancelled(self):
        """TEST-005: submitting a real freecad.generate_enclosure job and
        immediately cancelling it actually stops it -- the daemon reports
        job.cancelled, not job.completed or job.failed. Skips itself
        (rather than failing) when no freecadcmd is found, e.g. in CI.

        This has a small, inherent race: cancel_event.set() must land
        before the real freecadcmd subprocess finishes on its own. In
        practice the cancel call fires within microseconds of the job
        being submitted, well inside the process-spawn + FreeCAD-init
        window CTX-104.1 measured in the seconds, but it is not
        impossible for a very fast machine to finish first -- see
        Plan Drift."""
        try:
            find_freecadcmd()
        except FreeCADUnavailableError:
            self.skipTest(
                "No local freecadcmd found. Install FreeCAD 0.20+ to run this "
                "test for real."
            )

        captured = []
        original_write_line = daemon._write_line
        daemon._write_line = lambda text: captured.append(json.loads(text))
        try:
            submit_request = json.dumps({
                "jsonrpc": "2.0",
                "method": "freecad.generate_enclosure",
                "params": {"width": 50, "depth": 30, "height": 20},
                "id": "req_submit",
            })
            response = json.loads(daemon.handle_request(submit_request))
            job_id = response["result"]["job_id"]

            cancel_request = json.dumps({
                "jsonrpc": "2.0",
                "method": "job.cancel",
                "params": {"job_id": job_id},
                "id": "req_cancel",
            })
            cancel_response = json.loads(daemon.handle_request(cancel_request))
            self.assertNotIn("error", cancel_response)

            deadline = time.monotonic() + 10.0
            terminal_notification = None
            while time.monotonic() < deadline:
                for n in captured:
                    if (
                        n.get("params", {}).get("job_id") == job_id
                        and n["method"] in ("job.completed", "job.failed", "job.cancelled")
                    ):
                        terminal_notification = n
                        break
                if terminal_notification:
                    break
                time.sleep(0.05)
        finally:
            daemon._write_line = original_write_line

        self.assertIsNotNone(terminal_notification, "job never reached a terminal state within 10s")
        self.assertEqual(
            terminal_notification["method"],
            "job.cancelled",
            f"expected job.cancelled, got {terminal_notification!r} -- the real freecadcmd "
            f"process may have finished before the cancel_event was noticed",
        )


class TestRealLLMChatJob(unittest.TestCase):

    def test_001_llm_chat_dispatched_through_handle_request_reports_job_completed(self):
        """TEST-006 (CTX-201.1): llm.chat, submitted through handle_request
        exactly like a real client would, returns a job_id immediately and
        reports job.completed with the real provider's response text --
        proving the full route/param-resolution/async-dispatch wiring, not
        just llm_providers.chat in isolation (test_llm_providers.py). Uses
        Ollama since it needs no API key and is always available locally
        on a machine with it installed; skips itself cleanly otherwise."""
        import httpx

        try:
            httpx.get("http://localhost:11434/api/version", timeout=1.0).raise_for_status()
        except Exception:
            self.skipTest("No local Ollama server reachable at localhost:11434.")

        captured = []
        original_write_line = daemon._write_line
        daemon._write_line = lambda text: captured.append(json.loads(text))
        try:
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "llm.chat",
                "params": {
                    "prompt": "Reply with exactly one word: pong",
                    "provider": "ollama",
                },
                "id": "req_llm_chat",
            })
            response = json.loads(daemon.handle_request(request))
            self.assertNotIn("error", response)
            job_id = response["result"]["job_id"]

            deadline = time.monotonic() + 30.0
            terminal_notification = None
            while time.monotonic() < deadline:
                for n in captured:
                    if (
                        n.get("params", {}).get("job_id") == job_id
                        and n["method"] in ("job.completed", "job.failed")
                    ):
                        terminal_notification = n
                        break
                if terminal_notification:
                    break
                time.sleep(0.1)
        finally:
            daemon._write_line = original_write_line

        self.assertIsNotNone(terminal_notification, "llm.chat job never reached a terminal state within 30s")
        self.assertEqual(terminal_notification["method"], "job.completed")
        self.assertIsInstance(terminal_notification["params"]["result"], str)
        self.assertGreater(len(terminal_notification["params"]["result"].strip()), 0)


class TestRealComponentGenerationJob(unittest.TestCase):

    def _load_dotenv_local(self):
        import os

        path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env.local'))
        if not os.path.exists(path):
            return
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

    def test_001_kicad_generate_component_dispatched_through_handle_request_reports_job_completed(self):
        """TEST-007 (CTX-202.1): kicad.generate_component, submitted
        through handle_request exactly as a real client would, returns a
        job_id immediately and reports job.completed with the real,
        validated component schema -- proving the full route/param-
        resolution/async-dispatch/secrets-passthrough chain, not just
        component_pipeline.generate_component in isolation. Skips itself
        cleanly when no real ANTHROPIC_API_KEY is available."""
        self._load_dotenv_local()
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        original_secrets = daemon.CONFIG.get("secrets")
        daemon.CONFIG["secrets"] = {"anthropic_api_key": api_key}

        captured = []
        original_write_line = daemon._write_line
        daemon._write_line = lambda text: captured.append(json.loads(text))
        try:
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "kicad.generate_component",
                "params": {"part_number": "ATtiny85"},
                "id": "req_generate_component",
            })
            response = json.loads(daemon.handle_request(request))
            self.assertNotIn("error", response)
            job_id = response["result"]["job_id"]

            deadline = time.monotonic() + 30.0
            terminal_notification = None
            while time.monotonic() < deadline:
                for n in captured:
                    if (
                        n.get("params", {}).get("job_id") == job_id
                        and n["method"] in ("job.completed", "job.failed")
                    ):
                        terminal_notification = n
                        break
                if terminal_notification:
                    break
                time.sleep(0.1)
        finally:
            daemon._write_line = original_write_line
            daemon.CONFIG["secrets"] = original_secrets

        self.assertIsNotNone(
            terminal_notification, "kicad.generate_component job never reached a terminal state within 30s"
        )
        self.assertEqual(terminal_notification["method"], "job.completed")
        schema = terminal_notification["params"]["result"]
        self.assertEqual(schema["part_number"], "ATtiny85")
        self.assertIn("pins", schema)


if __name__ == '__main__':
    unittest.main()

import json
import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import daemon
from freecad_bridge import FreeCADUnavailableError, find_freecadcmd
from tests.test_library_store import _OneShotServer


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

    def test_002_llm_chat_history_dispatched_through_handle_request_actually_uses_prior_context(self):
        """TEST-006 (CTX-302.1): llm.chat's new `history` parameter,
        submitted through handle_request exactly as the real chat UI
        does, proving the full route/param-resolution/async-dispatch
        chain -- not just llm_providers.chat's own history handling in
        isolation (test_llm_providers.py). Uses Anthropic, not Ollama:
        a real run found `llama3.2:1b` answers this exact prompt
        inconsistently (42/43/86 across repeated identical calls, even
        bypassing the daemon entirely) -- genuine model unreliability,
        not a wiring bug, the same class of finding CTX-202.1 already
        documented for this model. Skips cleanly without a real key."""
        import os

        dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env.local'))
        if os.path.exists(dotenv_path):
            with open(dotenv_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, _, value = line.partition('=')
                    os.environ.setdefault(key.strip(), value.strip())

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
                "method": "llm.chat",
                "params": {
                    "prompt": "What is my favorite number? Reply with only the number.",
                    "provider": "anthropic",
                    "history": [
                        {"role": "user", "content": "My favorite number is 42."},
                        {"role": "assistant", "content": "Got it, I'll remember that."},
                    ],
                },
                "id": "req_llm_chat_history",
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

        self.assertIsNotNone(terminal_notification, "llm.chat job never reached a terminal state within 30s")
        self.assertEqual(terminal_notification["method"], "job.completed")
        self.assertIn("42", terminal_notification["params"]["result"])


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


class TestRealInjectComponentJob(unittest.TestCase):

    def test_001_kicad_inject_component_dispatched_through_handle_request_reports_job_completed(self):
        """TEST-005 (CTX-108.1): kicad.inject_component, submitted through
        handle_request exactly as a real client would, returns a job_id
        immediately and reports job.completed with the real write result
        -- proving the full route/param-resolution/async-dispatch chain
        against the actually-running KiCad, not just
        kicad_bridge.inject_component in isolation (test_kicad_bridge.py).

        board.save() is patched to a no-op for the whole test: this
        suite must never be able to persist a change to whatever real
        .kicad_pcb file a developer happens to have open, no matter what
        route triggered the write. The created footprint is removed
        from the live in-memory board afterward so it never accumulates
        across repeated runs of this suite within the same KiCad
        session. Skips itself cleanly when no live KiCad IPC socket is
        reachable, matching CTX-103.1/104.1 precedent."""
        from unittest.mock import patch

        # A real connection attempt, not a socket-file existence check:
        # macOS doesn't reliably unlink the socket file when KiCad exits,
        # so a stale leftover file would make this test fail for real
        # instead of skipping cleanly.
        import kicad_bridge

        try:
            kicad_bridge.get_client()
        except kicad_bridge.KiCadUnavailableError as e:
            self.skipTest(
                f"No live KiCad IPC connection reachable: {e} Enable the IPC "
                "API (Preferences > Plugins), launch KiCad, and open a board "
                "in the PCB Editor to run this test for real."
            )
        try:
            kicad_bridge.get_client().get_board()
        except Exception as e:
            self.skipTest(f"KiCad is running but no board is open in the PCB Editor: {e}")

        schema = {
            "part_number": "TEST-CTX-108-1",
            "package": "SOIC-8",
            "pins": [{"number": str(i), "name": f"P{i}", "electrical_type": "passive"} for i in range(1, 9)],
            "package_dimensions": {"length_mm": 4.9, "width_mm": 3.9, "height_mm": 1.75, "pitch_mm": 1.27},
            "courtyard": {"length_mm": 5.2, "width_mm": 4.2},
        }

        captured = []
        original_write_line = daemon._write_line
        daemon._write_line = lambda text: captured.append(json.loads(text))
        try:
            with patch('kipy.board.Board.save', return_value=None):
                request = json.dumps({
                    "jsonrpc": "2.0",
                    "method": "kicad.inject_component",
                    "params": {"schema": schema, "x_mm": 110, "y_mm": 110},
                    "id": "req_inject_component",
                })
                response = json.loads(daemon.handle_request(request))
                self.assertNotIn("error", response)
                job_id = response["result"]["job_id"]

                deadline = time.monotonic() + 15.0
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
            # Remove the footprint this test just created from the live,
            # in-memory board -- board.save() was patched out above, so
            # this never touched disk, but the in-memory session would
            # otherwise carry the test footprint into the next run.
            board = kicad_bridge.get_client().get_board()
            leftover = [f for f in board.get_footprints() if f.value_field.text.value == "TEST-CTX-108-1"]
            if leftover:
                cleanup_commit = board.begin_commit()
                board.remove_items_by_id([f.id for f in leftover])
                board.push_commit(cleanup_commit, "test cleanup")

        self.assertIsNotNone(
            terminal_notification, "kicad.inject_component job never reached a terminal state within 15s"
        )
        self.assertEqual(terminal_notification["method"], "job.completed")
        result = terminal_notification["params"]["result"]
        self.assertEqual(result["part_number"], "TEST-CTX-108-1")
        self.assertEqual(result["pins"], 8)


class TestRealDatasheetGenerateGuidanceJob(unittest.TestCase):
    """CTX-205.3: datasheet.generate_guidance, submitted through
    handle_request exactly as a real client would, returns a job_id
    immediately and reports job.completed with the real, cited,
    persisted guidance -- proving the full route/param-resolution/
    async-dispatch/secrets-passthrough chain, not just
    datasheet_guidance.generate_datasheet_guidance in isolation
    (test_datasheet_guidance.py) or the route function's own
    orchestration in isolation (test_daemon.py). A real local HTTP
    server serves CTX-205.1's own real fixture PDF -- no outside
    internet access required for this real fetch, matching
    TestCacheDatasheet's own established pattern. Skips itself cleanly
    when no real ANTHROPIC_API_KEY is available."""

    def _load_dotenv_local(self):
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

    def test_001_dispatched_through_handle_request_reports_job_completed_with_real_cited_guidance(self):
        self._load_dotenv_local()
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        tmpdir = tempfile.TemporaryDirectory()
        daemon.library_store.configure(storage_root=tmpdir.name)

        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_datasheet.pdf")
        with open(fixture_path, "rb") as f:
            fixture_bytes = f.read()
        server = _OneShotServer(200, fixture_bytes)

        original_secrets = daemon.CONFIG.get("secrets")
        daemon.CONFIG["secrets"] = {"anthropic_api_key": api_key}

        captured = []
        original_write_line = daemon._write_line
        daemon._write_line = lambda text: captured.append(json.loads(text))
        try:
            provenance = {f: {"source": "test"} for f in daemon.library_store.PART_PROVENANCE_REQUIRED_FIELDS}
            daemon.library_store.save_part({
                "part_id": "ATtiny85-real-guidance", "manufacturer": "Microchip", "package": "SOIC-8",
                "pins": [], "datasheet_url": server.url, "package_dimensions": {}, "courtyard": {},
                "provenance": provenance,
            })

            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "datasheet.generate_guidance",
                "params": {"part_id": "ATtiny85-real-guidance"},
                "id": "req_generate_guidance",
            })
            response = json.loads(daemon.handle_request(request))
            self.assertNotIn("error", response)
            job_id = response["result"]["job_id"]

            deadline = time.monotonic() + 60.0
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
            server.stop()
            daemon.library_store.configure(storage_root=None)
            tmpdir.cleanup()

        self.assertIsNotNone(
            terminal_notification, "datasheet.generate_guidance job never reached a terminal state within 60s"
        )
        self.assertEqual(terminal_notification["method"], "job.completed")
        updated_part = terminal_notification["params"]["result"]
        guidance = updated_part["design_guidance"]
        self.assertTrue(guidance["content_hash"])
        self.assertIn("reset", guidance["categories"])
        self.assertGreater(len(guidance["categories"]["reset"]), 0)


if __name__ == '__main__':
    unittest.main()

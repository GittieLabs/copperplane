import json
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import daemon
import tool_registry


class TestBuildToolRegistry(unittest.TestCase):
    """TEST-001: registers exactly the routes named in TOOL_DEFINITIONS that
    are actually present in daemon.ROUTES right now -- no more, no fewer."""

    def test_001_registers_exactly_the_intended_routes(self):
        registry = tool_registry.build_tool_registry()
        registered_names = {t["name"] for t in registry.list_tools()}
        expected_names = set(tool_registry.TOOL_DEFINITIONS) & set(daemon.ROUTES)
        self.assertEqual(registered_names, expected_names)
        # Every named tool actually exists in daemon.ROUTES on this real,
        # fully-imported daemon module -- not a hypothetical route.
        self.assertTrue(expected_names, "expected at least one real route to be registered")


class TestConfirmationGating(unittest.IsolatedAsyncioTestCase):
    """TEST-002/TEST-004: kicad.inject_component is gated; other tools are not."""

    async def test_002_inject_component_first_call_returns_pending_without_mutating(self):
        calls = []

        def fake_inject(**kwargs):
            calls.append(kwargs)
            return {"status": "written"}

        wrapped = tool_registry._wrap_route("kicad.inject_component", fake_inject)
        result = await wrapped(schema={"pins": 2}, x_mm=1.0, y_mm=2.0)

        self.assertEqual(calls, [])  # the real handler was never invoked
        self.assertIn("confirmed=true", result)

    async def test_002b_inject_component_confirmed_call_actually_dispatches(self):
        calls = []

        def fake_inject(**kwargs):
            calls.append(kwargs)
            return {"status": "written"}

        wrapped = tool_registry._wrap_route("kicad.inject_component", fake_inject)
        result = await wrapped(schema={"pins": 2}, x_mm=1.0, y_mm=2.0, confirmed=True)

        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads(result), {"status": "written"})

    async def test_003_a_non_gated_tool_dispatches_immediately(self):
        calls = []

        def fake_search(**kwargs):
            calls.append(kwargs)
            return [{"part": "ESP32"}]

        wrapped = tool_registry._wrap_route("component.search", fake_search)
        result = await wrapped(query="esp32")

        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads(result), [{"part": "ESP32"}])


class TestExceptionPropagation(unittest.IsolatedAsyncioTestCase):
    """TEST-004: a handler's real exception propagates through
    ToolRegistry.dispatch rather than being swallowed -- proving the
    add_tool() choice over LocalToolDispatcher (SPEC-204 SS3) is real, not
    just documented."""

    async def test_004_registry_dispatch_propagates_a_real_exception(self):
        from agentflow.tools.registry import ToolRegistry

        def failing_handler(**kwargs):
            raise ValueError("board write failed: pad overlap")

        registry = ToolRegistry()
        registry.add_tool(
            "kicad.inject_component",
            tool_registry._wrap_route("kicad.inject_component", failing_handler),
        )

        with self.assertRaises(ValueError):
            await registry.dispatch("kicad.inject_component", {"confirmed": True})


class TestChatAgentToolDefinitions(unittest.TestCase):
    """CTX-206.5 (SPEC-206 SS2.5): the real tool set every SPEC-318 chat
    agent's own `tools:` frontmatter references -- verified against the
    real .prompt.md files below, not just this dict in isolation."""

    def test_001_every_tool_named_by_a_real_agent_prompt_is_registered_and_available(self):
        import glob

        agents_dir = os.path.join(os.path.dirname(__file__), "..", "agentflow", "agents")
        prompt_files = glob.glob(os.path.join(agents_dir, "chat_*.prompt.md"))
        self.assertTrue(prompt_files, "expected at least one chat_*.prompt.md to exist")

        referenced_tools = set()
        for path in prompt_files:
            with open(path, encoding="utf-8") as f:
                in_tools_block = False
                for line in f:
                    if line.startswith("tools:"):
                        in_tools_block = True
                        continue
                    if in_tools_block:
                        if line.startswith("  - "):
                            referenced_tools.add(line.strip()[2:])
                        else:
                            in_tools_block = False

        # context.search is a real, named exception -- CTX-206.5 deliberately
        # defers it until SPEC-206 SS2.6's retrieval index exists.
        referenced_tools.discard("context.search")

        for tool_name in referenced_tools:
            self.assertIn(tool_name, tool_registry.TOOL_DEFINITIONS, f"{tool_name} has no TOOL_DEFINITIONS entry")
            self.assertIn(tool_name, daemon.ROUTES, f"{tool_name} is not a real, registered daemon route")

    def test_002_datasheet_read_pages_requires_part_id_and_pages(self):
        schema = tool_registry.TOOL_DEFINITIONS["datasheet.read_pages"]["input_schema"]
        self.assertEqual(set(schema["required"]), {"part_id", "pages"})

    def test_003_library_load_part_requires_part_id(self):
        schema = tool_registry.TOOL_DEFINITIONS["library.load_part"]["input_schema"]
        self.assertEqual(schema["required"], ["part_id"])

    def test_004_library_list_parts_has_no_required_fields(self):
        schema = tool_registry.TOOL_DEFINITIONS["library.list_parts"]["input_schema"]
        self.assertEqual(schema["required"], [])

    def test_005_kicad_get_component_heights_takes_no_arguments(self):
        schema = tool_registry.TOOL_DEFINITIONS["kicad.get_component_heights"]["input_schema"]
        self.assertEqual(schema["properties"], {})
        self.assertEqual(schema["required"], [])


class TestAgentDispatchToolEndToEnd(unittest.TestCase):
    """TEST-005: drives daemon.py's real JSON-RPC surface end to end through
    the agent.dispatch_tool route (CTX-204.1 Phase 2) -- not the wrapped
    functions in isolation, but the same handle_request path a real Tauri
    caller uses. A fake test tool (registered the same way test_daemon.py's
    own test_004_async_route_returns_job_id_immediately does) stands in for
    a real bridge call, so this test needs no live KiCad/FreeCAD."""

    def setUp(self):
        self.captured = []
        self.original_write_line = daemon._write_line
        daemon._write_line = lambda text: self.captured.append(json.loads(text))

        self.calls = []

        def fake_gated_route(**kwargs):
            self.calls.append(kwargs)
            return {"status": "written"}

        daemon.ROUTES['test.gated_tool'] = fake_gated_route
        daemon.ASYNC_ROUTES.add('test.gated_tool')
        tool_registry.TOOL_DEFINITIONS['test.gated_tool'] = {
            "description": "test-only", "input_schema": {"type": "object", "properties": {}},
        }
        tool_registry.CONFIRMATION_REQUIRED_TOOLS.add('test.gated_tool')

    def tearDown(self):
        daemon._write_line = self.original_write_line
        daemon.ROUTES.pop('test.gated_tool', None)
        daemon.ASYNC_ROUTES.discard('test.gated_tool')
        tool_registry.TOOL_DEFINITIONS.pop('test.gated_tool', None)
        tool_registry.CONFIRMATION_REQUIRED_TOOLS.discard('test.gated_tool')

    def _dispatch(self, tool_input=None, confirmed=None, req_id="req_1"):
        params = {"tool_name": "test.gated_tool"}
        if tool_input is not None:
            params["tool_input"] = tool_input
        if confirmed is not None:
            params["confirmed"] = confirmed
        request = json.dumps({"jsonrpc": "2.0", "method": "agent.dispatch_tool", "params": params, "id": req_id})
        return json.loads(daemon.handle_request(request))

    def test_005a_unconfirmed_call_returns_pending_and_submits_no_job(self):
        response = self._dispatch(tool_input={"x": 1})

        self.assertNotIn("error", response)
        self.assertEqual(response["result"], {"status": "pending_confirmation", "tool": "test.gated_tool", "input": {"x": 1}})
        self.assertEqual(self.calls, [])  # the real handler was never invoked
        self.assertEqual(self.captured, [])  # no job.* notifications either

    def test_005b_confirmed_call_actually_dispatches_through_the_real_async_job_protocol(self):
        response = self._dispatch(tool_input={"x": 1}, confirmed=True)

        self.assertIn("job_id", response.get("result", {}))
        job_id = response["result"]["job_id"]

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            completed = [n for n in self.captured if n.get("method") == "job.completed" and n["params"]["job_id"] == job_id]
            if completed:
                break
            time.sleep(0.05)
        else:
            self.fail("job.completed notification never arrived")

        self.assertEqual(self.calls, [{"x": 1}])  # the real handler ran with exactly tool_input, nothing else
        self.assertEqual(completed[0]["params"]["result"], {"status": "written"})

    def test_005c_unknown_tool_returns_a_real_jsonrpc_error(self):
        request = json.dumps({
            "jsonrpc": "2.0", "method": "agent.dispatch_tool",
            "params": {"tool_name": "not.a.real.tool"}, "id": "req_2",
        })
        response = json.loads(daemon.handle_request(request))

        self.assertIn("error", response)
        self.assertIn("Unknown or unavailable tool", response["error"]["message"])


if __name__ == '__main__':
    unittest.main()

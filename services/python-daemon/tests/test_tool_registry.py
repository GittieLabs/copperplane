import json
import glob
import os
import re
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
        # Registered under the provider-safe name, dispatched to the dotted
        # route (CTX-204.x: Anthropic rejects a dot in a tool name).
        expected_names = {
            tool_registry.tool_name_for_route(route)
            for route in set(tool_registry.TOOL_DEFINITIONS) & set(daemon.ROUTES)
        }
        self.assertEqual(registered_names, expected_names)
        # Every named tool actually exists in daemon.ROUTES on this real,
        # fully-imported daemon module -- not a hypothetical route.
        self.assertTrue(expected_names, "expected at least one real route to be registered")

    def test_002_exclude_leaves_every_other_route_registered(self):
        """CTX-319.1 (SPEC-319 §2.2): review()'s own real call shape --
        excluding CONFIRMATION_REQUIRED_TOOLS must not affect any other
        registered tool."""
        full = tool_registry.build_tool_registry()
        filtered = tool_registry.build_tool_registry(exclude=tool_registry.CONFIRMATION_REQUIRED_TOOLS)

        full_names = {t["name"] for t in full.list_tools()}
        filtered_names = {t["name"] for t in filtered.list_tools()}

        gated = {
            tool_registry.tool_name_for_route(route)
            for route in tool_registry.CONFIRMATION_REQUIRED_TOOLS
        }
        self.assertEqual(full_names - filtered_names, gated & full_names)
        self.assertTrue(filtered_names, "expected at least one real route to survive the exclusion")

    def test_003_exclude_a_name_that_is_not_registered_at_all_is_a_harmless_no_op(self):
        registry = tool_registry.build_tool_registry(exclude={"not.a.real.tool"})
        self.assertEqual(
            {t["name"] for t in registry.list_tools()},
            {
                tool_registry.tool_name_for_route(route)
                for route in set(tool_registry.TOOL_DEFINITIONS) & set(daemon.ROUTES)
            },
        )


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

        for tool_name in referenced_tools:
            # A prompt names the tool the MODEL sees, which is the
            # provider-safe name, not the dotted route behind it.
            self.assertIn(
                tool_name, tool_registry.ROUTE_FOR_TOOL,
                f"{tool_name} is not a tool this app offers under that name",
            )
            route = tool_registry.ROUTE_FOR_TOOL[tool_name]
            self.assertIn(route, daemon.ROUTES, f"{route} is not a real, registered daemon route")

    def test_002_datasheet_read_pages_requires_part_id_and_pages(self):
        schema = tool_registry.TOOL_DEFINITIONS["datasheet.read_pages"]["input_schema"]
        self.assertEqual(set(schema["required"]), {"part_id", "pages"})

    def test_003_library_load_part_requires_part_id(self):
        schema = tool_registry.TOOL_DEFINITIONS["library.load_part"]["input_schema"]
        self.assertEqual(schema["required"], ["part_id"])

    def test_004_context_search_requires_only_query(self):
        """CTX-206.7: closes the gap CTX-206.5 named -- context.search now
        has a real route and TOOL_DEFINITIONS entry, so test_001 above no
        longer needs to exempt it."""
        schema = tool_registry.TOOL_DEFINITIONS["context.search"]["input_schema"]
        self.assertEqual(schema["required"], ["query"])

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


class TestEveryToolNameIsAcceptableToEveryProvider(unittest.TestCase):
    """The check that would have caught it, and did not exist.

    Anthropic validates tool names against `^[a-zA-Z0-9_-]{1,128}$` and
    rejects the entire request with a 400 if any one fails. Every tool this
    app offered was named for its dotted JSON-RPC route, so every review,
    chat turn and part lookup failed on Anthropic -- reported from the built
    app the first time an Anthropic key was configured:

        tools.0.custom.name: String should match pattern '^[a-zA-Z0-9_-]{1,128}$'

    It survived because the maintainer's roles were bound to Google, which
    accepts dots. A test suite that never asserted the constraint could not
    tell the two providers apart.
    """

    #: Anthropic's published constraint, and the strictest of the providers
    #: this app supports -- so satisfying it satisfies all of them.
    NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")

    def test_001_every_registered_tool_name_matches_the_pattern(self):
        registry = tool_registry.build_tool_registry()
        offenders = [
            t["name"] for t in registry.list_tools()
            if not self.NAME_PATTERN.match(t["name"])
        ]
        self.assertEqual(offenders, [])

    def test_002_every_definition_maps_to_an_acceptable_name(self):
        """Covers definitions whose route is absent from ROUTES on this
        machine, which build_tool_registry silently skips."""
        offenders = [
            route for route in tool_registry.TOOL_DEFINITIONS
            if not self.NAME_PATTERN.match(tool_registry.tool_name_for_route(route))
        ]
        self.assertEqual(offenders, [])

    def test_003_the_translation_is_reversible_and_collision_free(self):
        """Two routes must never map to one tool name -- a silent collision
        would send a tool call to the wrong handler."""
        names = [tool_registry.tool_name_for_route(r) for r in tool_registry.TOOL_DEFINITIONS]

        self.assertEqual(len(names), len(set(names)))
        for route in tool_registry.TOOL_DEFINITIONS:
            self.assertEqual(tool_registry.ROUTE_FOR_TOOL[tool_registry.tool_name_for_route(route)], route)

    def test_004_every_prompt_names_a_tool_that_survives_translation(self):
        """A prompt naming a dotted tool would be describing a tool the model
        is never offered -- the failure that produced this bug, one layer up."""
        agents_dir = os.path.join(os.path.dirname(__file__), "..", "agentflow", "agents")
        offenders = []
        for path in glob.glob(os.path.join(agents_dir, "*.prompt.md")):
            with open(path, encoding="utf-8") as handle:
                for route in tool_registry.TOOL_DEFINITIONS:
                    if route in handle.read():
                        offenders.append(f"{os.path.basename(path)} names the route {route}")
                        break
        self.assertEqual(offenders, [])

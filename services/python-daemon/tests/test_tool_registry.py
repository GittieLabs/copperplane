import json
import os
import sys
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


if __name__ == '__main__':
    unittest.main()

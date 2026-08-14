"""
SPEC-204/CTX-204.1: registers a subset of daemon.py's ROUTES as AgentFlow
tools.

Uses ToolRegistry.add_tool() (inline registration), never
LocalToolDispatcher -- verified directly against gittielabs-agentflow==0.8.2
(SPEC-204 SS3): add_tool's inline handlers let a real exception propagate to
AgentExecutor's own is_error/ERROR-event handling, while LocalToolDispatcher
swallows every handler exception into a "Tool error: ..." string. Reaching
for LocalToolDispatcher here -- the more obviously-named class for "a
locally-running tool" -- would silently reintroduce that failure-signaling
gap.

Structured results ride the ContextVar AgentExecutor already reads
(agentflow.tools.http_dispatcher.last_raw_tool_result), not a bespoke
channel -- also verified directly, not assumed from LocalToolDispatcher's
registration signature (see SPEC-204 SS2's account of the original, wrong
diagnosis).

Phase 1 scope only: every tool wrapped here calls its daemon.ROUTES handler
directly and synchronously. Four of these five routes
(kicad.inject_component, freecad.generate_enclosure, kicad.generate_component,
component.search) are normally invoked through daemon.py's ASYNC_ROUTES /
submit_job machinery (SPEC-105) instead -- calling them directly here
bypasses that job-progress protocol entirely. That's deliberately deferred
to CTX-204.1 Phase 2, which is scoped to wire this registry into
daemon.py's real JSON-RPC surface through SPEC-105's async job channel.
Nothing in this module is wired into daemon.py yet.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from agentflow.tools.http_dispatcher import last_raw_tool_result
from agentflow.tools.registry import ToolRegistry

import daemon

# The subset of daemon.ROUTES an agent plan would plausibly call -- not
# local project/library CRUD (SPEC-204 SS1's own non-goal against
# registering all ~20 routes on day one).
TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "kicad.inject_component": {
        "description": (
            "Writes a validated component schema into the board KiCad "
            "already has open, at the given position. Mutates a live "
            "board -- requires confirmed=true on a second call before it "
            "actually runs; the first call always returns pending."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "schema": {"type": "object", "description": "A SPEC-202-validated component schema."},
                "x_mm": {"type": "number"},
                "y_mm": {"type": "number"},
                "confirmed": {
                    "type": "boolean",
                    "description": "Must be true to actually perform the board write; omit or false to propose it.",
                },
            },
            "required": ["schema", "x_mm", "y_mm"],
        },
    },
    "freecad.generate_enclosure": {
        "description": (
            "Generates an enclosure body. Supplying both width and depth "
            "always uses manual dimensions; omitting them uses the "
            "currently-connected board's real outline and mounting holes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "height": {"type": "number"},
                "width": {"type": "number"},
                "depth": {"type": "number"},
                "wall_thickness_mm": {"type": "number"},
                "clearance_mm": {"type": "number"},
                "fillet_radius_mm": {"type": "number"},
                "standoff_height_mm": {"type": "number"},
                "project_name": {"type": "string"},
            },
            "required": ["height"],
        },
    },
    "kicad.generate_component": {
        "description": "Runs LLM extraction plus deterministic validation for a part number, returning a validated component schema.",
        "input_schema": {
            "type": "object",
            "properties": {"part_number": {"type": "string"}},
            "required": ["part_number"],
        },
    },
    "component.search": {
        "description": "Free-text component search, returning ranked candidates.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}

# The only tool here that mutates a document the user didn't ask this app
# to open -- every other registered route reads, or writes only to this
# app's own local storage (verified against every route in daemon.ROUTES,
# SPEC-204 SS2).
CONFIRMATION_REQUIRED_TOOLS = {"kicad.inject_component"}


def _wrap_route(name: str, handler: Callable[..., Any]) -> Callable[..., Any]:
    """Adapts a synchronous daemon.ROUTES handler into the async,
    string-returning shape ToolRegistry.add_tool() requires. The wrapper
    is a signature adapter only -- it does not introduce concurrent
    dispatch the single-threaded daemon was never designed for (SPEC-204
    SS3)."""

    async def _tool(**kwargs: Any) -> str:
        if name in CONFIRMATION_REQUIRED_TOOLS and not kwargs.pop("confirmed", False):
            pending = {"status": "pending_confirmation", "tool": name, "input": kwargs}
            last_raw_tool_result.set(pending)
            return (
                f"{name} was proposed but not executed -- it requires explicit "
                f"confirmation. Re-invoke it with confirmed=true to actually run it."
            )

        result = handler(**kwargs)
        last_raw_tool_result.set(result if isinstance(result, dict) else None)
        return json.dumps(result)

    return _tool


def build_tool_registry() -> ToolRegistry:
    """Builds a real ToolRegistry wrapping whichever of TOOL_DEFINITIONS'
    routes actually exist in daemon.ROUTES right now. A route is absent
    when its bridge module never imported (SPEC-107 SS2 -- e.g. no KiCad
    connection available) -- this registry silently reflects that, the
    same way daemon.ROUTES' own conditional registration already does,
    rather than registering a tool that would immediately KeyError."""
    registry = ToolRegistry()
    for name, definition in TOOL_DEFINITIONS.items():
        handler = daemon.ROUTES.get(name)
        if handler is None:
            continue
        registry.add_tool(
            name,
            _wrap_route(name, handler),
            description=definition["description"],
            input_schema=definition["input_schema"],
        )
    return registry

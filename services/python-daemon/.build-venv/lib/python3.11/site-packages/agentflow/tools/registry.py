"""
Tool registry that manages multiple dispatchers and generates unified tool lists.

The registry maps tool names to dispatchers. When the agent wants to call a tool,
the registry routes it to the correct dispatcher (HTTP, local, etc.).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from agentflow.protocols import ToolDispatcher

logger = logging.getLogger("agentflow.tools")


class ToolRegistry:
    """
    Aggregates multiple ToolDispatchers under a single interface.

    Tools can also be registered directly with inline definitions and handlers.
    """

    def __init__(self) -> None:
        self._dispatchers: list[tuple[set[str], ToolDispatcher]] = []
        self._inline_tools: dict[str, dict[str, Any]] = {}
        self._inline_handlers: dict[str, Callable[..., Awaitable[str]]] = {}

    def add_dispatcher(self, tool_names: set[str], dispatcher: ToolDispatcher) -> None:
        """Register a dispatcher for a set of tool names."""
        self._dispatchers.append((tool_names, dispatcher))

    def add_tool(
        self,
        name: str,
        handler: Callable[..., Awaitable[str]],
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        """Register a single inline tool with its handler and definition."""
        self._inline_tools[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema or {"type": "object", "properties": {}},
        }
        self._inline_handlers[name] = handler

    async def dispatch(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Route a tool call to the appropriate dispatcher."""
        # Check inline handlers first
        if tool_name in self._inline_handlers:
            logger.info("Tool call (inline): %s", tool_name)
            return await self._inline_handlers[tool_name](**tool_input)

        # Check registered dispatchers
        for tool_names, dispatcher in self._dispatchers:
            if tool_name in tool_names:
                logger.info("Tool call (dispatched): %s", tool_name)
                return await dispatcher.dispatch(tool_name, tool_input)

        return f"Unknown tool: {tool_name}"

    def list_tools(self) -> list[dict[str, Any]]:
        """Return merged tool definitions from all dispatchers and inline tools."""
        tools: list[dict[str, Any]] = []

        # Inline tools
        tools.extend(self._inline_tools.values())

        # Dispatcher tools
        for _names, dispatcher in self._dispatchers:
            tools.extend(dispatcher.list_tools())

        return tools

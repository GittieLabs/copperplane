"""
Local tool dispatcher — calls in-process async functions.

Used for tools that run in the same process (e.g., Signal messaging, phone calls).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Awaitable

from agentflow.tools.http_dispatcher import last_raw_tool_result

logger = logging.getLogger("agentflow.tools.local")


class LocalToolDispatcher:
    """ToolDispatcher that calls locally registered async functions."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Awaitable[str]]] = {}
        self._definitions: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        handler: Callable[..., Awaitable[str]],
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        """Register a local tool handler with its definition."""
        self._handlers[name] = handler
        self._definitions[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema or {"type": "object", "properties": {}},
        }

    async def dispatch(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Call the local handler for the given tool."""
        handler = self._handlers.get(tool_name)
        if handler is None:
            return f"Unknown local tool: {tool_name}"

        try:
            result_str = await handler(**tool_input)
            # Set raw_result so the TOOL_RESULT event includes structured data,
            # matching the HTTP dispatcher behavior.  If the handler already
            # set the ContextVar (e.g. because it has access to the raw dict
            # before formatting), honour that value instead of overwriting it
            # with a potentially lossy json.loads() of the formatted string.
            if last_raw_tool_result.get() is None:
                try:
                    raw = json.loads(result_str)
                    last_raw_tool_result.set(raw if isinstance(raw, dict) else None)
                except (json.JSONDecodeError, TypeError):
                    pass  # leave as None — handler didn't set it either
            return result_str
        except Exception as exc:
            logger.error("Local tool %s error: %s", tool_name, exc)
            return f"Tool error: {exc}"

    def list_tools(self) -> list[dict[str, Any]]:
        """Return definitions of all registered local tools."""
        return list(self._definitions.values())

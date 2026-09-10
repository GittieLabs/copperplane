"""
HTTP tool dispatcher — calls a remote tools-server.

Compatible with the existing OpenClaw tools-server protocol:
  POST /tools/run  { "tool": name, "input": {...} }
  Response:         { "tool": name, "result": any, "success": bool }
"""
from __future__ import annotations

import contextvars
import json
import logging
from typing import Any

logger = logging.getLogger("agentflow.tools.http")

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

# Asyncio-safe storage for the raw (pre-formatted) tool result dict.
# Set by HTTPToolDispatcher.dispatch(), read by AgentExecutor to enrich
# TOOL_RESULT events.  ContextVar is task-local so concurrent agent
# executions never clobber each other.
last_raw_tool_result: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "last_raw_tool_result", default=None,
)


class HTTPToolDispatcher:
    """ToolDispatcher that calls a remote HTTP tools-server."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 120.0,
        tool_definitions: list[dict[str, Any]] | None = None,
        result_formatter: Any = None,
    ):
        if httpx is None:
            raise ImportError("Install httpx: pip install httpx")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._tool_definitions = tool_definitions or []
        self._result_formatter = result_formatter

    async def dispatch(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """POST to the tools-server and return the result as a string."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/tools/run",
                    json={"tool": tool_name, "input": tool_input},
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("success"):
                result = data["result"]
                # Stash raw result for TOOL_RESULT event enrichment
                last_raw_tool_result.set(result if isinstance(result, dict) else None)
                if self._result_formatter and isinstance(result, dict):
                    return self._result_formatter(result)
                if isinstance(result, dict):
                    return json.dumps(result, indent=2)
                return str(result)
            else:
                return f"Tool error: {data.get('result', 'unknown error')}"

        except Exception as exc:
            logger.error("HTTP tool dispatch error for %s: %s", tool_name, exc)
            return f"Tool unavailable: {exc}"

    def list_tools(self) -> list[dict[str, Any]]:
        """Return the tool definitions configured at init time."""
        return self._tool_definitions

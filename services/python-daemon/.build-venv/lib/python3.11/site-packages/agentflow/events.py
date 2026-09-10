"""
Simple async event bus for observability.

Allows hooking into framework events (node_started, tool_called, error, etc.)
without coupling to any specific logging or metrics system.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from agentflow.protocols import EventHandler

logger = logging.getLogger("agentflow.events")

# Standard event types
NODE_STARTED = "node_started"
NODE_COMPLETED = "node_completed"
TOOL_CALLED = "tool_called"
TOOL_RESULT = "tool_result"
ROUTER_DECISION = "router_decision"
SESSION_CREATED = "session_created"
WORKFLOW_STARTED = "workflow_started"
WORKFLOW_COMPLETED = "workflow_completed"
MEMORY_STORED = "memory_stored"
DOMAIN_ROUTED = "domain_routed"
ERROR = "error"
LLM_CALL_STARTED = "llm_call_started"
LLM_CALL_COMPLETED = "llm_call_completed"
FOREACH_ITERATION = "foreach_iteration"
HANDLER_RESULT = "handler_result"


class EventBus:
    """Pub/sub event system. Observer errors never break execution."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def on(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        self._handlers[event_type].append(handler)

    def off(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event to all registered handlers. Errors are logged, never raised."""
        for handler in self._handlers.get(event_type, []):
            try:
                await handler.on_event(event_type, data or {})
            except Exception:
                logger.exception("Event handler error for %s", event_type)


class LoggingEventHandler:
    """Built-in handler that logs all events at INFO level."""

    async def on_event(self, event_type: str, data: dict[str, Any]) -> None:
        logger.info("[%s] %s", event_type, data)

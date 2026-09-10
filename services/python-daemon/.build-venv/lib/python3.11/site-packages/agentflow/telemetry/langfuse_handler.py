"""
Langfuse observability handler for agentflow EventBus.

Maps agentflow events to the Langfuse trace/span/generation hierarchy:

  WORKFLOW_STARTED     → start_observation(as_type="span") — root trace span
  NODE_STARTED         → root_span.start_observation(as_type="span")
  LLM_CALL_COMPLETED   → node_span.start_observation(as_type="generation") — nested LLM call
  TOOL_CALLED          → node_span.start_observation(as_type="tool") — nested tool call
  NODE_COMPLETED       → close node span
  WORKFLOW_COMPLETED   → close root span
  DOMAIN_ROUTED        → span recording routing decision
  ERROR                → mark span as error and close

Compatible with Langfuse SDK v4+.

Requirements:
    pip install langfuse>=4.0   (or gittielabs-agentflow[telemetry])

Usage:
    from agentflow.telemetry import LangfuseEventHandler
    from agentflow import EventBus, WORKFLOW_STARTED, WORKFLOW_COMPLETED, ...

    bus = EventBus()
    handler = LangfuseEventHandler(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_BASE_URL"),
        resource_attributes={"service.name": "my-app"},
    )

    # Set per-request context before each workflow execution:
    handler.set_trace_context(
        session_id="signal:default-pipeline",
        trace_name="signal:default-pipeline",
        user_id="+14846491129",
        tags=["signal", "default-pipeline"],
        metadata={"channel": "signal", "git_sha": "abc123"},
    )

    for event in (WORKFLOW_STARTED, WORKFLOW_COMPLETED, NODE_STARTED, NODE_COMPLETED,
                  LLM_CALL_COMPLETED, TOOL_CALLED, DOMAIN_ROUTED, ERROR):
        bus.on(event, handler)

    # On shutdown:
    handler.flush()
"""
from __future__ import annotations

import logging
from typing import Any

from agentflow.events import (
    DOMAIN_ROUTED,
    ERROR,
    LLM_CALL_COMPLETED,
    NODE_COMPLETED,
    NODE_STARTED,
    TOOL_CALLED,
    WORKFLOW_COMPLETED,
    WORKFLOW_STARTED,
)

logger = logging.getLogger("agentflow.telemetry")


class LangfuseEventHandler:
    """EventBus subscriber that creates Langfuse traces from agentflow events.

    Span keying strategy:
    - Root spans (traces) are keyed by workflow name.
    - Node spans are keyed by node_id (the ``node`` value emitted by NODE_STARTED).
    - LLM generations and tool spans are children of the matching node span.

    Trace context:
    - Call ``set_trace_context()`` before each workflow execution to attach
      session IDs, trace names, tags, and metadata to the root trace.
    - Context is consumed (cleared) when WORKFLOW_STARTED fires.

    Thread safety: not thread-safe; designed for use within a single asyncio event loop.
    """

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        host: str | None = None,
        resource_attributes: dict[str, str] | None = None,
    ) -> None:
        """
        Args:
            public_key:          Langfuse public key (LANGFUSE_PUBLIC_KEY).
            secret_key:          Langfuse secret key (LANGFUSE_SECRET_KEY).
            host:                Optional Langfuse instance URL. Defaults to Langfuse Cloud EU.
                                 Use ``https://us.cloud.langfuse.com`` for Langfuse Cloud US.
            resource_attributes: Static attributes attached to the Langfuse client instance.
                                 Use for service.name, service.version, etc.
        """
        try:
            from langfuse import Langfuse
        except ImportError:
            raise ImportError(
                "langfuse package is required. "
                "Install with: pip install langfuse  "
                "or: pip install gittielabs-agentflow[telemetry]"
            )

        kwargs: dict[str, Any] = {
            "public_key": public_key,
            "secret_key": secret_key,
        }
        if host:
            kwargs["host"] = host

        # resource_attributes may not be supported in older Langfuse SDK versions
        if resource_attributes:
            try:
                self._lf = Langfuse(**kwargs, resource_attributes=resource_attributes)
            except TypeError:
                logger.info("Langfuse SDK does not support resource_attributes — skipping")
                self._lf = Langfuse(**kwargs)
        else:
            self._lf = Langfuse(**kwargs)

        # Active observations — keyed by workflow name (root spans) / node_id (child spans)
        self._root_spans: dict[str, Any] = {}   # workflow → root LangfuseSpan
        self._node_spans: dict[str, Any] = {}   # node_id  → child LangfuseSpan

        # Per-request trace context — set by caller, consumed on WORKFLOW_STARTED
        self._trace_ctx: dict[str, Any] | None = None

    def set_trace_context(
        self,
        *,
        session_id: str | None = None,
        trace_name: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Set conversation-level context for the next trace.

        Call this before each workflow execution (e.g. in ``chat()``).
        The context is consumed once when WORKFLOW_STARTED fires, then cleared.

        Args:
            session_id:  Groups traces in a Langfuse session (< 200 chars).
                         Format: ``<channel>:<workflow_name>`` e.g. ``signal:default-pipeline``.
            trace_name:  Overrides the root trace name (defaults to workflow name).
            user_id:     Langfuse user identifier for the trace.
            tags:        List of tags for filtering (e.g. ``["signal", "default-pipeline"]``).
            metadata:    Extra metadata merged into the root span (channel, domain, git_sha, etc.).
        """
        self._trace_ctx = {
            "session_id": session_id,
            "trace_name": trace_name,
            "user_id": user_id,
            "tags": tags,
            "metadata": metadata or {},
        }

    async def on_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Dispatch an event to the appropriate handler. Errors are caught and logged."""
        try:
            if event_type == WORKFLOW_STARTED:
                self._handle_workflow_started(data)
            elif event_type == WORKFLOW_COMPLETED:
                self._handle_workflow_completed(data)
            elif event_type == NODE_STARTED:
                self._handle_node_started(data)
            elif event_type == NODE_COMPLETED:
                self._handle_node_completed(data)
            elif event_type == LLM_CALL_COMPLETED:
                self._handle_llm_call_completed(data)
            elif event_type == TOOL_CALLED:
                self._handle_tool_called(data)
            elif event_type == DOMAIN_ROUTED:
                self._handle_domain_routed(data)
            elif event_type == ERROR:
                self._handle_error(data)
        except Exception:
            logger.warning("LangfuseEventHandler error on event '%s'", event_type, exc_info=True)

    # ─── Event handlers ──────────────────────────────────────────────────────

    def _handle_workflow_started(self, data: dict[str, Any]) -> None:
        workflow = data.get("workflow", "unknown")

        # Consume trace context (set by caller before this workflow)
        ctx = self._trace_ctx or {}
        self._trace_ctx = None  # clear — one-shot per workflow

        # Merge event data with caller-provided metadata
        merged_metadata = {**data}
        if ctx.get("metadata"):
            merged_metadata.update(ctx["metadata"])

        # Build root trace kwargs
        trace_kwargs: dict[str, Any] = {
            "name": ctx.get("trace_name") or workflow,
            "metadata": merged_metadata,
        }
        if ctx.get("session_id"):
            trace_kwargs["session_id"] = ctx["session_id"]
        if ctx.get("user_id"):
            trace_kwargs["user_id"] = ctx["user_id"]
        if ctx.get("tags"):
            trace_kwargs["tags"] = ctx["tags"]

        try:
            # Langfuse v2/v3+ uses trace() for the root object
            root_span = self._lf.trace(**trace_kwargs)
        except (AttributeError, TypeError):
            # Fallback for very old SDKs or if trace() is somehow different
            trace_kwargs["as_type"] = "span"
            if "session_id" in trace_kwargs:
                del trace_kwargs["session_id"] # session_id not supported on spans
            root_span = self._lf.start_observation(**trace_kwargs)

        self._root_spans[workflow] = root_span
        logger.debug("Langfuse root span created: %s (session=%s)",
                     trace_kwargs["name"], ctx.get("session_id"))

    def _handle_workflow_completed(self, data: dict[str, Any]) -> None:
        workflow = data.get("workflow", "unknown")
        root_span = self._root_spans.pop(workflow, None)
        if root_span:
            root_span.update(
                output=data.get("result", ""),
                metadata={"nodes_completed": data.get("nodes_completed", 0)},
            )
            root_span.end()
            logger.debug("Langfuse root span closed: %s", workflow)

    def _handle_node_started(self, data: dict[str, Any]) -> None:
        node = data.get("node", "unknown")
        # Attach to the most recently opened root span
        root_span = next(iter(self._root_spans.values()), None)
        if root_span:
            node_span = root_span.start_observation(
                name=node,
                as_type="span",
                input=data,
            )
            self._node_spans[node] = node_span
            logger.debug("Langfuse node span created: %s", node)

    def _handle_node_completed(self, data: dict[str, Any]) -> None:
        node = data.get("node", "unknown")
        node_span = self._node_spans.pop(node, None)
        if node_span:
            node_span.update(
                output=data.get("output", ""),
                metadata={"agent": data.get("agent", "")},
            )
            node_span.end()
            logger.debug("Langfuse node span closed: %s", node)

    def _handle_llm_call_completed(self, data: dict[str, Any]) -> None:
        """Record an LLM generation nested under the appropriate node span."""
        node = data.get("node") or data.get("agent", "unknown")
        parent = self._node_spans.get(node)
        if parent is None:
            # Fall back to root span if node span not found
            parent = next(iter(self._root_spans.values()), None)
        if parent is None:
            return

        input_tokens = data.get("input_tokens", 0)
        output_tokens = data.get("output_tokens", 0)

        gen = parent.start_observation(
            name=f"{data.get('agent', 'llm')}/round-{data.get('round', 0)}",
            as_type="generation",
            model=data.get("model"),
            usage_details={
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
            metadata={
                "round": data.get("round"),
                "elapsed_ms": data.get("elapsed_ms"),
                "stop_reason": data.get("stop_reason"),
                "tool_calls": data.get("tool_calls", 0),
            },
        )
        # Generations are point-in-time — end immediately
        gen.end()

    def _handle_tool_called(self, data: dict[str, Any]) -> None:
        node = data.get("node", "unknown")
        node_span = self._node_spans.get(node)
        if node_span:
            tool_name = data.get("tool", "unknown")
            tool_span = node_span.start_observation(
                name=f"tool:{tool_name}",
                as_type="tool",
                input=data.get("input"),
                metadata={"round": data.get("round")},
            )
            # Tool spans are fire-and-forget for now — end immediately
            # (TOOL_RESULT event could be used to close them properly)
            tool_span.end()

    def _handle_domain_routed(self, data: dict[str, Any]) -> None:
        """Record the routing decision as a span on the root trace."""
        root_span = next(iter(self._root_spans.values()), None)
        if root_span:
            route_span = root_span.start_observation(
                name=f"route:{data.get('target', 'unknown')}",
                as_type="span",
                metadata={
                    "domain": data.get("domain"),
                    "target": data.get("target"),
                    "confidence": data.get("confidence"),
                    "router": data.get("router"),
                },
            )
            route_span.end()

    def _handle_error(self, data: dict[str, Any]) -> None:
        node = data.get("node", "unknown")
        node_span = self._node_spans.pop(node, None)
        if node_span:
            node_span.update(
                level="ERROR",
                status_message=data.get("error", "unknown error"),
            )
            node_span.end()

    # ─── Lifecycle ───────────────────────────────────────────────────────────

    def flush(self) -> None:
        """Flush pending events to Langfuse. Call this on application shutdown."""
        try:
            self._lf.flush()
            logger.debug("Langfuse flush completed")
        except Exception:
            logger.warning("Langfuse flush error", exc_info=True)

"""
AgentFlow core types.

Canonical data structures shared across all modules. These are provider-agnostic —
each LLM provider adapter translates to/from these types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Message role in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "tool_result"


class NodeMode(str, Enum):
    """Execution mode for workflow nodes."""

    SYNC = "sync"
    PARALLEL = "parallel"
    ASYNC = "async"


@dataclass
class ToolCall:
    """A request from the LLM to invoke a tool."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResult:
    """The result of executing a tool call."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class Message:
    """A single message in a conversation."""

    role: Role
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Unified response from any LLM provider."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use" | "max_tokens"
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None  # Original provider response for debugging
    metadata: dict[str, Any] = field(default_factory=dict)  # Provider-specific metadata (e.g. thinking text)


@dataclass
class NodeOutput:
    """Output from a single workflow node execution."""

    node_id: str
    agent_id: str
    text: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

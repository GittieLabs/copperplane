"""
AgentFlow protocols.

Structural typing interfaces (PEP 544) that define the contracts for pluggable
backends. Any class implementing these methods works — no inheritance required.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agentflow.types import AgentResponse, Message


@runtime_checkable
class LLMProvider(Protocol):
    """Contract for LLM backends (Anthropic, OpenAI, Google, etc.)."""

    # `params` is forwarded verbatim to the underlying vendor SDK call.
    #
    # It exists because vendors add parameters faster than any framework can
    # name them -- reasoning effort, thinking budgets, and whatever comes
    # next -- and predicting which model supports which is not a problem
    # AgentFlow can win. The caller chooses and owns correctness.
    #
    # A key AgentFlow itself sets is REFUSED rather than merged, so a
    # passthrough can never silently redirect a call to a different model or
    # a different conversation. Each provider raises ValueError naming the
    # offending key; see `_merge_params`.
    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        params: dict[str, Any] | None = None,
    ) -> AgentResponse: ...


@runtime_checkable
class StorageBackend(Protocol):
    """Contract for reading/writing files (filesystem, S3, in-memory)."""

    async def read(self, path: str) -> str | None: ...
    async def write(self, path: str, content: str) -> None: ...
    async def exists(self, path: str) -> bool: ...
    async def list(self, prefix: str) -> list[str]: ...
    async def delete(self, path: str) -> None: ...


@runtime_checkable
class ToolDispatcher(Protocol):
    """Contract for dispatching tool calls."""

    async def dispatch(self, tool_name: str, tool_input: dict[str, Any]) -> str: ...
    def list_tools(self) -> list[dict[str, Any]]: ...


@runtime_checkable
class MemoryStore(Protocol):
    """Contract for semantic memory (vector search, file-based, etc.)."""

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]: ...
    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str: ...


@runtime_checkable
class VectorBackend(Protocol):
    """Contract for vector database backends (Qdrant, LanceDB, Chroma, etc.).

    Each backend must translate these operations into the native API of the
    underlying vector store. The ``query`` method must return a list of dicts
    with keys ``id`` (str), ``score`` (float), and ``payload`` (dict).
    """

    def ensure_collection(self, name: str, dim: int) -> None: ...
    def upsert(
        self, collection: str, point_id: str, vector: list[float], payload: dict[str, Any]
    ) -> None: ...
    def query(self, collection: str, vector: list[float], limit: int) -> list[dict[str, Any]]: ...
    def delete_points(self, collection: str, point_ids: list[str]) -> None: ...


@runtime_checkable
class EventHandler(Protocol):
    """Contract for observability event handlers."""

    async def on_event(self, event_type: str, data: dict[str, Any]) -> None: ...

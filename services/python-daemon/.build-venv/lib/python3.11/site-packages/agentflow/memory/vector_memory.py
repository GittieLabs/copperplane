"""
Vector memory backend with pluggable vector stores.

Implements the MemoryStore protocol with semantic search powered by
vector embeddings. Both embedding-agnostic and backend-agnostic — the
caller provides their own embed function and a VectorBackend instance
(Qdrant, LanceDB, ChromaDB, etc.).

Requires one of:
    pip install agentflow[vector]    # Qdrant
    pip install agentflow[lancedb]   # LanceDB
    pip install agentflow[chroma]    # ChromaDB
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from agentflow.protocols import VectorBackend

logger = logging.getLogger("agentflow.memory.vector")

# Type for an async embedding function: text -> vector
EmbedFn = Callable[[str], Awaitable[list[float]]]


class VectorMemory:
    """
    MemoryStore implementation using a pluggable VectorBackend for semantic search.

    Embedding-agnostic: the caller must supply ``embed_fn`` (an async
    function ``str -> list[float]``) and ``embedding_dim`` (the vector
    size produced by that function).

    Backend-agnostic: the caller must supply a ``backend`` that implements
    the ``VectorBackend`` protocol (QdrantBackend, LanceDBBackend,
    ChromaBackend, or any custom implementation).

    Stores text with embeddings for semantic retrieval. Each memory entry
    has:
    - vector: embedding of the content text
    - payload: {content, created_at, agent, ...metadata}
    """

    def __init__(
        self,
        *,
        embed_fn: EmbedFn,
        embedding_dim: int,
        backend: VectorBackend,
        collection: str = "agentflow_memories",
        agent: str = "default",
    ) -> None:
        if not callable(embed_fn):
            raise TypeError("embed_fn must be an async callable (str -> list[float])")
        if embedding_dim < 1:
            raise ValueError("embedding_dim must be a positive integer")

        self._backend = backend
        self._collection = collection
        self._embed_fn = embed_fn
        self._embedding_dim = embedding_dim
        self._agent = agent

        self._backend.ensure_collection(self._collection, self._embedding_dim)

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """
        Store a memory with its embedding.

        Returns the point ID as a string.
        """
        vector = await self._embed_fn(content)
        point_id = str(uuid.uuid4())

        payload = {
            "content": content,
            "agent": self._agent,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        }

        self._backend.upsert(self._collection, point_id, vector, payload)

        logger.debug("Stored vector memory: %s (agent=%s)", point_id, self._agent)
        return point_id

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search memories by semantic similarity.

        Returns list of dicts with 'content', 'id', 'score', and any stored metadata.
        """
        query_vector = await self._embed_fn(query)

        results = self._backend.query(self._collection, query_vector, limit)

        return [
            {
                "content": r["payload"].get("content", ""),
                "id": r["id"],
                "score": r["score"],
                **{k: v for k, v in r["payload"].items() if k != "content"},
            }
            for r in results
        ]

    async def delete(self, point_id: str) -> None:
        """Delete a specific memory by point ID."""
        self._backend.delete_points(self._collection, [point_id])

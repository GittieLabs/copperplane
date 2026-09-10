"""
Memory manager.

Orchestrates short-term (session scratchpads) and long-term (FileMemory or
VectorMemory) memory retrieval. The ContextAssembler uses this indirectly,
but the MemoryManager provides higher-level operations like:

- Storing post-conversation memories from agent output
- Searching across both memory tiers
- Pruning old entries based on MemoryConfig rules
"""
from __future__ import annotations

import logging
from typing import Any

from agentflow.config.schemas import MemoryConfig
from agentflow.protocols import MemoryStore

logger = logging.getLogger("agentflow.memory")


class MemoryManager:
    """
    High-level memory operations combining short-term and long-term stores.

    Provides a unified search that queries the long-term store and formats
    results for injection into agent context.
    """

    def __init__(
        self,
        long_term: MemoryStore | None = None,
        config: MemoryConfig | None = None,
    ) -> None:
        self._long_term = long_term
        self._config = config

    @property
    def long_term(self) -> MemoryStore | None:
        return self._long_term

    async def remember(self, content: str, metadata: dict[str, Any] | None = None) -> str | None:
        """
        Store a memory in the long-term store.

        Returns the storage path/ID, or None if no store is configured.
        """
        if not self._long_term:
            logger.debug("No long-term memory store configured, skipping store")
            return None

        return await self._long_term.store(content, metadata)

    async def recall(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search long-term memory for entries relevant to the query.

        Returns list of dicts with 'content', 'path'/'id', and 'score'.
        """
        if not self._long_term:
            return []

        return await self._long_term.search(query, limit=limit)

    async def recall_formatted(self, query: str, limit: int = 5) -> str:
        """
        Search and format results as a markdown string for context injection.

        Returns empty string if no results found.
        """
        results = await self.recall(query, limit=limit)
        if not results:
            return ""

        parts = ["## Relevant Memories"]
        for i, entry in enumerate(results, 1):
            content = entry.get("content", "").strip()
            if content:
                parts.append(f"\n### Memory {i}\n{content}")

        return "\n".join(parts)

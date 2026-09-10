"""
Context assembler.

Builds the full system prompt for an agent by concatenating:
1. Main prompt body (from .prompt.md, with variable interpolation)
2. Static context files (.context.md)
3. Long-term memory (.memory.md or vector store)
4. Session notes (scratchpad summaries from prior nodes)
"""
from __future__ import annotations

import logging
from typing import Any

from agentflow.agent.prompt import PromptTemplate
from agentflow.config.schemas import AgentConfig
from agentflow.protocols import MemoryStore, StorageBackend

logger = logging.getLogger("agentflow.agent.context")


class ContextAssembler:
    """Builds complete system prompt from multiple context sources."""

    def __init__(
        self,
        storage: StorageBackend | None = None,
        memory: MemoryStore | None = None,
    ):
        self._storage = storage
        self._memory = memory

    async def assemble(
        self,
        config: AgentConfig,
        prompt_body: str,
        variables: dict[str, Any] | None = None,
        session_id: str | None = None,
        query: str | None = None,
    ) -> str:
        """
        Assemble the full system prompt.

        Args:
            config: Agent config with context_files list
            prompt_body: Raw markdown body from the .prompt.md file
            variables: Template variables (date, user_name, etc.)
            session_id: Current session ID for loading session notes
            query: Recent user message for memory retrieval
        """
        parts: list[str] = []

        # 1. Main prompt with variable interpolation
        template = PromptTemplate(prompt_body)
        parts.append(template.render(variables))

        # 2. Static context files
        if self._storage and config.context_files:
            for ctx_file in config.context_files:
                content = await self._storage.read(f"agents/{ctx_file}")
                if content:
                    parts.append(f"\n---\n{content}")

        # 3. Long-term memory
        if self._memory and query:
            try:
                memories = await self._memory.search(query, limit=5)
                if memories:
                    memory_text = "\n".join(
                        m.get("content", "") for m in memories if m.get("content")
                    )
                    if memory_text:
                        parts.append(f"\n---\n## Relevant Memory\n{memory_text}")
            except Exception:
                logger.warning("Memory search failed", exc_info=True)

        # 4. Session notes
        if self._storage and session_id:
            session_context = await self._load_session_notes(session_id)
            if session_context:
                parts.append(f"\n---\n## Session Context\n{session_context}")

        return "\n".join(parts)

    async def _load_session_notes(self, session_id: str) -> str | None:
        """Load all *_summary.md files from the session directory."""
        if not self._storage:
            return None

        prefix = f"sessions/{session_id}/"
        files = await self._storage.list(prefix)
        summaries = [f for f in files if f.endswith("_summary.md")]

        if not summaries:
            return None

        parts = []
        for path in summaries:
            content = await self._storage.read(path)
            if content:
                parts.append(content)
        return "\n\n".join(parts) if parts else None

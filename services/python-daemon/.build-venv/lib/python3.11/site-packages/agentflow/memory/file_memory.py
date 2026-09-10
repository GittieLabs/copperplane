"""
File-based memory backend.

Implements the MemoryStore protocol using markdown files with YAML metadata.
Each memory entry is a file:

    agents/<agent>_memories/<timestamp>.md
    ---
    created_at: 2026-03-09T12:00:00Z
    tags: [search, weather]
    ---
    User asked about weather in Philadelphia. Prefers detailed forecasts.

Simple substring search — suitable for low-volume use. For semantic search
at scale, use VectorMemory (Phase 5) with Qdrant instead.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agentflow.protocols import StorageBackend

logger = logging.getLogger("agentflow.memory")


class FileMemory:
    """
    MemoryStore implementation backed by markdown files.

    Stores entries as individual .md files and searches via substring matching.
    """

    def __init__(self, storage: StorageBackend, agent: str = "default") -> None:
        self._storage = storage
        self._prefix = f"agents/{agent}_memories"

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """
        Store a memory entry. Returns the storage path.

        Creates a timestamped .md file with optional YAML front-matter metadata.
        """
        meta = metadata or {}
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        path = f"{self._prefix}/{timestamp}.md"

        # Build front-matter
        lines = ["---"]
        lines.append(f"created_at: {datetime.now(timezone.utc).isoformat()}")
        if "tags" in meta:
            tags_str = ", ".join(meta["tags"])
            lines.append(f"tags: [{tags_str}]")
        for key, val in meta.items():
            if key != "tags":
                lines.append(f"{key}: {val}")
        lines.append("---")
        lines.append(content)

        await self._storage.write(path, "\n".join(lines))
        logger.debug("Stored memory: %s", path)
        return path

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search memories by substring match.

        Returns the most recent matching entries (up to `limit`).
        Each result has 'content', 'path', and 'score' (1.0 for match, 0.0 otherwise).
        """
        files = await self._storage.list(self._prefix)
        # Sort descending (newest first) since filenames are timestamps
        files.sort(reverse=True)

        query_lower = query.lower()
        results: list[dict[str, Any]] = []

        for path in files:
            if len(results) >= limit:
                break

            raw = await self._storage.read(path)
            if raw is None:
                continue

            # Extract body (after front-matter)
            body = self._extract_body(raw)
            if query_lower in body.lower():
                results.append({
                    "content": body,
                    "path": path,
                    "score": 1.0,
                })

        return results

    async def list_entries(self) -> list[str]:
        """List all memory entry paths."""
        return await self._storage.list(self._prefix)

    async def delete(self, path: str) -> None:
        """Delete a specific memory entry."""
        await self._storage.delete(path)

    @staticmethod
    def _extract_body(raw: str) -> str:
        """Extract the body after YAML front-matter (--- ... ---)."""
        if not raw.startswith("---"):
            return raw
        # Find the closing ---
        end = raw.find("---", 3)
        if end == -1:
            return raw
        return raw[end + 3:].strip()

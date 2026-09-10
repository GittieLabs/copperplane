"""
Artifact store.

Typed file storage within a session directory. Artifacts are named outputs
from agent nodes — documents, images, data files, etc.

Convention:
    sessions/<session_id>/artifacts/<filename>
"""
from __future__ import annotations

import json
from typing import Any

from agentflow.protocols import StorageBackend


class ArtifactStore:
    """
    Read/write artifacts within a session directory.

    Supports text files directly and JSON-serializable objects via
    store_json/load_json convenience methods.
    """

    def __init__(self, storage: StorageBackend, session_id: str) -> None:
        self._storage = storage
        self._prefix = f"sessions/{session_id}/artifacts"

    def _path(self, name: str) -> str:
        return f"{self._prefix}/{name}"

    async def store(self, name: str, content: str) -> str:
        """Store a text artifact. Returns the storage path."""
        path = self._path(name)
        await self._storage.write(path, content)
        return path

    async def load(self, name: str) -> str | None:
        """Load a text artifact by name."""
        return await self._storage.read(self._path(name))

    async def store_json(self, name: str, data: Any) -> str:
        """Store a JSON-serializable artifact."""
        return await self.store(name, json.dumps(data, indent=2))

    async def load_json(self, name: str) -> Any | None:
        """Load a JSON artifact, returning the parsed object."""
        raw = await self.load(name)
        if raw is None:
            return None
        return json.loads(raw)

    async def exists(self, name: str) -> bool:
        """Check if an artifact exists."""
        return await self._storage.exists(self._path(name))

    async def list_artifacts(self) -> list[str]:
        """List all artifact names in this session."""
        files = await self._storage.list(self._prefix)
        prefix_len = len(self._prefix) + 1  # +1 for trailing /
        return [f[prefix_len:] for f in files if len(f) > prefix_len]

    async def delete(self, name: str) -> None:
        """Delete an artifact."""
        await self._storage.delete(self._path(name))

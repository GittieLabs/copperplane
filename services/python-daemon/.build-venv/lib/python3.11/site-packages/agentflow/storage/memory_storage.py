"""
In-memory storage backend for testing.

Dict-backed implementation of StorageBackend — no filesystem or network needed.
"""
from __future__ import annotations


class InMemoryStorage:
    """StorageBackend implementation backed by a plain dict."""

    def __init__(self) -> None:
        self._files: dict[str, str] = {}

    async def read(self, path: str) -> str | None:
        return self._files.get(path)

    async def write(self, path: str, content: str) -> None:
        self._files[path] = content

    async def exists(self, path: str) -> bool:
        return path in self._files

    async def list(self, prefix: str) -> list[str]:
        return sorted(k for k in self._files if k.startswith(prefix))

    async def delete(self, path: str) -> None:
        self._files.pop(path, None)

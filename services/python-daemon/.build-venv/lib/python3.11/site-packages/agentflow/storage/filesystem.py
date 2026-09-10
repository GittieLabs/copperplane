"""
Local filesystem storage backend.

Default backend for development — reads/writes files to a base directory.
"""
from __future__ import annotations

import os
from pathlib import Path


class FileSystemStorage:
    """StorageBackend implementation backed by the local filesystem."""

    def __init__(self, base_dir: str | Path):
        self._base = Path(base_dir)

    def _resolve(self, path: str) -> Path:
        return self._base / path

    async def read(self, path: str) -> str | None:
        fp = self._resolve(path)
        if not fp.exists():
            return None
        return fp.read_text(encoding="utf-8")

    async def write(self, path: str, content: str) -> None:
        fp = self._resolve(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")

    async def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    async def list(self, prefix: str) -> list[str]:
        base = self._resolve(prefix)
        if not base.exists():
            return []
        result = []
        for root, _dirs, files in os.walk(base):
            for f in sorted(files):
                full = Path(root) / f
                result.append(str(full.relative_to(self._base)))
        return result

    async def delete(self, path: str) -> None:
        fp = self._resolve(path)
        if fp.exists():
            fp.unlink()

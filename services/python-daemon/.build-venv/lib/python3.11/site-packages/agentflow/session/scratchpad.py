"""
Per-node scratchpad.

Each node in a workflow gets two files:
- *_scratch.md — working notes the agent reads/writes during execution
- *_summary.md — a distilled summary written at the end of the node

The ContextAssembler already loads *_summary.md files to inject prior-node
context into downstream agents.
"""
from __future__ import annotations

from agentflow.protocols import StorageBackend


class Scratchpad:
    """
    Read/write scratchpad files for a specific node within a session.

    Convention:
        sessions/<session_id>/<workflow>/<node_id>_scratch.md
        sessions/<session_id>/<workflow>/<node_id>_summary.md
    """

    def __init__(
        self,
        storage: StorageBackend,
        session_id: str,
        node_id: str,
        workflow: str = "default",
    ) -> None:
        self._storage = storage
        self._base = f"sessions/{session_id}/{workflow}"
        self._node_id = node_id

    @property
    def scratch_path(self) -> str:
        return f"{self._base}/{self._node_id}_scratch.md"

    @property
    def summary_path(self) -> str:
        return f"{self._base}/{self._node_id}_summary.md"

    async def read_scratch(self) -> str | None:
        """Read the working scratch notes."""
        return await self._storage.read(self.scratch_path)

    async def write_scratch(self, content: str) -> None:
        """Write or overwrite the working scratch notes."""
        await self._storage.write(self.scratch_path, content)

    async def append_scratch(self, content: str) -> None:
        """Append to existing scratch notes."""
        existing = await self.read_scratch() or ""
        separator = "\n\n" if existing else ""
        await self._storage.write(self.scratch_path, f"{existing}{separator}{content}")

    async def read_summary(self) -> str | None:
        """Read the node summary."""
        return await self._storage.read(self.summary_path)

    async def write_summary(self, content: str) -> None:
        """Write the node summary (typically at the end of execution)."""
        await self._storage.write(self.summary_path, content)

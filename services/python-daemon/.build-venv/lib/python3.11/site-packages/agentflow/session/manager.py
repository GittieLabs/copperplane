"""
Session manager.

Creates, loads, and manages session lifecycles. Each session is a directory
in storage containing session metadata and per-node scratchpads/artifacts.

Session directory convention:
    sessions/<session-id>/
        session.json            — metadata (created_at, agent, status)
        <workflow>/<node>_scratch.md
        <workflow>/<node>_summary.md
        artifacts/<filename>
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from agentflow.protocols import StorageBackend

logger = logging.getLogger("agentflow.session")


@dataclass
class Session:
    """Represents an active or completed session."""

    id: str
    created_at: str
    agent: str = ""
    workflow: str = ""
    status: str = "active"  # active | completed | error
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            agent=data.get("agent", ""),
            workflow=data.get("workflow", ""),
            status=data.get("status", "active"),
            metadata=data.get("metadata", {}),
        )


class SessionManager:
    """
    Creates and manages sessions backed by a StorageBackend.

    Sessions are lightweight — just a JSON metadata file plus a directory
    convention for scratchpads and artifacts.
    """

    def __init__(self, storage: StorageBackend) -> None:
        self._storage = storage

    async def create(
        self,
        agent: str = "",
        workflow: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Create a new session with a unique ID."""
        session = Session(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            agent=agent,
            workflow=workflow,
            metadata=metadata or {},
        )
        await self._save(session)
        logger.info("Created session %s (agent=%s, workflow=%s)", session.id, agent, workflow)
        return session

    async def get(self, session_id: str) -> Session | None:
        """Load an existing session by ID. Returns None if not found."""
        path = f"sessions/{session_id}/session.json"
        raw = await self._storage.read(path)
        if raw is None:
            return None
        try:
            return Session.from_dict(json.loads(raw))
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupt session file: %s", path)
            return None

    async def update_status(self, session_id: str, status: str) -> None:
        """Update a session's status (active -> completed | error)."""
        session = await self.get(session_id)
        if session:
            session.status = status
            await self._save(session)

    async def list_sessions(self, prefix: str = "sessions/") -> list[str]:
        """List all session IDs."""
        files = await self._storage.list(prefix)
        # Extract session IDs from paths like sessions/<id>/session.json
        ids = set()
        for f in files:
            parts = f.split("/")
            if len(parts) >= 3 and parts[0] == "sessions":
                ids.add(parts[1])
        return sorted(ids)

    async def _save(self, session: Session) -> None:
        path = f"sessions/{session.id}/session.json"
        await self._storage.write(path, json.dumps(session.to_dict(), indent=2))

"""
Multi-user conversation history manager.

Generic per-user in-memory history with an optional abstract persistence hook.
Applications that store history in a database (e.g. PostgreSQL) implement the
HistoryPersistence protocol and pass an instance to MultiUserHistory.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Protocol, runtime_checkable

from agentflow.types import Message, Role


MAX_DEFAULT = 50


@runtime_checkable
class HistoryPersistence(Protocol):
    """Protocol for pluggable conversation history persistence backends."""

    async def load(self, user_id: str) -> list[Message]:
        """Load stored messages for a user. Return empty list if none."""
        ...

    async def save(self, user_id: str, messages: list[Message]) -> None:
        """Persist the current in-memory messages for a user."""
        ...


class MultiUserHistory:
    """Per-user in-memory conversation history with configurable max and optional persistence.

    Usage:
        history = MultiUserHistory(max_history=50)
        history.append(user_id, Role.USER, "Hello")
        history.append(user_id, Role.ASSISTANT, "Hi there!")
        messages = history.get(user_id)  # [Message(role=USER, ...), Message(role=ASSISTANT, ...)]

    With PostgreSQL persistence:
        history = MultiUserHistory(max_history=50, persistence=postgres_adapter)
        await history.load(user_id)     # loads once per user per session
        history.append(...)
        await history.save(user_id)     # flush to DB
    """

    def __init__(
        self,
        max_history: int = MAX_DEFAULT,
        persistence: HistoryPersistence | None = None,
    ) -> None:
        self._history: dict[str, list[Message]] = defaultdict(list)
        self._loaded: set[str] = set()
        self._max = max_history
        self._persistence = persistence

    def get(self, user_id: str) -> list[Message]:
        """Return the current in-memory history for a user, trimming to max_history."""
        history = self._history[user_id]
        if len(history) > self._max:
            self._history[user_id] = history[-self._max:]
        return self._history[user_id]

    def append(self, user_id: str, role: Role, content: str) -> None:
        """Add a message to a user's history."""
        self._history[user_id].append(Message(role=role, content=content))

    def clear(self, user_id: str) -> None:
        """Discard all in-memory history for a user and reset the loaded flag."""
        self._history[user_id] = []
        self._loaded.discard(user_id)

    async def load(self, user_id: str) -> None:
        """Load persisted messages for a user (once per user per session).

        Subsequent calls for the same user_id are no-ops until clear() is called.
        """
        if user_id in self._loaded or self._persistence is None:
            return
        messages = await self._persistence.load(user_id)
        if messages:
            self._history[user_id] = messages[-self._max:]
        self._loaded.add(user_id)

    async def save(self, user_id: str) -> None:
        """Persist the current in-memory history for a user.

        No-op when no persistence backend is configured.
        """
        if self._persistence is None:
            return
        await self._persistence.save(user_id, self._history[user_id])

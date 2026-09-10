"""
Mock LLM provider for deterministic testing.

Returns scripted responses in order, making workflow and agent tests
fully reproducible without real API calls.
"""
from __future__ import annotations

from typing import Any

from agentflow.types import AgentResponse, Message


class MockLLMProvider:
    """LLMProvider that returns pre-defined responses in sequence."""

    def __init__(self, responses: list[AgentResponse] | None = None):
        self._responses = list(responses) if responses else []
        self._call_index = 0
        self.calls: list[dict[str, Any]] = []  # Record all calls for assertions

    def add_response(self, response: AgentResponse) -> None:
        """Add a response to the queue."""
        self._responses.append(response)

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        params: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Return the next scripted response."""
        self.calls.append({
            "messages": messages,
            "system": system,
            "tools": tools,
            "params": params,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })

        if self._call_index >= len(self._responses):
            return AgentResponse(text="[MockLLM: no more responses]", stop_reason="end_turn")

        response = self._responses[self._call_index]
        self._call_index += 1
        return response

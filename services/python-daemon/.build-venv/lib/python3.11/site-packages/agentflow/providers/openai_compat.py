"""
OpenAI-compatible LLM provider.

Works with any API that implements the OpenAI /chat/completions format:
- OpenAI (GPT-4o, etc.)
- Perplexity Sonar
- Groq
- Together AI
- Ollama
- Any local model with OpenAI-compatible API

Uses the official openai SDK when available, falls back to httpx.
"""
from __future__ import annotations

import logging
from typing import Any

from agentflow.providers._params import merge_params
from agentflow.types import AgentResponse, Message, Role, ToolCall

logger = logging.getLogger("agentflow.providers.openai_compat")

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]


class OpenAICompatProvider:
    """
    LLMProvider for any OpenAI-compatible API.

    Uses the openai SDK if installed, which handles retries,
    streaming, and connection pooling.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
    ) -> None:
        if openai is None:
            raise ImportError("Install openai: pip install agentflow[openai]")

        self._model = model
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        params: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Send messages and return an AgentResponse.

        `params` is forwarded verbatim to `chat.completions.create`, which is
        how reasoning effort reaches OpenAI -- e.g.
        `params={"reasoning_effort": "high"}`. Note this provider serves any
        OpenAI-compatible server, and a local Ollama or a Perplexity endpoint
        need not honour an OpenAI-specific parameter; a silently ignored
        parameter is the caller's business, per the module docstring in
        `_params`.
        """
        api_messages = self._to_api_messages(messages, system)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if tools:
            kwargs["tools"] = self._to_api_tools(tools)

        merge_params(kwargs, params, provider="openai_compat")

        response = await self._client.chat.completions.create(**kwargs)
        return self._from_api_response(response)

    def _to_api_messages(self, messages: list[Message], system: str) -> list[dict[str, Any]]:
        """Convert agentflow Messages to OpenAI format."""
        api_msgs: list[dict[str, Any]] = []

        if system:
            api_msgs.append({"role": "system", "content": system})

        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue

            if msg.role == Role.TOOL_RESULT:
                for tr in msg.tool_results:
                    api_msgs.append({
                        "role": "tool",
                        "tool_call_id": tr.tool_call_id,
                        "content": tr.content,
                    })
            elif msg.tool_calls:
                # Assistant message with tool calls
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": _json_dumps(tc.input),
                        },
                    }
                    for tc in msg.tool_calls
                ]
                api_msgs.append({
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": tool_calls,
                })
            else:
                api_msgs.append({
                    "role": msg.role.value,
                    "content": msg.content,
                })

        return api_msgs

    def _to_api_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert agentflow tool definitions to OpenAI function-calling format."""
        api_tools = []
        for tool in tools:
            api_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
        return api_tools

    def _from_api_response(self, response: Any) -> AgentResponse:
        """Convert OpenAI response to AgentResponse."""
        choice = response.choices[0]
        msg = choice.message

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    input=_json_loads(tc.function.arguments),
                ))

        stop_reason = "tool_use" if choice.finish_reason == "tool_calls" else "end_turn"

        usage = {}
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }

        return AgentResponse(
            text=msg.content or "",
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            raw=response,
        )


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj)


def _json_loads(s: str) -> dict[str, Any]:
    import json
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}

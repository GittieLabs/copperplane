"""
Anthropic Claude LLM provider.

Translates between agentflow's canonical types and the Anthropic SDK's
message format, including tool use.
"""
from __future__ import annotations

import logging
import inspect
from typing import Any

from agentflow.providers._params import merge_params
from agentflow.types import AgentResponse, Message, Role, ToolCall

logger = logging.getLogger("agentflow.providers.anthropic")

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]


# Anthropic's newest reasoning model lines (first hit: claude-sonnet-5)
# reject `temperature` outright once thinking is active, and use an
# adaptive-thinking + effort interface rather than the older fixed
# `budget_tokens` one.
#
# Until 0.11.0 that was selected by a `-low`/`-medium`/`-high` model-name
# suffix, parsed with `rsplit("-", 1)`. That was removed: it silently
# truncated any legitimate model whose real name ended in one of those
# words, was invisible to callers, and had no equivalent on
# openai_compat -- so the same request meant different things depending
# on which provider served it. Effort now arrives through `params`,
# where the caller states it explicitly.
def _accepts_temperature(create_method) -> bool:
    """Whether the installed anthropic SDK's `messages.create` still takes
    `temperature`.

    The SDK removed it in the 1.x line. Sending it there raises a plain
    `TypeError` **client-side, before any network call**, which the
    BadRequestError retry below cannot catch -- so every chat with a
    non-1.0 temperature failed outright against anthropic>=1.0.

    Resolved by introspection rather than a version comparison: the
    parameter's presence is the thing that actually matters, and a version
    check would need updating for every future SDK release, which is the
    same trap the model-suffix convention fell into. Verified to match
    runtime behaviour exactly -- the TypeError is raised by Python's own
    argument binding, which is what `signature` describes.

    Returns True when it cannot tell, so an SDK this cannot introspect
    behaves as it did before rather than silently dropping a parameter.
    A callable taking `**kwargs` accepts anything, so it counts as
    accepting `temperature` -- that covers test doubles and any wrapper
    that forwards blindly, both of which would otherwise be misread as a
    new SDK and quietly lose the parameter.
    """
    try:
        params = inspect.signature(create_method).parameters
    except (TypeError, ValueError):
        return True
    if "temperature" in params:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


class AnthropicProvider:
    """LLMProvider implementation for Anthropic Claude models."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-5",
    ):
        if anthropic is None:
            raise ImportError("Install anthropic: pip install agentflow[anthropic]")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        params: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Send messages to Claude and return an AgentResponse.

        `params` is forwarded verbatim to `messages.create`. Reasoning effort
        is set this way -- e.g. `params={"thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"}}` -- rather than by decorating the
        model name, which 0.11.0 removed (see the module changelog entry).
        """
        api_messages = self._to_api_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": api_messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        # Adaptive thinking requires temperature to be entirely absent from
        # the request, not merely set to 1. A caller enabling it through
        # `params` therefore must not also be sent a temperature, so this
        # decision is made from `params` rather than from a decorated model.
        wants_thinking = bool(params) and "thinking" in params
        if (
            temperature != 1.0
            and not wants_thinking
            and _accepts_temperature(self._client.messages.create)
        ):
            kwargs["temperature"] = temperature

        merge_params(kwargs, params, provider="anthropic")

        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.BadRequestError as e:
            # Some Claude model lines reject `temperature` outright even
            # with no explicit thinking suffix (first hit: bare
            # `claude-sonnet-5`, thinking on by default) -- retry once
            # without it rather than hardcoding a model-name allowlist
            # that would need updating for every future model release,
            # the exact problem this fix exists to get away from.
            body = e.body if isinstance(e.body, dict) else {}
            error_message = body.get("error", {}).get("message", "")
            if "temperature" in kwargs and "temperature" in error_message and "deprecated" in error_message:
                del kwargs["temperature"]
                response = await self._client.messages.create(**kwargs)
            else:
                raise

        return self._from_api_response(response)

    def _to_api_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert agentflow Messages to Anthropic API format."""
        api_msgs: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue  # System is passed separately
            if msg.role == Role.TOOL_RESULT:
                # Tool results are sent as "user" role with tool_result content blocks
                content = [
                    {
                        "type": "tool_result",
                        "tool_use_id": tr.tool_call_id,
                        "content": tr.content,
                        **({"is_error": True} if tr.is_error else {}),
                    }
                    for tr in msg.tool_results
                ]
                api_msgs.append({"role": "user", "content": content})
            elif msg.tool_calls:
                # Assistant message with tool use — reconstruct content blocks
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.input,
                    })
                api_msgs.append({"role": "assistant", "content": content})
            else:
                api_msgs.append({"role": msg.role.value, "content": msg.content})
        return api_msgs

    def _from_api_response(self, response: Any) -> AgentResponse:
        """Convert Anthropic API response to AgentResponse."""
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )

        return AgentResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason="tool_use" if response.stop_reason == "tool_use" else "end_turn",
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            raw=response,
        )

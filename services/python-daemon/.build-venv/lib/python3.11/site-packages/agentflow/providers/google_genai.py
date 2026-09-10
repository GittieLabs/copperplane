"""
Google Gemini LLM provider.

Wraps the google-genai SDK to implement the LLMProvider protocol.
Handles translation between agentflow types and Gemini's contents/parts format.

Gemini differences from Anthropic/OpenAI:
- Uses "model" role instead of "assistant"
- Content is structured as parts: [{text: "..."}, {functionCall: ...}]
- Tool definitions use "function_declarations" instead of tool schemas
- System instruction is a separate config parameter, not a message
"""
from __future__ import annotations

import logging
from typing import Any

from agentflow.providers._params import merge_params
from agentflow.types import AgentResponse, Message, Role, ToolCall

logger = logging.getLogger("agentflow.providers.google_genai")

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]


class GoogleGenAIProvider:
    """
    LLMProvider implementation for Google Gemini models.

    Uses the google-genai SDK's async interface.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-flash-latest",
    ) -> None:
        if genai is None:
            raise ImportError("Install google-genai: pip install agentflow[google]")

        self._client = genai.Client(api_key=api_key)
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
        """Send messages to Gemini and return an AgentResponse.

        `params` is forwarded verbatim into `GenerateContentConfig`, which is
        how thinking level reaches Gemini -- e.g.
        `params={"thinking_config": {"thinking_level": "high"}}` -- rather
        than by decorating the model name, which 0.11.0 removed.
        """
        contents = self._to_api_contents(messages)

        current_model = self._model

        config_kwargs: dict[str, Any] = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
        # Thinking level and anything else vendor-specific arrives through
        # `params` and lands inside GenerateContentConfig, where Gemini's own
        # SDK expects it.
        merge_params(config_kwargs, params, provider="google_genai")
        if system:
            config_kwargs["system_instruction"] = system

        config = genai_types.GenerateContentConfig(**config_kwargs)

        kwargs: dict[str, Any] = {
            "model": current_model,
            "contents": contents,
            "config": config,
        }

        if tools:
            kwargs["config"] = genai_types.GenerateContentConfig(
                **config_kwargs,
                tools=[self._to_api_tools(tools)],
            )

        response = await self._client.aio.models.generate_content(**kwargs)
        return self._from_api_response(response)

    def _to_api_contents(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert agentflow Messages to Gemini contents format."""
        contents: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue  # System is passed via config

            if msg.role == Role.TOOL_RESULT:
                # Gemini expects function responses as user-role parts
                parts = []
                for tr in msg.tool_results:
                    parts.append({
                        "function_response": {
                            "name": tr.tool_call_id,  # Gemini uses name, not ID
                            "response": {"result": tr.content},
                        }
                    })
                contents.append({"role": "user", "parts": parts})

            elif msg.role == Role.ASSISTANT:
                # For Gemini thinking models, preserve the raw candidate content
                # to keep thought_signature intact. Without this, the API returns
                # 400 INVALID_ARGUMENT on subsequent turns.
                raw_response = msg.metadata.get("_raw_response") if msg.metadata else None
                if (
                    raw_response is not None
                    and hasattr(raw_response, "candidates")
                    and raw_response.candidates
                    and raw_response.candidates[0].content
                ):
                    contents.append(raw_response.candidates[0].content)
                else:
                    # Fallback: reconstruct (works for non-thinking models)
                    parts: list[dict[str, Any]] = []
                    if msg.content:
                        parts.append({"text": msg.content})
                    for tc in msg.tool_calls:
                        parts.append({
                            "function_call": {
                                "name": tc.name,
                                "args": tc.input,
                            }
                        })
                    contents.append({"role": "model", "parts": parts})

            elif msg.role == Role.USER:
                contents.append({
                    "role": "user",
                    "parts": [{"text": msg.content}],
                })

        return contents

    def _to_api_tools(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Convert agentflow tool definitions to Gemini function_declarations."""
        declarations = []
        for tool in tools:
            decl: dict[str, Any] = {
                "name": tool["name"],
                "description": tool.get("description", ""),
            }
            schema = tool.get("input_schema", {})
            if schema:
                decl["parameters"] = schema
            declarations.append(decl)

        return {"function_declarations": declarations}

    def _from_api_response(self, response: Any) -> AgentResponse:
        """Convert Gemini response to AgentResponse.

        Separates thinking parts (part.thought == True) from response parts
        so callers can surface reasoning independently (e.g. as trace events).
        Thinking text is stored in AgentResponse metadata["thinking"].
        """
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        # Gemini response has candidates[0].content.parts
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    # Thinking models emit thought parts with part.thought == True
                    is_thought = getattr(part, "thought", False)
                    if is_thought:
                        if hasattr(part, "text") and part.text:
                            thinking_parts.append(part.text)
                    elif hasattr(part, "text") and part.text:
                        text_parts.append(part.text)
                    elif hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        args = dict(fc.args) if fc.args else {}
                        tool_calls.append(ToolCall(
                            id=fc.name,  # Gemini uses name as ID
                            name=fc.name,
                            input=args,
                        ))

        stop_reason = "tool_use" if tool_calls else "end_turn"

        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "input_tokens": getattr(um, "prompt_token_count", 0),
                "output_tokens": getattr(um, "candidates_token_count", 0),
                "thinking_tokens": getattr(um, "thoughts_token_count", 0),
            }

        metadata: dict[str, Any] = {}
        if thinking_parts:
            metadata["thinking"] = "".join(thinking_parts)

        return AgentResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            raw=response,
            metadata=metadata,
        )

"""
Agent executor — the core execution unit.

Loads agent config, assembles context, calls the LLM, handles tool-use loops,
and returns structured output. This replaces the per-agent execution logic
that was previously hardcoded in OpenClaw's runtime.py.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from agentflow.agent.context import ContextAssembler
from agentflow.config.schemas import AgentConfig
from agentflow.events import EventBus, TOOL_CALLED, TOOL_RESULT, ERROR, LLM_CALL_STARTED, LLM_CALL_COMPLETED
from agentflow.protocols import LLMProvider, ToolDispatcher
from agentflow.tools.http_dispatcher import last_raw_tool_result
from agentflow.types import Message, NodeOutput, Role, ToolResult

logger = logging.getLogger("agentflow.agent")


class AgentExecutor:
    """
    Executes a single agent: assembles context, calls LLM, handles tool loops.

    This is the per-node execution unit used both for standalone agent calls
    and as part of workflow DAG execution.
    """

    def __init__(
        self,
        config: AgentConfig,
        prompt_body: str,
        llm: LLMProvider,
        tools: ToolDispatcher | None = None,
        context_assembler: ContextAssembler | None = None,
        event_bus: EventBus | None = None,
    ):
        self._config = config
        self._prompt_body = prompt_body
        self._llm = llm
        self._tools = tools
        self._context = context_assembler
        self._events = event_bus

    @property
    def config(self) -> AgentConfig:
        return self._config

    async def run(
        self,
        message: str,
        session_id: str | None = None,
        node_id: str | None = None,
        history: list[Message] | None = None,
        variables: dict[str, Any] | None = None,
    ) -> NodeOutput:
        """
        Execute the agent with the given message.

        Args:
            message: User/input message to process
            session_id: Optional session ID for context loading
            node_id: Optional node ID when running as part of a workflow
            history: Optional conversation history to continue
            variables: Template variables for prompt rendering

        Returns:
            NodeOutput with the agent's response text and metadata
        """
        # Assemble system prompt
        if self._context:
            system = await self._context.assemble(
                config=self._config,
                prompt_body=self._prompt_body,
                variables=variables,
                session_id=session_id,
                query=message,
            )
        else:
            from agentflow.agent.prompt import PromptTemplate
            system = PromptTemplate(self._prompt_body).render(variables)

        # Build messages
        messages = list(history) if history else []
        messages.append(Message(role=Role.USER, content=message))

        # Get tool definitions, filtered by agent config if specified
        if self._tools:
            all_tool_defs = self._tools.list_tools()
            if self._config.tools:
                allowed = set(self._config.tools)
                tool_defs = [t for t in all_tool_defs if t["name"] in allowed]
            else:
                tool_defs = all_tool_defs
        else:
            tool_defs = None

        # Tool-use loop
        tool_calls_log: list[dict[str, Any]] = []
        for round_num in range(self._config.max_tool_rounds):
            t0 = time.monotonic()
            if self._events:
                await self._events.emit(LLM_CALL_STARTED, {
                    "agent": self._config.name,
                    "model": self._config.model,
                    "node": node_id,
                    "session_id": session_id,
                    "round": round_num,
                })

            response = await self._llm.chat(
                messages=messages,
                system=system,
                tools=tool_defs,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                params=self._config.params or None,
            )

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            if self._events:
                await self._events.emit(LLM_CALL_COMPLETED, {
                    "agent": self._config.name,
                    "model": self._config.model,
                    "node": node_id,
                    "session_id": session_id,
                    "round": round_num,
                    "stop_reason": response.stop_reason,
                    "input_tokens": response.usage.get("input_tokens", 0) if response.usage else 0,
                    "output_tokens": response.usage.get("output_tokens", 0) if response.usage else 0,
                    "elapsed_ms": elapsed_ms,
                    "tool_calls": len(response.tool_calls),
                })

            # Emit thinking text as a trace event (Gemini thinking models only).
            # This is separated from response text in the provider's _from_api_response.
            # Checks the raw response directly since AgentResponse doesn't carry metadata yet.
            if self._events and hasattr(response, "raw") and response.raw:
                raw = response.raw
                if hasattr(raw, "candidates") and raw.candidates:
                    candidate = raw.candidates[0]
                    if candidate.content and candidate.content.parts:
                        thought_parts = [
                            getattr(p, "text", "") or ""
                            for p in candidate.content.parts
                            if getattr(p, "thought", False)
                        ]
                        if thought_parts:
                            await self._events.emit("thinking", {
                                "agent": self._config.name,
                                "round": round_num,
                                "thinking": "".join(thought_parts)[:1000],  # cap for WS
                            })

            if response.stop_reason == "tool_use" and response.tool_calls and self._tools:
                # Add assistant message with tool calls to history.
                # Store raw response so providers (e.g. Gemini thinking models)
                # can preserve thought_signature when replaying history.
                messages.append(Message(
                    role=Role.ASSISTANT,
                    content=response.text,
                    tool_calls=response.tool_calls,
                    metadata={"_raw_response": response.raw},
                ))

                # Dispatch each tool call
                results: list[ToolResult] = []
                for tc in response.tool_calls:
                    if self._events:
                        await self._events.emit(TOOL_CALLED, {
                            "tool": tc.name,
                            "input": tc.input,
                            "round": round_num,
                        })

                    try:
                        result_str = await self._tools.dispatch(tc.name, tc.input)
                        is_error = False
                    except Exception as exc:
                        result_str = f"Tool error: {exc}"
                        is_error = True
                        if self._events:
                            await self._events.emit(ERROR, {
                                "tool": tc.name,
                                "error": str(exc),
                            })

                    results.append(ToolResult(
                        tool_call_id=tc.id,
                        content=result_str,
                        is_error=is_error,
                    ))
                    tool_calls_log.append({
                        "name": tc.name,
                        "input": tc.input,
                        "result": result_str,
                        "is_error": is_error,
                    })

                    if self._events:
                        raw = last_raw_tool_result.get()
                        last_raw_tool_result.set(None)
                        await self._events.emit(TOOL_RESULT, {
                            "tool": tc.name,
                            "input": tc.input,
                            "result": result_str,
                            "raw_result": raw,
                            "result_length": len(result_str),
                            "is_error": is_error,
                        })

                # Add tool results to history
                messages.append(Message(
                    role=Role.TOOL_RESULT,
                    content="",
                    tool_results=results,
                ))
                continue

            # No tool use — we're done
            return NodeOutput(
                node_id=node_id or "default",
                agent_id=self._config.name,
                text=response.text,
                metadata={"usage": response.usage, "rounds": round_num + 1, "tool_calls": tool_calls_log},
            )

        # Exhausted tool rounds — return accumulated tool results instead of an error
        logger.warning("Agent %s exhausted %d tool rounds", self._config.name, self._config.max_tool_rounds)
        accumulated = []
        for msg in messages:
            if msg.role == Role.TOOL_RESULT:
                for tr in msg.tool_results:
                    if tr.content and not tr.is_error:
                        accumulated.append(tr.content)
        fallback_text = "\n\n".join(accumulated) if accumulated else "No results found."
        return NodeOutput(
            node_id=node_id or "default",
            agent_id=self._config.name,
            text=fallback_text,
            metadata={"exhausted_rounds": True, "tool_calls": tool_calls_log},
        )

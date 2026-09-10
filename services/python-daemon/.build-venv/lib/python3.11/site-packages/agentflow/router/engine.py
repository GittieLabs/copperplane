"""
Router engine.

Combines YAML rule matching with optional LLM fallback for intent classification.
This is the main entry point for routing user messages to the right agent or workflow.

Flow:
1. Evaluate YAML rules in order → first match wins
2. If no rule matches and llmFallback is enabled → ask LLM to classify
3. If still no match → route to fallback agent
"""
from __future__ import annotations

import logging
from typing import Any

from agentflow.config.schemas import RouterConfig
from agentflow.events import EventBus, ROUTER_DECISION
from agentflow.protocols import LLMProvider
from agentflow.router.rules import RuleEvaluator
from agentflow.types import Message, Role

logger = logging.getLogger("agentflow.router")


class RoutingResult:
    """The outcome of a routing decision."""

    def __init__(
        self,
        target: str,
        method: str,
        confidence: float = 1.0,
        domain: str | None = None,
    ) -> None:
        self.target = target       # Agent or workflow name
        self.method = method       # "rule" | "llm" | "fallback" | "domain:*"
        self.confidence = confidence
        self.domain = domain       # Which domain handled this (None for flat routing)

    def __repr__(self) -> str:
        parts = f"target={self.target!r}, method={self.method!r}"
        if self.domain:
            parts += f", domain={self.domain!r}"
        return f"RoutingResult({parts})"


class RouterEngine:
    """
    Routes messages to agents/workflows using rules + optional LLM fallback.
    """

    def __init__(
        self,
        config: RouterConfig,
        router_prompt: str = "",
        available_targets: list[str] | None = None,
        llm: LLMProvider | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._config = config
        self._router_prompt = router_prompt
        self._available_targets = available_targets or []
        self._llm = llm
        self._events = event_bus
        self._evaluator = RuleEvaluator()

    async def route(self, message: str, context: dict[str, Any] | None = None) -> RoutingResult:
        """
        Route a message to the appropriate agent/workflow.

        Args:
            message: The user message to route
            context: Additional context (channel, intent, user metadata, etc.)

        Returns:
            RoutingResult with the target name and the method used
        """
        ctx = dict(context) if context else {}
        ctx.setdefault("message", message)

        # Step 1: Try YAML rules
        target = self._evaluator.match(self._config.routing_rules, ctx)
        if target:
            result = RoutingResult(target=target, method="rule")
            await self._emit(result, ctx)
            return result

        # Step 2: LLM fallback
        if self._config.llm_fallback and self._llm and self._available_targets:
            target = await self._llm_classify(message)
            if target:
                result = RoutingResult(target=target, method="llm", confidence=0.8)
                await self._emit(result, ctx)
                return result

        # Step 3: Static fallback
        result = RoutingResult(target=self._config.fallback, method="fallback")
        await self._emit(result, ctx)
        return result

    async def _llm_classify(self, message: str) -> str | None:
        """Ask the LLM to classify the message into one of the available targets."""
        targets_str = ", ".join(self._available_targets)
        system = self._router_prompt or (
            f"You are a routing classifier. Given a user message, respond with ONLY "
            f"the name of the most appropriate handler from this list: [{targets_str}]. "
            f"Respond with just the name, nothing else."
        )

        try:
            response = await self._llm.chat(
                messages=[Message(role=Role.USER, content=message)],
                system=system,
                max_tokens=50,
                temperature=0.0,
            )
            candidate = response.text.strip().lower()

            # Validate the LLM's choice is actually in our target list
            # Normalize both sides: replace spaces with underscores for comparison
            norm_candidate = candidate.replace(" ", "_").replace("-", "_")
            for target in self._available_targets:
                norm_target = target.lower().replace(" ", "_").replace("-", "_")
                if norm_target == norm_candidate or target.lower() == candidate:
                    return target

            # Prefix fallback: if the LLM truncated the name (e.g. "contract_"),
            # match if it's a unique prefix of exactly one target.
            if len(norm_candidate) >= 4:
                prefix_matches = [
                    t for t in self._available_targets
                    if t.lower().replace(" ", "_").replace("-", "_").startswith(norm_candidate)
                ]
                if len(prefix_matches) == 1:
                    logger.info("LLM routing matched by prefix: %s → %s", candidate, prefix_matches[0])
                    return prefix_matches[0]

            logger.warning("LLM routing returned unknown target: %s", candidate)
            return None

        except Exception:
            logger.warning("LLM routing failed", exc_info=True)
            return None

    async def _emit(self, result: RoutingResult, context: dict[str, Any]) -> None:
        if self._events:
            await self._events.emit(ROUTER_DECISION, {
                "target": result.target,
                "method": result.method,
                "confidence": result.confidence,
            })

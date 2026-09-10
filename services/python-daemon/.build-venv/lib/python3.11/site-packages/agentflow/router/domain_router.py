"""
Two-tier domain router.

Composes a top-level ``RouterEngine`` (fast/cheap LLM for domain classification)
with per-domain ``RouterEngine`` instances (more capable LLM for intra-domain
routing to specific agents or workflows).

Flow:
1. Top-level router classifies message into a domain name (e.g. "content",
   "leadgen") or "direct" for requests the default agent can handle.
2. If "direct" (or the top-level fallback) → return immediately with the
   configured direct target.
3. Otherwise look up the ``DomainConfig`` for that domain, create/cache a
   domain-level ``RouterEngine``, and route to a specific agent or workflow.

The result always includes ``domain`` so callers can track which domain
handled a request (useful for scoped memory and telemetry).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from agentflow.config.loader import ConfigLoader
from agentflow.config.schemas import DomainConfig, RouterConfig
from agentflow.events import DOMAIN_ROUTED, EventBus
from agentflow.protocols import LLMProvider
from agentflow.router.engine import RouterEngine, RoutingResult

logger = logging.getLogger("agentflow.router.domain")

# Type for a factory that creates an LLMProvider for a given model name.
LLMFactory = Callable[[str], LLMProvider]


class DomainRouter:
    """Two-tier router: top-level domain classification → intra-domain routing.

    Args:
        top_router: The existing ``RouterEngine`` whose targets are domain names
            (plus "direct" for pass-through to the default agent).
        loader: ``ConfigLoader`` with domains loaded.
        llm_factory: Callable that creates an ``LLMProvider`` for a given model
            name.  Used to create domain-level routing LLMs.
        direct_target: Agent name to use when the top-level routes to "direct".
            Defaults to ``"openclaw_default"``.
        event_bus: Optional ``EventBus`` for emitting ``DOMAIN_ROUTED`` events.
    """

    def __init__(
        self,
        top_router: RouterEngine,
        loader: ConfigLoader,
        llm_factory: LLMFactory,
        direct_target: str = "openclaw_default",
        event_bus: EventBus | None = None,
    ) -> None:
        self._top = top_router
        self._loader = loader
        self._llm_factory = llm_factory
        self._direct_target = direct_target
        self._events = event_bus
        # Cache domain-level RouterEngine instances (created on first use)
        self._domain_routers: dict[str, RouterEngine] = {}

    async def route(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> RoutingResult:
        """Route a message through two tiers: domain → agent/workflow.

        Returns a ``RoutingResult`` with ``.domain`` set to the domain name
        (or ``"direct"`` for pass-through).
        """
        # ── Tier 1: classify into a domain ──────────────────────────────────
        top_result = await self._top.route(message, context=context)
        domain_name = top_result.target

        # "direct" or fallback → pass through to the default agent
        if domain_name == "direct" or domain_name == self._direct_target:
            result = RoutingResult(
                target=self._direct_target,
                method=f"domain:direct ({top_result.method})",
                confidence=top_result.confidence,
                domain="direct",
            )
            await self._emit(result, context)
            return result

        # ── Tier 2: intra-domain routing ────────────────────────────────────
        try:
            domain_config, domain_body = self._loader.get_domain(domain_name)
        except KeyError:
            logger.warning(
                "Top-level router selected unknown domain %r — falling back to direct",
                domain_name,
            )
            result = RoutingResult(
                target=self._direct_target,
                method="domain:unknown_fallback",
                domain="direct",
            )
            await self._emit(result, context)
            return result

        domain_router = self._get_domain_router(domain_name, domain_config, domain_body)
        domain_result = await domain_router.route(message, context=context)

        result = RoutingResult(
            target=domain_result.target,
            method=f"domain:{domain_name} ({domain_result.method})",
            confidence=domain_result.confidence,
            domain=domain_name,
        )
        await self._emit(result, context)
        return result

    def _get_domain_router(
        self,
        name: str,
        config: DomainConfig,
        body: str,
    ) -> RouterEngine:
        """Get or create a cached RouterEngine for a domain."""
        if name in self._domain_routers:
            return self._domain_routers[name]

        llm = self._llm_factory(config.router_model)

        router = RouterEngine(
            config=RouterConfig(
                name=f"domain_{name}_router",
                fallback=config.fallback or self._direct_target,
                llm_fallback=True,
            ),
            router_prompt=body,
            available_targets=config.available_targets,
            llm=llm,
            event_bus=self._events,
        )

        self._domain_routers[name] = router
        logger.info(
            "Created domain router for %r (%d targets, model=%s)",
            name, len(config.available_targets), config.router_model,
        )
        return router

    async def _emit(self, result: RoutingResult, context: dict[str, Any] | None) -> None:
        if self._events:
            await self._events.emit(DOMAIN_ROUTED, {
                "domain": result.domain,
                "target": result.target,
                "method": result.method,
                "confidence": result.confidence,
            })

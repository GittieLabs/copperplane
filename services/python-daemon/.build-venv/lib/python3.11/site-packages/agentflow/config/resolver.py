"""
Context resolver — expands context_files references with profile support.

Given an agent's `context_files` list (from .prompt.md front-matter), resolves
each entry by:
1. If the entry is a context profile (type: profile), expand its `includes`
   and evaluate `conditionalIncludes` against the runtime context.
2. Otherwise, return the raw context body.

The result is a list of context body strings ready to be appended to the
agent's system prompt.
"""
from __future__ import annotations

import logging
from typing import Any

from agentflow.config.loader import ConfigLoader
from agentflow.config.schemas import ContextProfile
from agentflow.router.rules import RuleEvaluator

logger = logging.getLogger("agentflow.config.resolver")


class ContextResolver:
    """Resolves context_files references, expanding profiles conditionally."""

    def __init__(self, loader: ConfigLoader):
        self._loader = loader
        self._evaluator = RuleEvaluator()

    def resolve(
        self,
        context_files: list[str],
        runtime_context: dict[str, Any] | None = None,
        domain_context_files: list[str] | None = None,
    ) -> list[str]:
        """
        Resolve a list of context file references to their body strings.

        Args:
            context_files: List of context file keys from agent config
                (e.g. ["shared/content-profile.context.md", "shared/persona-keith.context.md"])
            runtime_context: Runtime context dict for evaluating conditional includes
                (e.g. {"message": "Write a blog post about AI agents"})
            domain_context_files: Optional list of domain-level context files to resolve
                first.  These are prepended before the agent's own context_files so that
                domain-wide context is always included.  Duplicates are automatically
                de-duplicated against the agent's list.

        Returns:
            List of context body strings, in order, with profiles expanded.
            Duplicates are removed (preserving first occurrence).
        """
        ctx = runtime_context or {}
        seen: set[str] = set()
        result: list[str] = []

        # Domain-level context first (if provided)
        if domain_context_files:
            for ref in domain_context_files:
                self._resolve_ref(ref, ctx, seen, result)

        # Agent-level context
        for ref in context_files:
            self._resolve_ref(ref, ctx, seen, result)

        return result

    def _resolve_ref(
        self,
        ref: str,
        ctx: dict[str, Any],
        seen: set[str],
        result: list[str],
    ) -> None:
        """Resolve a single context file reference."""
        if ref in seen:
            return
        seen.add(ref)

        profile = self._loader.get_profile(ref)
        if profile is not None:
            self._expand_profile(profile, ref, ctx, seen, result)
        else:
            body = self._loader.get_context_body(ref)
            if body:
                result.append(body)
            else:
                logger.warning("Context file not found: %s", ref)

    def _expand_profile(
        self,
        profile: ContextProfile,
        profile_key: str,
        ctx: dict[str, Any],
        seen: set[str],
        result: list[str],
    ) -> None:
        """Expand a context profile into its constituent context files."""
        # Include the profile's own body text if it has any
        body = self._loader.get_context_body(profile_key)
        if body and body.strip():
            result.append(body)

        # Always-included files
        for inc in profile.includes:
            self._resolve_ref(inc, ctx, seen, result)

        # Conditional includes — evaluate each condition against runtime context
        for ci in profile.conditional_includes:
            if self._evaluator.eval_expr(ci.condition, ctx):
                for inc in ci.include_list():
                    self._resolve_ref(inc, ctx, seen, result)

    def has_profiles(self, context_files: list[str]) -> bool:
        """Check if any of the context_files references are profiles.

        Useful for determining whether an executor can be cached
        (profiles with conditionals depend on per-request context).
        """
        return any(self._loader.is_profile(ref) for ref in context_files)

"""
Async DAG executor for multi-step orchestration plans.

Executes a Plan by resolving inter-step dependencies ({{key.result}} references)
and running independent steps concurrently via asyncio.gather().
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Awaitable, Callable

from agentflow.orchestration.types import Plan, PlanStep

logger = logging.getLogger("agentflow.orchestration")

# Callable signature: runner(workflow_name, message) -> result_text
WorkflowRunner = Callable[[str, str], Awaitable[str]]


class DAGExecutor:
    """Executes a Plan using async topological round-batching.

    Independent steps — those whose message templates have no unresolved
    ``{{key.result}}`` references — run concurrently via asyncio.gather().
    Steps that depend on earlier output wait only for their specific prerequisites.

    If a dependency cycle is detected (no steps are ready but some remain), the
    executor falls back to sequential execution to avoid a deadlock.

    Example:
        plan = Plan(steps=[
            PlanStep(id="s1", workflow="research", message="AI agents", output_key="research"),
            PlanStep(id="s2", workflow="write", message="Write based on {{research.result}}", output_key="article"),
        ])
        executor = DAGExecutor()
        result = await executor.execute(plan, runner=my_runner)
    """

    _DEP_PATTERN = re.compile(r"\{\{(\w+)\.result\}\}")

    async def execute(
        self,
        plan: Plan,
        runner: WorkflowRunner,
        variables: dict | None = None,
    ) -> str:
        """Execute the plan and return a combined result string.

        Args:
            plan:      The orchestration plan with steps to execute.
            runner:    Async callable that invokes a named workflow with a message.
            variables: Optional extra variables (currently reserved for future use).

        Returns:
            Newline-separated results from all successful steps. Failed steps are
            omitted from the combined output but logged as errors.
        """
        outputs: dict[str, str] = {}
        ordered: list[tuple[int, str]] = []  # (original_index, result_text)

        async def _run(step: PlanStep, idx: int) -> tuple[int, str]:
            """Execute one step, substituting resolved outputs into its message."""
            msg = step["message"]
            for key, val in outputs.items():
                msg = msg.replace(f"{{{{{key}.result}}}}", val[:3000])
            try:
                result = await runner(step["workflow"], msg)
                logger.info(
                    "Step %s (%s) completed (%d chars)",
                    step["id"], step["workflow"], len(result),
                )
                return idx, result
            except Exception as exc:
                logger.error("Step %s (%s) failed: %s", step["id"], step["workflow"], exc)
                return idx, f"[Step {step['id']} failed: {exc}]"

        remaining = list(enumerate(plan["steps"]))
        completed: set[str] = set()

        while remaining:
            ready: list[tuple[int, PlanStep]] = []
            waiting: list[tuple[int, PlanStep]] = []

            for idx, step in remaining:
                deps = self._DEP_PATTERN.findall(step["message"])
                if all(d in completed for d in deps):
                    ready.append((idx, step))
                else:
                    waiting.append((idx, step))

            if not ready:
                # Circular or unresolvable dependencies — run remaining sequentially
                logger.warning(
                    "DAGExecutor: %d step(s) have unresolvable dependencies, "
                    "falling back to sequential execution",
                    len(waiting),
                )
                ready, waiting = waiting, []

            # Run all ready steps concurrently
            results = await asyncio.gather(*[_run(step, idx) for idx, step in ready])

            for (_, step), (idx, result) in zip(ready, results):
                outputs[step["output_key"]] = result
                completed.add(step["output_key"])
                ordered.append((idx, result))

            remaining = waiting

        # Re-sort by original step order and filter out failed steps
        ordered.sort(key=lambda x: x[0])
        good = [r for _, r in ordered if not r.startswith("[Step ")]
        return "\n\n---\n\n".join(good) if good else "No results produced."

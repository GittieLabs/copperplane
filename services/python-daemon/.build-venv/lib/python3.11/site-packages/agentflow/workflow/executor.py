"""
Workflow executor.

Walks a WorkflowDAG, executing nodes in topological order. Supports
parallel execution of independent nodes via asyncio.gather, code handler
nodes (registered Python functions), and foreach iteration over list
artifacts.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Awaitable

from agentflow.config.schemas import WorkflowConfig
from agentflow.events import (
    EventBus,
    WORKFLOW_STARTED,
    WORKFLOW_COMPLETED,
    NODE_STARTED,
    NODE_COMPLETED,
    FOREACH_ITERATION,
    HANDLER_RESULT,
    ERROR,
)
from agentflow.types import NodeOutput
from agentflow.workflow.dag import WorkflowDAG
from agentflow.workflow.node import NodeRunner

logger = logging.getLogger("agentflow.workflow")


class WorkflowNodeError(RuntimeError):
    """Raised when a node configured with ``on_error: abort`` fails.

    By default a failing node degrades gracefully — its NodeOutput carries
    ``metadata={"error": True}`` and the rest of the DAG keeps running, so a
    handler that doesn't check for it can silently treat a failure as a
    normal result. ``on_error: abort`` opts a specific node out of that: its
    exception propagates out of ``WorkflowExecutor.run()`` instead, wrapped
    here so the failing node id survives. The original exception is
    available as ``__cause__``.
    """

    def __init__(self, node_id: str, original: BaseException) -> None:
        super().__init__(f"Node '{node_id}' failed (on_error: abort): {original}")
        self.node_id = node_id
        self.original = original

# Type for a factory that creates NodeRunner for a given node_id
NodeRunnerFactory = Callable[[str], Awaitable[NodeRunner] | NodeRunner]

# Type for a code-node handler function
HandlerFn = Callable[
    [str, dict[str, NodeOutput]],
    Awaitable[NodeOutput],
]


class WorkflowExecutor:
    """
    Executes a workflow DAG by walking nodes in dependency order.

    Parallel nodes (those with no dependency between them) are executed
    concurrently using asyncio.gather. Sequential nodes run one at a time.

    Code handler nodes run a registered Python function instead of an LLM.
    Foreach nodes iterate over a list artifact, running the node body once
    per item and collecting results into ``artifacts["results"]``.
    """

    def __init__(
        self,
        config: WorkflowConfig,
        runner_factory: NodeRunnerFactory,
        event_bus: EventBus | None = None,
        handlers: dict[str, HandlerFn] | None = None,
    ) -> None:
        self._dag = WorkflowDAG(config)
        self._factory = runner_factory
        self._events = event_bus
        self._handlers = handlers or {}

    @property
    def dag(self) -> WorkflowDAG:
        return self._dag

    async def run(
        self,
        initial_message: str = "",
        session_id: str | None = None,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, NodeOutput]:
        """
        Execute the full workflow.

        Args:
            initial_message: Message to pass to entry nodes
            session_id: Session ID for scratchpad/artifact storage
            variables: Template variables for prompt rendering

        Returns:
            Dict of node_id -> NodeOutput for all executed nodes
        """
        if self._events:
            await self._events.emit(WORKFLOW_STARTED, {"workflow": self._dag.name})

        # Validate DAG
        errors = self._dag.validate()
        if errors:
            raise ValueError(f"Invalid workflow: {'; '.join(errors)}")

        outputs: dict[str, NodeOutput] = {}
        completed: set[str] = set()

        # Seed entry nodes with the initial message
        entry_nodes = set(self._dag.entry_nodes())

        # Nodes with mode: async that are running in the background, dispatched
        # without the wave loop waiting on them. Drained (results merged into
        # outputs/completed) either when the loop runs out of graph-ready work
        # or once the whole DAG is otherwise done — run() never returns with a
        # background task still in flight.
        background: dict[str, asyncio.Task] = {}

        # Process nodes in waves until all are complete
        while True:
            # Exclude nodes already dispatched into `background` — they
            # haven't reached `completed` yet (that only happens once
            # harvested), but they're not idle either. Without this filter
            # ready_nodes() would keep re-offering them every wave, since
            # nothing else marks them as no-longer-ready.
            ready = [nid for nid in self._dag.ready_nodes(completed) if nid not in background]

            if not ready:
                if not background:
                    break
                # No node is graph-ready, but async-mode nodes are still
                # running — wait for at least one to finish rather than
                # ending the workflow while work is outstanding.
                done, _ = await asyncio.wait(background.values(), return_when=asyncio.FIRST_COMPLETED)
                await self._harvest_background(background, done, outputs, completed)
                continue

            # Group ready nodes by execution mode
            parallel_batch: list[str] = []
            sequential_batch: list[str] = []
            async_batch: list[str] = []

            for nid in ready:
                node = self._dag.nodes[nid]
                if node.mode == "parallel":
                    parallel_batch.append(nid)
                elif node.mode == "async":
                    async_batch.append(nid)
                else:
                    sequential_batch.append(nid)

            # Dispatch async (fire-and-forget) nodes without waiting on them —
            # siblings in this wave and later waves proceed immediately.
            for nid in async_batch:
                background[nid] = asyncio.create_task(
                    self._run_node(nid, outputs, entry_nodes, initial_message, session_id, variables)
                )

            # Execute parallel nodes concurrently
            if parallel_batch:
                tasks = []
                for nid in parallel_batch:
                    tasks.append(self._run_node(
                        nid, outputs, entry_nodes, initial_message, session_id, variables
                    ))
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for nid, result in zip(parallel_batch, results):
                    if isinstance(result, Exception):
                        logger.error("Node %s failed: %s", nid, result)
                        if self._events:
                            await self._events.emit(ERROR, {"node": nid, "error": str(result)})
                        if self._dag.nodes[nid].on_error == "abort":
                            for task in background.values():
                                task.cancel()
                            raise WorkflowNodeError(nid, result) from result
                        outputs[nid] = NodeOutput(
                            node_id=nid,
                            agent_id="",
                            text=f"Error: {result}",
                            metadata={"error": True},
                        )
                    else:
                        outputs[nid] = result
                    completed.add(nid)

            # Execute sequential nodes one at a time
            for nid in sequential_batch:
                try:
                    result = await self._run_node(
                        nid, outputs, entry_nodes, initial_message, session_id, variables
                    )
                    outputs[nid] = result
                except Exception as exc:
                    logger.error("Node %s failed: %s", nid, exc)
                    if self._events:
                        await self._events.emit(ERROR, {"node": nid, "error": str(exc)})
                    if self._dag.nodes[nid].on_error == "abort":
                        for task in background.values():
                            task.cancel()
                        raise WorkflowNodeError(nid, exc) from exc
                    outputs[nid] = NodeOutput(
                        node_id=nid,
                        agent_id="",
                        text=f"Error: {exc}",
                        metadata={"error": True},
                    )
                completed.add(nid)

            # Opportunistically harvest any background tasks that finished
            # while we were awaiting the parallel/sequential batches above —
            # keeps completed/outputs current so their dependents can become
            # ready on the very next wave instead of an extra idle round-trip.
            finished = [t for t in background.values() if t.done()]
            if finished:
                await self._harvest_background(background, finished, outputs, completed)

        if self._events:
            await self._events.emit(WORKFLOW_COMPLETED, {
                "workflow": self._dag.name,
                "nodes_completed": len(completed),
            })

        return outputs

    async def _harvest_background(
        self,
        background: dict[str, asyncio.Task],
        done_tasks,
        outputs: dict[str, NodeOutput],
        completed: set[str],
    ) -> None:
        """Collect finished async-mode node tasks into outputs/completed.

        Mirrors the error handling of the parallel/sequential paths so an
        async node's failure surfaces the same way theirs does, instead of
        being lost with the task.
        """
        for task in done_tasks:
            nid = next(n for n, t in background.items() if t is task)
            del background[nid]
            try:
                result = await task
            except Exception as exc:
                logger.error("Node %s failed: %s", nid, exc)
                if self._events:
                    await self._events.emit(ERROR, {"node": nid, "error": str(exc)})
                if self._dag.nodes[nid].on_error == "abort":
                    # Cancel other still-running background tasks before
                    # propagating — otherwise they'd be left dangling once
                    # this exception unwinds run().
                    for other in background.values():
                        other.cancel()
                    raise WorkflowNodeError(nid, exc) from exc
                result = NodeOutput(
                    node_id=nid,
                    agent_id="",
                    text=f"Error: {exc}",
                    metadata={"error": True},
                )
            outputs[nid] = result
            completed.add(nid)

    async def _run_node(
        self,
        node_id: str,
        prior_outputs: dict[str, NodeOutput],
        entry_nodes: set[str],
        initial_message: str,
        session_id: str | None,
        variables: dict[str, Any] | None,
    ) -> NodeOutput:
        """Execute a single node — dispatches to handler, foreach, or LLM path."""
        if self._events:
            await self._events.emit(NODE_STARTED, {"node": node_id})

        node = self._dag.nodes[node_id]

        # For entry nodes with no prior outputs, inject the initial message
        effective_outputs = dict(prior_outputs)
        if node_id in entry_nodes and not prior_outputs:
            effective_outputs["__initial__"] = NodeOutput(
                node_id="__initial__",
                agent_id="",
                text=initial_message,
            )

        # Dispatch based on node type
        if node.foreach:
            result = await self._run_foreach_node(
                node_id, node, effective_outputs, session_id, variables
            )
        elif node.handler:
            result = await self._run_handler_node(
                node_id, node, effective_outputs
            )
        else:
            result = await self._run_agent_node(
                node_id, effective_outputs, session_id, variables
            )

        if self._events:
            await self._events.emit(NODE_COMPLETED, {
                "node": node_id,
                "agent": result.agent_id,
            })

        return result

    # ------------------------------------------------------------------
    # Agent node (LLM execution — original path)
    # ------------------------------------------------------------------

    async def _run_agent_node(
        self,
        node_id: str,
        prior_outputs: dict[str, NodeOutput],
        session_id: str | None,
        variables: dict[str, Any] | None,
    ) -> NodeOutput:
        """Run a node through its AgentExecutor (LLM + tools)."""
        runner = self._factory(node_id)
        if asyncio.iscoroutine(runner):
            runner = await runner

        return await runner.run(
            prior_outputs=prior_outputs,
            session_id=session_id,
            variables=variables,
        )

    # ------------------------------------------------------------------
    # Handler node (registered Python function)
    # ------------------------------------------------------------------

    async def _run_handler_node(
        self,
        node_id: str,
        node,
        prior_outputs: dict[str, NodeOutput],
    ) -> NodeOutput:
        """Run a code handler node."""
        handler = self._handlers.get(node.handler)
        if not handler:
            raise ValueError(
                f"Node '{node_id}': handler '{node.handler}' not registered. "
                f"Available: {list(self._handlers.keys())}"
            )

        message = NodeRunner.resolve_message(node.inputs, prior_outputs)
        result = await handler(message, prior_outputs)

        # Ensure node_id is set correctly
        if result.node_id != node_id:
            result = NodeOutput(
                node_id=node_id,
                agent_id=result.agent_id or node.handler,
                text=result.text,
                artifacts=result.artifacts,
                metadata=result.metadata,
            )

        # Emit handler result so observers can react to handler outputs
        # (e.g., asset collectors capturing document URLs from artifacts).
        if self._events:
            await self._events.emit(HANDLER_RESULT, {
                "node": node_id,
                "handler": node.handler,
                "text": result.text,
                "artifacts": result.artifacts,
                "metadata": result.metadata,
            })

        return result

    # ------------------------------------------------------------------
    # Foreach node (iterates over a list artifact)
    # ------------------------------------------------------------------

    async def _run_foreach_node(
        self,
        node_id: str,
        node,
        prior_outputs: dict[str, NodeOutput],
        session_id: str | None,
        variables: dict[str, Any] | None,
    ) -> NodeOutput:
        """Run a node once per item in the referenced list artifact."""
        # Resolve the foreach reference to a Python list
        items = NodeRunner.resolve_ref_raw(node.foreach, prior_outputs)
        if items is None:
            logger.warning(
                "Node %s: foreach ref '%s' resolved to None — skipping",
                node_id, node.foreach,
            )
            return NodeOutput(
                node_id=node_id,
                agent_id=node.agent or node.handler or "",
                text="",
                artifacts={"results": []},
                metadata={"foreach": True, "iterations": 0},
            )

        if not isinstance(items, list):
            raise TypeError(
                f"Node '{node_id}': foreach ref '{node.foreach}' must resolve "
                f"to a list, got {type(items).__name__}"
            )

        if not items:
            return NodeOutput(
                node_id=node_id,
                agent_id=node.agent or node.handler or "",
                text="",
                artifacts={"results": []},
                metadata={"foreach": True, "iterations": 0},
            )

        total = len(items)
        iteration_results: list[str] = []

        for i, item in enumerate(items):
            # Serialize item for text representation
            if isinstance(item, (dict, list)):
                item_str = json.dumps(item, indent=2, ensure_ascii=False)
            else:
                item_str = str(item)

            # Inject __loop__ synthetic output so inputs/message can reference it
            loop_output = NodeOutput(
                node_id="__loop__",
                agent_id="",
                text=item_str,
                artifacts={
                    "item": item,
                    "index": i,
                    "total": total,
                    "prior_results": list(iteration_results),
                },
            )
            effective = {**prior_outputs, "__loop__": loop_output}

            # Also inject accumulated results as __loop_accumulator__
            accumulator_text = "\n\n---\n\n".join(iteration_results) if iteration_results else ""
            effective["__loop_accumulator__"] = NodeOutput(
                node_id="__loop_accumulator__",
                agent_id="",
                text=accumulator_text,
            )

            # Build per-iteration variables
            iter_vars = dict(variables) if variables else {}
            iter_vars.update({
                "loop_item": item_str,
                "loop_index": str(i),
                "loop_total": str(total),
                "loop_prior_results": accumulator_text,
            })

            logger.info(
                "Foreach %s: iteration %d/%d",
                node_id, i + 1, total,
            )

            try:
                if node.handler:
                    result = await self._run_handler_node(node_id, node, effective)
                else:
                    runner = self._factory(node_id)
                    if asyncio.iscoroutine(runner):
                        runner = await runner
                    result = await runner.run(
                        prior_outputs=effective,
                        session_id=session_id,
                        variables=iter_vars,
                    )
                iteration_results.append(result.text)
            except Exception as exc:
                logger.error(
                    "Foreach %s: iteration %d failed: %s", node_id, i, exc
                )
                if node.on_error == "abort":
                    raise WorkflowNodeError(node_id, exc) from exc
                return NodeOutput(
                    node_id=node_id,
                    agent_id=node.agent or node.handler or "",
                    text=f"Error at iteration {i}: {exc}",
                    artifacts={
                        "results": iteration_results,
                        "error_index": i,
                    },
                    metadata={
                        "foreach": True,
                        "error": True,
                        "failed_index": i,
                        "completed": i,
                        "total": total,
                    },
                )

            if self._events:
                await self._events.emit(FOREACH_ITERATION, {
                    "node": node_id,
                    "index": i,
                    "total": total,
                })

        # Merge all iteration results
        return NodeOutput(
            node_id=node_id,
            agent_id=node.agent or node.handler or "",
            text="\n\n---\n\n".join(iteration_results),
            artifacts={"results": iteration_results},
            metadata={
                "foreach": True,
                "iterations": total,
            },
        )

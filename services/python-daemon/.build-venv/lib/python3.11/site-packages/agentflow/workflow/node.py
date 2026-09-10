"""
Workflow node runner.

Wraps an AgentExecutor as a DAG node, resolving input mappings from
prior node outputs and writing results to session scratchpads.
"""
from __future__ import annotations

import logging
from typing import Any

from agentflow.agent.runtime import AgentExecutor
from agentflow.config.schemas import WorkflowNode
from agentflow.session.scratchpad import Scratchpad
from agentflow.types import NodeOutput

logger = logging.getLogger("agentflow.workflow.node")


class NodeRunner:
    """
    Executes a single node within a workflow.

    Resolves input mappings from prior node outputs, runs the agent, and
    writes the result to the scratchpad.

    **How inputs reach the agent**

    The ``inputs`` field in a node's YAML config controls what the agent
    receives as its user-facing message.  There are three distinct patterns:

    1. **Single message** (``message`` key) — the most common case.  One
       upstream output is routed directly as the message::

           inputs:
             message: "research.text"

    2. **Named inputs** (any keys except ``message``) — for nodes that need
       output from multiple upstream nodes.  Each key becomes a labeled
       section delivered to the agent in YAML-definition order::

           inputs:
             outline: "outline.text"
             sections: "write.text"

       The agent receives::

           [outline]
           <outline content>

           [sections]
           <sections content>

       Write the agent's system prompt to reference these labeled sections
       by name.

    3. **No inputs defined** — the node is treated as an entry node and
       receives the workflow's initial message.  Use this only for the
       first node in a pipeline.
    """

    def __init__(
        self,
        node: WorkflowNode,
        executor: AgentExecutor,
        scratchpad: Scratchpad | None = None,
    ) -> None:
        self._node = node
        self._executor = executor
        self._scratchpad = scratchpad

    @property
    def node_id(self) -> str:
        return self._node.id

    @property
    def mode(self) -> str:
        return self._node.mode

    async def run(
        self,
        prior_outputs: dict[str, NodeOutput],
        session_id: str | None = None,
        variables: dict[str, Any] | None = None,
    ) -> NodeOutput:
        """
        Execute this node.

        Args:
            prior_outputs: Outputs from upstream nodes, keyed by node_id
            session_id: Current session ID
            variables: Template variables for prompt rendering

        Returns:
            NodeOutput from the agent execution
        """
        # Resolve input message from prior node outputs
        message = self._resolve_message(prior_outputs)

        # Write incoming context to scratchpad
        if self._scratchpad and prior_outputs:
            context_parts = []
            for nid, output in prior_outputs.items():
                if nid in self._input_node_ids():
                    context_parts.append(f"## From {nid}\n{output.text}")
            if context_parts:
                await self._scratchpad.write_scratch("\n\n".join(context_parts))

        # Run the agent
        result = await self._executor.run(
            message=message,
            session_id=session_id,
            node_id=self._node.id,
            variables=variables,
        )

        # Write output summary to scratchpad
        if self._scratchpad:
            await self._scratchpad.write_summary(result.text)

        return result

    def _resolve_message(self, prior_outputs: dict[str, NodeOutput]) -> str:
        return NodeRunner.resolve_message(self._node.inputs, prior_outputs)

    def _resolve_ref(self, ref: str, prior_outputs: dict[str, NodeOutput]) -> str:
        return NodeRunner.resolve_ref(ref, prior_outputs)

    # ------------------------------------------------------------------
    # Static helpers — used by the executor for handler / foreach nodes
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_message(inputs: dict[str, str], prior_outputs: dict[str, NodeOutput]) -> str:
        """
        Build the message for a node from input mappings or prior outputs.

        Resolution rules (applied in order):

        **Rule 1 — explicit ``message`` key:**
        Route a single upstream output directly as the message.

            inputs:
              message: "research.text"

        **Rule 2 — named inputs (no ``message`` key):**
        Resolve each key in YAML-definition order.  Deliver as labeled
        sections so the agent's system prompt can reference each input by
        name.  The format is::

            [key1]
            <resolved value>

            [key2]
            <resolved value>

        **Rule 3 — no inputs defined:**
        Entry-node path.  The workflow's initial message is passed through
        via the ``__initial__`` sentinel injected by the executor.  For
        non-entry nodes with no ``inputs`` key, the message will be empty —
        always use Rule 1 or Rule 2 to wire data between pipeline stages.
        """
        # Rule 1: single explicit message
        if "message" in inputs:
            return NodeRunner.resolve_ref(inputs["message"], prior_outputs)

        # Rule 2: named inputs — labeled sections in definition order
        if inputs:
            parts = []
            for key, ref in inputs.items():
                value = NodeRunner.resolve_ref(ref, prior_outputs)
                parts.append(f"[{key}]\n{value}")
            return "\n\n".join(parts)

        # Rule 3: no inputs — entry node receives initial message
        initial = prior_outputs.get("__initial__")
        return initial.text if initial else ""

    @staticmethod
    def resolve_ref(ref: str, prior_outputs: dict[str, NodeOutput]) -> str:
        """
        Resolve a dotted reference to a prior node's output.

        Supported forms:
        - ``"node_id.text"``             — the node's full text response
        - ``"node_id.artifacts.key"``    — a named artifact from the node
        """
        parts = ref.split(".")
        if len(parts) < 2:
            return ref

        node_id = parts[0]
        output = prior_outputs.get(node_id)
        if not output:
            return ""

        if parts[1] == "text":
            return output.text
        elif parts[1] == "artifacts" and len(parts) >= 3:
            return str(output.artifacts.get(parts[2], ""))

        return output.text

    @staticmethod
    def resolve_ref_raw(ref: str, prior_outputs: dict[str, NodeOutput]) -> Any:
        """
        Resolve a dotted reference and return the raw Python object.

        Unlike :meth:`resolve_ref`, this does **not** stringify the result.
        Used by foreach expansion to obtain the actual list from an
        ``artifacts`` reference.
        """
        parts = ref.split(".")
        if len(parts) < 2:
            return ref

        node_id = parts[0]
        output = prior_outputs.get(node_id)
        if not output:
            return None

        if parts[1] == "text":
            return output.text
        elif parts[1] == "artifacts" and len(parts) >= 3:
            return output.artifacts.get(parts[2])

        return output.text

    def _input_node_ids(self) -> list[str]:
        """
        Return the node IDs referenced by this node's inputs.

        Used to filter prior_outputs for scratchpad context writes.
        """
        node_ids = []
        seen: set[str] = set()
        for ref in self._node.inputs.values():
            nid = ref.split(".")[0]
            if nid not in seen:
                seen.add(nid)
                node_ids.append(nid)
        return node_ids

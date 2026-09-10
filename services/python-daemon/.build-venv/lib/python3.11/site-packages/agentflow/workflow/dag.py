"""
Workflow DAG parser.

Converts a WorkflowConfig (from *.workflow.md) into a directed acyclic graph.
Provides topological sorting and identifies which nodes are ready to execute
given a set of completed nodes.
"""
from __future__ import annotations

from collections import defaultdict

from agentflow.config.schemas import WorkflowConfig, WorkflowNode


class WorkflowDAG:
    """
    Directed acyclic graph representation of a workflow.

    Provides traversal helpers for the WorkflowExecutor:
    - topological_order(): full execution order
    - ready_nodes(completed): nodes whose dependencies are all met
    - predecessors(node_id): which nodes feed into a given node
    """

    def __init__(self, config: WorkflowConfig) -> None:
        self._config = config
        self._nodes: dict[str, WorkflowNode] = {n.id: n for n in config.nodes}
        self._edges: dict[str, list[str]] = defaultdict(list)  # parent -> children
        self._reverse: dict[str, list[str]] = defaultdict(list)  # child -> parents

        for node in config.nodes:
            for child_id in node.next_nodes():
                self._edges[node.id].append(child_id)
                self._reverse[child_id].append(node.id)

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def nodes(self) -> dict[str, WorkflowNode]:
        return self._nodes

    def entry_nodes(self) -> list[str]:
        """Nodes with no predecessors — the starting points."""
        return [nid for nid in self._nodes if nid not in self._reverse]

    def terminal_nodes(self) -> list[str]:
        """Nodes with no successors — the endpoints."""
        return [nid for nid in self._nodes if nid not in self._edges]

    def successors(self, node_id: str) -> list[str]:
        """Direct children of a node."""
        return self._edges.get(node_id, [])

    def predecessors(self, node_id: str) -> list[str]:
        """Direct parents of a node."""
        return self._reverse.get(node_id, [])

    def topological_order(self) -> list[str]:
        """
        Return nodes in topological order (Kahn's algorithm).

        Raises ValueError if the graph has a cycle.
        """
        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        for nid in self._nodes:
            for child in self._edges.get(nid, []):
                if child in in_degree:
                    in_degree[child] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: list[str] = []

        while queue:
            # Sort for deterministic order among nodes with equal in-degree
            queue.sort()
            node = queue.pop(0)
            order.append(node)

            for child in self._edges.get(node, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(self._nodes):
            raise ValueError(f"Workflow '{self.name}' contains a cycle")

        return order

    def ready_nodes(self, completed: set[str]) -> list[str]:
        """
        Return nodes whose predecessors are all in the completed set
        and that haven't been completed themselves.
        """
        ready = []
        for nid in self._nodes:
            if nid in completed:
                continue
            parents = self._reverse.get(nid, [])
            if all(p in completed for p in parents):
                ready.append(nid)
        return sorted(ready)

    def validate(self) -> list[str]:
        """
        Validate the DAG structure. Returns a list of error messages (empty if valid).
        """
        errors = []

        # Check for references to non-existent nodes (must come before topo sort)
        for node in self._config.nodes:
            for child_id in node.next_nodes():
                if child_id not in self._nodes:
                    errors.append(f"Node '{node.id}' references unknown node '{child_id}'")

        # Check for cycles (only if references are valid)
        if not errors:
            try:
                self.topological_order()
            except ValueError as e:
                errors.append(str(e))

        # Check for no entry nodes
        if not self.entry_nodes():
            errors.append("Workflow has no entry nodes (all nodes have predecessors)")

        # Validate foreach references point to existing node IDs
        for node in self._config.nodes:
            if node.foreach:
                ref_node = node.foreach.split(".")[0]
                if ref_node not in self._nodes:
                    errors.append(
                        f"Node '{node.id}' foreach ref '{node.foreach}' "
                        f"references unknown node '{ref_node}'"
                    )

        return errors

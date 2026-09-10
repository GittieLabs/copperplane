"""
Orchestration type definitions.

PlanStep and Plan describe the output of a planner agent — a set of
workflow invocations (possibly with inter-step dependencies) that together
satisfy a complex user request.
"""
from __future__ import annotations

from typing import TypedDict


class PlanStep(TypedDict):
    """A single step in an orchestration plan.

    Fields:
        id:         Unique identifier for this step (e.g. "step_1").
        workflow:   Name of the workflow to invoke (must exist in the config loader).
        message:    Input message for the workflow. May contain ``{{output_key.result}}``
                    references to the output of prior steps.
        output_key: Key under which this step's result is stored for use by later steps.
    """

    id: str
    workflow: str
    message: str
    output_key: str


class Plan(TypedDict):
    """A complete orchestration plan produced by a planner agent.

    Fields:
        steps: Ordered list of PlanStep items. DAGExecutor resolves
               inter-step dependencies and executes independent steps concurrently.
    """

    steps: list[PlanStep]

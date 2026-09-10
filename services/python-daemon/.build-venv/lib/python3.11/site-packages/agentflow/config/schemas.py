"""
Pydantic models for validating YAML front-matter in config files.

Each file type (*.prompt.md, *.workflow.md, router.prompt.md, *.memory.md)
has a corresponding schema that validates and types the front-matter.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


# ── Agent config (*.prompt.md) ────────────────────────────────────────────────


class ToolDefinition(BaseModel):
    """Schema for a tool definition embedded in agent config."""

    name: str
    description: str = ""
    input_schema: dict = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Front-matter schema for *.prompt.md files."""

    name: str
    description: str = ""
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_tool_rounds: int = 6
    tools: list[str] = Field(default_factory=list)
    tool_definitions: list[ToolDefinition] = Field(default_factory=list)
    context_files: list[str] = Field(default_factory=list)
    # Vendor arguments forwarded verbatim to the provider's SDK call, for
    # anything AgentFlow does not name itself -- reasoning effort, thinking
    # budgets, and whatever a vendor ships next. Declared per agent because
    # that is the level at which a model is chosen, so the parameter and the
    # model it applies to stay together. See providers/_params.py.
    params: dict[str, Any] = Field(default_factory=dict)


# ── Router config (router.prompt.md) ──────────────────────────────────────────


class RoutingRule(BaseModel):
    """A single if/routeTo rule in the router."""

    condition: str = Field(alias="if")
    route_to: str = Field(alias="routeTo")

    model_config = {"populate_by_name": True}


class RouterConfig(BaseModel):
    """Front-matter schema for router.prompt.md."""

    name: str = "router"
    routing_rules: list[RoutingRule] = Field(default_factory=list, alias="routingRules")
    fallback: str = "default"
    llm_fallback: bool = Field(default=True, alias="llmFallback")

    model_config = {"populate_by_name": True}


# ── Workflow config (*.workflow.md) ───────────────────────────────────────────


class WorkflowNode(BaseModel):
    """A single node in a workflow DAG.

    Each node must have exactly one of ``agent`` (LLM execution) or
    ``handler`` (registered Python function).  Optionally, ``foreach``
    references a list artifact from an upstream node — the executor runs
    this node once per item in that list, collecting results into
    ``artifacts["results"]``.
    """

    id: str
    agent: str | None = None
    handler: str | None = None
    foreach: str | None = None
    next: list[str] | str | None = None
    mode: str = "sync"  # "sync" | "parallel" | "async"
    on_error: str = Field(default="continue", alias="onError")  # "continue" | "abort"
    inputs: dict[str, str] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _check_agent_or_handler(self) -> "WorkflowNode":
        if self.agent and self.handler:
            raise ValueError(
                f"Node '{self.id}': set either 'agent' or 'handler', not both"
            )
        if not self.agent and not self.handler:
            raise ValueError(
                f"Node '{self.id}': must set 'agent' or 'handler'"
            )
        if self.mode not in ("sync", "parallel", "async"):
            raise ValueError(
                f"Node '{self.id}': invalid mode {self.mode!r} — must be "
                f"'sync', 'parallel', or 'async'"
            )
        if self.on_error not in ("continue", "abort"):
            raise ValueError(
                f"Node '{self.id}': invalid on_error {self.on_error!r} — must be "
                f"'continue' or 'abort'"
            )
        return self

    def next_nodes(self) -> list[str]:
        """Normalize next to a list."""
        if self.next is None:
            return []
        if isinstance(self.next, str):
            return [self.next]
        return self.next


class WorkflowConfig(BaseModel):
    """Front-matter schema for *.workflow.md files."""

    name: str
    description: str = ""
    trigger: str = "manual"  # "manual" | "api" | "cron" | "webhook"
    callable: bool = False
    nodes: list[WorkflowNode] = Field(default_factory=list)

    def entry_node(self) -> WorkflowNode | None:
        """Return the first node (entry point) of the workflow."""
        return self.nodes[0] if self.nodes else None


# ── Context profile (*.context.md with type: profile) ────────────────────────


class ConditionalInclude(BaseModel):
    """A single conditional include: loads context files when condition matches."""

    condition: str = Field(alias="if")
    include: str | list[str]

    model_config = {"populate_by_name": True}

    def include_list(self) -> list[str]:
        """Normalize include to a list."""
        if isinstance(self.include, str):
            return [self.include]
        return self.include


class ContextProfile(BaseModel):
    """Front-matter schema for *.context.md files with type: profile.

    A context profile is a manifest that declares which other context files
    to load (always or conditionally). Conditions are evaluated at runtime
    against a context dict (e.g. containing the user message).

    Example YAML front-matter:
        type: profile
        includes:
          - shared/persona-keith.context.md
        conditionalIncludes:
          - if: "'blog' in message or 'article' in message"
            include: shared/content-guidelines.context.md
          - if: "'lead' in message"
            include:
              - shared/lead-gen-config.context.md
              - shared/email-templates.context.md
    """

    type: str = "profile"
    includes: list[str] = Field(default_factory=list)
    conditional_includes: list[ConditionalInclude] = Field(
        default_factory=list, alias="conditionalIncludes"
    )

    model_config = {"populate_by_name": True}


# ── Domain config (*.domain.md) ───────────────────────────────────────────────


class DomainConfig(BaseModel):
    """Front-matter schema for *.domain.md files.

    A domain groups related agents and workflows under a common routing
    boundary.  The top-level router classifies a message into a domain,
    then the domain's own router (using ``router_model``) picks the
    specific agent or workflow.

    Example YAML front-matter::

        name: content
        description: "Content research, creation, editing, and publishing"
        routerModel: claude-sonnet-4-6
        agents:
          - content_researcher
          - content_formatter
        workflows:
          - content-research
          - content-creation
        contextFiles:
          - shared/content-guidelines.context.md
        fallback: content_researcher
    """

    name: str
    description: str = ""
    router_model: str = Field(default="claude-sonnet-4-6", alias="routerModel")
    router_temperature: float = Field(default=0.0, alias="routerTemperature")
    agents: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    context_files: list[str] = Field(default_factory=list, alias="contextFiles")
    fallback: str = ""

    model_config = {"populate_by_name": True}

    @property
    def available_targets(self) -> list[str]:
        """All agents + workflows this domain can route to."""
        return self.agents + self.workflows


# ── Memory config (*.memory.md) ───────────────────────────────────────────────


class MemoryConfig(BaseModel):
    """Front-matter schema for *.memory.md files."""

    agent: str
    retention: str = "permanent"  # "permanent" | "session" | "ttl:7d"
    max_entries: int = 100

"""
Directory scanner that loads a /context/ tree into typed config objects.

Expected layout:
  context/
    router.prompt.md
    agents/*.prompt.md
    agents/*.context.md
    agents/*.memory.md
    workflows/*.workflow.md
    shared/*.context.md
"""
from __future__ import annotations

import logging
from pathlib import Path

from agentflow.config.parser import parse_prompt_file
from agentflow.config.schemas import (
    AgentConfig,
    ContextProfile,
    DomainConfig,
    MemoryConfig,
    RouterConfig,
    WorkflowConfig,
)

logger = logging.getLogger("agentflow.config")


class ConfigLoader:
    """Loads and caches all config files from a context directory."""

    def __init__(self, context_dir: str | Path):
        self._root = Path(context_dir)
        self._agents: dict[str, tuple[AgentConfig, str]] = {}
        self._workflows: dict[str, tuple[WorkflowConfig, str]] = {}
        self._router: tuple[RouterConfig, str] | None = None
        self._context_files: dict[str, str] = {}  # filename -> context body
        self._profiles: dict[str, ContextProfile] = {}  # filename -> ContextProfile
        self._memory_configs: dict[str, tuple[MemoryConfig, str]] = {}
        self._domains: dict[str, tuple[DomainConfig, str]] = {}

    @property
    def agents(self) -> dict[str, tuple[AgentConfig, str]]:
        return self._agents

    @property
    def workflows(self) -> dict[str, tuple[WorkflowConfig, str]]:
        return self._workflows

    @property
    def router(self) -> tuple[RouterConfig, str] | None:
        return self._router

    @property
    def profiles(self) -> dict[str, ContextProfile]:
        return self._profiles

    @property
    def domains(self) -> dict[str, tuple[DomainConfig, str]]:
        return self._domains

    def get_domain(self, name: str) -> tuple[DomainConfig, str]:
        """Get domain config and prompt body by name."""
        if name not in self._domains:
            raise KeyError(
                f"Domain not found: {name}. Available: {list(self._domains.keys())}"
            )
        return self._domains[name]

    def is_profile(self, filename: str) -> bool:
        """Check if a context file is a profile (has conditional includes)."""
        return filename in self._profiles

    def get_profile(self, filename: str) -> ContextProfile | None:
        """Get a ContextProfile by filename, or None if not a profile."""
        return self._profiles.get(filename)

    def load(self) -> None:
        """Scan the context directory and load all config files."""
        if not self._root.exists():
            raise FileNotFoundError(f"Context directory not found: {self._root}")

        self._load_router()
        self._load_agents()
        self._load_workflows()
        self._load_domains()
        self._load_context_files()
        self._load_shared_context()
        self._load_memory_configs()

        logger.info(
            "Loaded %d agents, %d workflows, %d domains, router=%s",
            len(self._agents),
            len(self._workflows),
            len(self._domains),
            self._router is not None,
        )

    def get_agent(self, name: str) -> tuple[AgentConfig, str]:
        """Get agent config and prompt body by name."""
        if name not in self._agents:
            raise KeyError(f"Agent not found: {name}. Available: {list(self._agents.keys())}")
        return self._agents[name]

    def get_workflow(self, name: str) -> tuple[WorkflowConfig, str]:
        """Get workflow config and description body by name."""
        if name not in self._workflows:
            raise KeyError(
                f"Workflow not found: {name}. Available: {list(self._workflows.keys())}"
            )
        return self._workflows[name]

    def get_context_body(self, filename: str) -> str | None:
        """Get the body of a .context.md file by filename.

        Supports both agent context files (e.g. "company.context.md")
        and shared context files (e.g. "shared/persona-keith.context.md").
        """
        return self._context_files.get(filename)

    def _load_router(self) -> None:
        router_path = self._root / "router.prompt.md"
        if router_path.exists():
            meta, body = parse_prompt_file(router_path)
            self._router = (RouterConfig(**meta), body)

    def _load_agents(self) -> None:
        agents_dir = self._root / "agents"
        if not agents_dir.exists():
            return
        for path in sorted(agents_dir.glob("*.prompt.md")):
            meta, body = parse_prompt_file(path)
            config = AgentConfig(**meta)
            self._agents[config.name] = (config, body)
            logger.debug("Loaded agent: %s from %s", config.name, path.name)

    def _load_workflows(self) -> None:
        workflows_dir = self._root / "workflows"
        if not workflows_dir.exists():
            return
        for path in sorted(workflows_dir.glob("*.workflow.md")):
            meta, body = parse_prompt_file(path)
            config = WorkflowConfig(**meta)
            self._workflows[config.name] = (config, body)
            logger.debug("Loaded workflow: %s from %s", config.name, path.name)

    def _load_domains(self) -> None:
        """Load domain definitions from domains/*.domain.md."""
        domains_dir = self._root / "domains"
        if not domains_dir.exists():
            return
        for path in sorted(domains_dir.glob("*.domain.md")):
            meta, body = parse_prompt_file(path)
            config = DomainConfig(**meta)
            self._domains[config.name] = (config, body)
            logger.debug("Loaded domain: %s from %s", config.name, path.name)

    def _load_context_files(self) -> None:
        agents_dir = self._root / "agents"
        if not agents_dir.exists():
            return
        for path in sorted(agents_dir.glob("*.context.md")):
            meta, body = parse_prompt_file(path)
            key = path.name
            if meta.get("type") == "profile":
                self._profiles[key] = ContextProfile(**meta)
                logger.debug("Loaded context profile: %s", key)
            # Always store the body — profiles have descriptive body text too
            self._context_files[key] = body

    def _load_shared_context(self) -> None:
        """Load context files from shared/ and any other non-agent/workflow directories.

        Scans all subdirectories of the context root (except agents/ and workflows/)
        for *.context.md files. Keys include the directory prefix so agents can
        reference them as e.g. "shared/persona-keith.context.md" or
        "templates/standard.context.md".
        """
        # Directories to skip (handled by other loaders)
        skip_dirs = {"agents", "workflows"}

        for subdir in sorted(self._root.iterdir()):
            if not subdir.is_dir() or subdir.name in skip_dirs or subdir.name.startswith("."):
                continue
            self._load_context_dir(subdir, prefix=subdir.name)

    def _load_context_dir(self, directory: Path, prefix: str) -> None:
        """Load all *.context.md files from a directory with the given key prefix."""
        for path in sorted(directory.glob("*.context.md")):
            meta, body = parse_prompt_file(path)
            key = f"{prefix}/{path.name}"
            if meta.get("type") == "profile":
                self._profiles[key] = ContextProfile(**meta)
                logger.debug("Loaded context profile: %s", key)
            self._context_files[key] = body
            logger.debug("Loaded context: %s from %s/", key, prefix)

    def _load_memory_configs(self) -> None:
        agents_dir = self._root / "agents"
        if not agents_dir.exists():
            return
        for path in sorted(agents_dir.glob("*.memory.md")):
            meta, body = parse_prompt_file(path)
            config = MemoryConfig(**meta)
            self._memory_configs[config.agent] = (config, body)

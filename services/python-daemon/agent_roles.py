"""
SPEC-208 §2.3.3: a thin local sidecar re-reading each `.prompt.md` file's
own YAML frontmatter for the two keys AgentFlow's `AgentConfig` silently
drops. Verified against the installed source (2026-08-25): `AgentConfig`
(`agentflow/config/schemas.py`) is a plain pydantic v2 `BaseModel` with no
`model_config` override, so `extra` defaults to `"ignore"`, and
`ConfigLoader._load_agents` builds it with a bare `AgentConfig(**meta)` --
`model_role`/`requires` are parsed out of the YAML and silently discarded.
`loader.get_agent()` can never return them; this module is what makes
them real, reusing AgentFlow's own `parse_prompt_file` rather than a
second, hand-rolled frontmatter parser.

Because `extra="ignore"` never errors, a *typo'd* `model_role` would be
discarded exactly as silently as a valid unknown key. `load_agent_roles`
validates its own two keys itself: a missing or unrecognized `model_role`,
or an unrecognized `requires` entry, is a load-time `AgentRoleError`, not
a fall-through to a default role (SPEC-208 §2.3.3's own named gotcha).
"""
from pathlib import Path

from agentflow.config.parser import parse_prompt_file

# SPEC-208 §2.3.1: exactly two roles, deliberately -- see the spec's own
# reasoning for why a third is a preset migration, not a redesign.
VALID_MODEL_ROLES = frozenset({"reasoning", "fast"})

# SPEC-208 §2.4: what an agent's prompt body actually needs, checked
# against a provider record's own declared `capabilities` -- CTX-208.3's
# job to enforce; this module only parses and validates the declaration.
VALID_REQUIRES = frozenset({"tool_use", "strict_json"})


class AgentRoleError(Exception):
    """A `.prompt.md` file with a missing/unrecognized `model_role`, or an
    unrecognized `requires` entry -- raised at load time, never silently
    dropped or defaulted."""


def load_agent_roles(agents_dir: str | Path) -> dict[str, dict]:
    """Returns `{agent_name: {"model_role": str, "requires": list[str]}}`
    for every `*.prompt.md` in `agents_dir`. Built fresh on every call,
    matching `ConfigLoader`'s own no-caching convention at every existing
    call site in this daemon."""
    agents_dir = Path(agents_dir)
    roles: dict[str, dict] = {}
    if not agents_dir.exists():
        return roles

    for path in sorted(agents_dir.glob("*.prompt.md")):
        meta, _ = parse_prompt_file(path)
        name = meta.get("name")
        if not name:
            raise AgentRoleError(f"{path}: missing required 'name' field")

        role = meta.get("model_role")
        if role not in VALID_MODEL_ROLES:
            raise AgentRoleError(
                f"{path}: model_role must be one of {sorted(VALID_MODEL_ROLES)}, got {role!r}"
            )

        requires = meta.get("requires") or []
        unknown = sorted(set(requires) - VALID_REQUIRES)
        if unknown:
            raise AgentRoleError(f"{path}: unrecognized requires entries {unknown}")

        roles[name] = {"model_role": role, "requires": list(requires)}

    return roles

"""
Component intelligence pipeline (SPEC-202): a part number or datasheet
excerpt in, a validated structured component schema out -- replacing
daemon.py's mock_generate_component (time.sleep(1.5) plus fabricated
filenames) with a real AgentFlow .workflow.md DAG.

The DAG has two nodes: `extract` (an agent node -- calls the configured
LLM via SPEC-201's provider layer) and `validate` (a handler node --
plain, deterministic Python, no LLM call, no network). The handler is
this module's real substance: the three checks that stop a hallucinated
footprint from reaching a real board (ROADMAP.md §6's risk register).

An unrecognized package fails closed (a validation error, not a silent
pass-through) -- SPEC-202 §3 raised this as a decision this context
needed to make explicitly; a package this pipeline can't check against
is treated the same as a package that fails a check, not as an
exemption.

Deliberately decoupled from daemon.py's CONFIG global, matching
kicad_bridge/freecad_bridge/llm_providers's own pattern -- callers pass
in the secrets dict explicitly rather than this module reaching into a
daemon-owned global.
"""
import asyncio
import json
import os

from agentflow import AgentExecutor, ConfigLoader, NodeOutput, WorkflowExecutor
from agentflow.workflow.node import NodeRunner

import llm_providers


class ComponentValidationError(Exception):
    """Raised when the extracted component schema fails a safety check --
    a clean, specific error naming which check failed and why, never a
    silently-accepted hallucination."""


_AGENTFLOW_DIR = os.path.join(os.path.dirname(__file__), "agentflow")

# Real, standard package dimensions -- pin count and pitch (mm) for each
# recognized package family. `pitch_range_mm` is `None` for packages
# where "pitch" isn't a meaningful check (a 2-terminal passive has no
# adjacent-pin spacing to validate) -- the pitch check is skipped for
# those, not silently passed as if it were checked.
PACKAGE_REFERENCE = {
    "SOIC-8": {"pin_count": 8, "pitch_range_mm": (1.17, 1.37)},
    "SOIC-14": {"pin_count": 14, "pitch_range_mm": (1.17, 1.37)},
    "SOIC-16": {"pin_count": 16, "pitch_range_mm": (1.17, 1.37)},
    "TSSOP-8": {"pin_count": 8, "pitch_range_mm": (0.55, 0.75)},
    "TQFP-32": {"pin_count": 32, "pitch_range_mm": (0.70, 0.90)},
    "TQFP-44": {"pin_count": 44, "pitch_range_mm": (0.70, 0.90)},
    "QFN-16": {"pin_count": 16, "pitch_range_mm": (0.40, 0.60)},
    "QFN-24": {"pin_count": 24, "pitch_range_mm": (0.40, 0.60)},
    "DIP-8": {"pin_count": 8, "pitch_range_mm": (2.44, 2.64)},
    "DIP-14": {"pin_count": 14, "pitch_range_mm": (2.44, 2.64)},
    "SOT-23": {"pin_count": 3, "pitch_range_mm": (0.85, 1.05)},
    "0603": {"pin_count": 2, "pitch_range_mm": None},
    "0805": {"pin_count": 2, "pitch_range_mm": None},
}

# How much larger than the package body the courtyard must be, per side,
# to count as "encloses the pads" -- a standard, conservative clearance,
# not zero (a courtyard exactly equal to the package body leaves no room
# for the pads themselves, which extend beyond the body on most packages).
_COURTYARD_MIN_CLEARANCE_MM = 0.1


def _extract_json(text: str) -> dict:
    """Parses the extraction agent's response as JSON, tolerating the
    common case of a model wrapping its answer in a markdown code fence
    despite being told not to -- real LLM output doesn't always follow
    instructions exactly, and treating that as a validation error (rather
    than a parse error) would be a confusing failure mode."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ComponentValidationError(f"Extraction did not return valid JSON: {e}") from e


def validate_schema(schema: dict) -> None:
    """Runs the three safety checks against an already-parsed component
    schema. Raises ComponentValidationError naming the first check that
    fails -- never returns a partial/best-effort result."""
    package = schema.get("package")
    reference = PACKAGE_REFERENCE.get(package)
    if reference is None:
        raise ComponentValidationError(
            f"Package '{package}' is not in the known reference table -- cannot verify pin "
            f"count or pitch. Add it to PACKAGE_REFERENCE or provide package data manually."
        )

    pins = schema.get("pins", [])
    if len(pins) != reference["pin_count"]:
        raise ComponentValidationError(
            f"Package '{package}' expects {reference['pin_count']} pins, got {len(pins)}."
        )

    pitch_range = reference["pitch_range_mm"]
    if pitch_range is not None:
        pitch = schema.get("package_dimensions", {}).get("pitch_mm")
        if pitch is None or not (pitch_range[0] <= pitch <= pitch_range[1]):
            raise ComponentValidationError(
                f"Package '{package}' pitch {pitch}mm is outside the sane range "
                f"{pitch_range[0]}-{pitch_range[1]}mm."
            )

    dims = schema.get("package_dimensions", {})
    courtyard = schema.get("courtyard", {})
    for axis, dim_key in (("length", "length_mm"), ("width", "width_mm")):
        body = dims.get(dim_key)
        yard = courtyard.get(dim_key)
        if body is None or yard is None or yard < body + _COURTYARD_MIN_CLEARANCE_MM:
            raise ComponentValidationError(
                f"Courtyard {axis} ({yard}mm) does not enclose the package body "
                f"({axis}={body}mm) with the required {_COURTYARD_MIN_CLEARANCE_MM}mm clearance."
            )


async def validate_component_schema(message: str, prior_outputs: dict) -> NodeOutput:
    """The workflow's `validate` handler node (AgentFlow's HandlerFn
    signature): parses the extraction agent's raw text as JSON, runs the
    three safety checks, and returns the validated schema as an artifact.
    Raises ComponentValidationError, which WorkflowExecutor.run catches
    and reports as a node error -- generate_component below turns that
    back into a clean, specific exception rather than a partial result."""
    schema = _extract_json(message)
    validate_schema(schema)
    return NodeOutput(
        node_id="validate",
        agent_id="validate_component_schema",
        text=json.dumps(schema),
        artifacts={"schema": schema, "valid": True},
    )


def _build_agent_executor(agent_name: str, loader: ConfigLoader, secrets: dict) -> tuple:
    """Returns (AgentExecutor, provider_client) -- the raw provider client
    is returned alongside so the caller can close it explicitly, since
    AgentExecutor calls the provider's own .chat() directly (not
    llm_providers.chat(), which already carries CTX-201.1's close-in-
    same-loop fix). Without this, each real workflow run leaks an
    unclosed async client the same way llm_providers.chat() itself did
    before that fix -- caught here the same way, by running it for real."""
    config, prompt_body = loader.get_agent(agent_name)
    api_key = secrets.get(f"{config.provider}_api_key", "")
    provider_client = llm_providers._build_provider(config.provider, api_key, config.model)
    executor = AgentExecutor(config=config, prompt_body=prompt_body, llm=provider_client)
    return executor, provider_client


async def _run_workflow_and_close(executor: WorkflowExecutor, part_number: str, provider_clients: list) -> dict:
    """Runs the workflow and closes every provider client built along the
    way, all inside the same event loop -- see _build_agent_executor's
    own docstring for why this is necessary."""
    try:
        return await executor.run(initial_message=part_number)
    finally:
        for provider_client in provider_clients:
            await llm_providers._close_provider_client(provider_client)


def generate_component(part_number: str, secrets: dict = None) -> dict:
    """The kicad.generate_component route (SPEC-202): runs the real
    extract -> validate DAG and returns the validated schema, or raises
    ComponentValidationError for any check failure. Synchronous, matching
    daemon.py's ROUTES dispatch (SPEC-102) -- the async/sync boundary is
    resolved here, the same pattern llm_providers.chat already
    established for SPEC-201."""
    secrets = secrets or {}

    loader = ConfigLoader(_AGENTFLOW_DIR)
    loader.load()
    config, _ = loader.get_workflow("component_intelligence")

    provider_clients = []

    def runner_factory(node_id: str) -> NodeRunner:
        node = next(n for n in config.nodes if n.id == node_id)
        executor, provider_client = _build_agent_executor(node.agent, loader, secrets)
        provider_clients.append(provider_client)
        return NodeRunner(node, executor)

    workflow_executor = WorkflowExecutor(
        config=config,
        runner_factory=runner_factory,
        handlers={"validate_component_schema": validate_component_schema},
    )

    outputs = asyncio.run(_run_workflow_and_close(workflow_executor, part_number, provider_clients))

    validate_output = outputs["validate"]
    if validate_output.metadata.get("error"):
        raise ComponentValidationError(validate_output.text.removeprefix("Error: "))

    return validate_output.artifacts["schema"]

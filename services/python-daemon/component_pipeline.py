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

# Real-world package naming has common synonyms an extraction agent may
# reasonably use ("PDIP-8" for "DIP-8") -- found by real end-to-end
# testing of SPEC-307's Part Detail re-extraction, where a real search
# result's own naming ("PDIP-8") failed this table's exact-string match
# even though the geometry is identical to an entry already present.
# Generated from PACKAGE_REFERENCE itself rather than hand-duplicated, so
# every current and future DIP-N entry gets its PDIP-N alias for free.
for _dip_key in list(PACKAGE_REFERENCE):
    if _dip_key.startswith("DIP-"):
        PACKAGE_REFERENCE[f"P{_dip_key}"] = PACKAGE_REFERENCE[_dip_key]
del _dip_key

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


def _build_agent_executor(
    agent_name: str, loader: ConfigLoader, secrets: dict, provider: str = None, model: str = None,
) -> tuple:
    """Returns (AgentExecutor, provider_client) -- the raw provider client
    is returned alongside so the caller can close it explicitly, since
    AgentExecutor calls the provider's own .chat() directly (not
    llm_providers.chat(), which already carries CTX-201.1's close-in-
    same-loop fix). Without this, each real workflow run leaks an
    unclosed async client the same way llm_providers.chat() itself did
    before that fix -- caught here the same way, by running it for real.

    `provider`/`model` (SPEC-303, CTX-303.2) override the agent's own
    `.prompt.md` frontmatter default when given -- daemon.py resolves
    these from CONFIG["llm_provider"]/["llm_model"] (the Settings-
    configured value), the same precedence llm_chat already uses. Neither
    given leaves the prompt file's own hardcoded default untouched, so a
    fresh install with nothing configured in Settings yet behaves exactly
    as before (CTX-303.1 Plan Drift Deviation 2 -- this used to always run
    the extraction agent's own hardcoded provider, ignoring Settings
    entirely).

    Switching `provider` without an explicit `model` does NOT keep the
    prompt file's own model default -- that default is provider-specific
    (e.g. an Anthropic model name) and is invalid for a different
    provider's API, which a real call against Google proved directly:
    an empty response, surfaced as a confusing JSON-parse error rather
    than an obviously-wrong-model error. Falls back to that new
    provider's own default model instead, the same fallback
    `llm_providers._build_provider` already applies when `model` is
    falsy -- applied explicitly here since `config.model` would
    otherwise never be falsy."""
    config, prompt_body = loader.get_agent(agent_name)
    overrides = {}
    if provider:
        overrides["provider"] = provider
    if model:
        overrides["model"] = model
    elif provider:
        overrides["model"] = llm_providers._DEFAULT_MODELS.get(provider, config.model)
    if overrides:
        config = config.model_copy(update=overrides)

    api_key = secrets.get(f"{config.provider}_api_key", "")
    provider_client = llm_providers._build_provider(config.provider, api_key, config.model)
    executor = AgentExecutor(config=config, prompt_body=prompt_body, llm=provider_client)
    return executor, provider_client


_SEARCH_REQUIRED_FIELDS = ("part_number", "manufacturer", "package", "datasheet_url", "confidence")
_SEARCH_CONFIDENCE_LEVELS = ("high", "medium", "low")


def _validate_candidates(candidates) -> list:
    """SPEC-306 §2: the disambiguation card is the only place a bad
    identity guess gets caught, so a malformed response fails closed here
    rather than reaching the UI as a half-populated card. `confidence` is
    a closed enum (matching component_extraction.prompt.md's own
    electrical_type enum pattern) so the UI can render a predictable
    label, never a raw, possibly-inconsistent float."""
    if not isinstance(candidates, list) or not candidates:
        raise ComponentValidationError("Search did not return a non-empty list of candidates.")
    for candidate in candidates:
        missing = [f for f in _SEARCH_REQUIRED_FIELDS if not candidate.get(f)]
        if missing:
            raise ComponentValidationError(
                f"Search candidate is missing required field(s): {', '.join(missing)}."
            )
        if candidate["confidence"] not in _SEARCH_CONFIDENCE_LEVELS:
            raise ComponentValidationError(
                f"Search candidate confidence '{candidate['confidence']}' is not one of "
                f"{_SEARCH_CONFIDENCE_LEVELS}."
            )
    return candidates


async def _run_agent_and_close(executor: AgentExecutor, message: str, provider_client) -> str:
    """Runs a single standalone agent call (no WorkflowExecutor/DAG --
    search has no deterministic validate step the way generate_component
    does) and closes its provider client in the same event loop, same
    reason _run_workflow_and_close does."""
    try:
        output = await executor.run(message=message)
        return output.text
    finally:
        await llm_providers._close_provider_client(provider_client)


def search_components(query: str, secrets: dict = None, provider: str = None, model: str = None) -> list:
    """The component.search route (SPEC-306): a free-text query in,
    ranked candidates out -- a sibling to generate_component, not a
    branch inside it, since it's a distinct extraction shape (multiple
    ranked candidates with a confidence signal, not one committed
    schema). Never auto-selects a single result, even a high-confidence
    one -- that's the UI's job to enforce by always rendering a
    disambiguation card (SPEC-306 §2)."""
    secrets = secrets or {}

    loader = ConfigLoader(_AGENTFLOW_DIR)
    loader.load()
    executor, provider_client = _build_agent_executor("component_search", loader, secrets, provider, model)

    text = asyncio.run(_run_agent_and_close(executor, query, provider_client))
    candidates = _extract_json(text)
    return _validate_candidates(candidates)


_GUIDANCE_REQUIRED_FIELDS = ("pin_guidance", "general_notes")


def _validate_connection_guidance(response, pins: list) -> dict:
    """SPEC-308's own real safety check for this concern: every
    pin_number the response references must be a real pin on this part
    -- a hallucinated pin reference would point the user at the wrong
    physical pin, the same category of consequence validate_schema's
    checks exist to prevent for footprint geometry, applied here to
    advisory text instead of pad placement."""
    if not isinstance(response, dict):
        raise ComponentValidationError("Connection guidance did not return a JSON object.")

    missing = [f for f in _GUIDANCE_REQUIRED_FIELDS if f not in response]
    if missing:
        raise ComponentValidationError(
            f"Connection guidance response is missing required field(s): {', '.join(missing)}."
        )

    pin_guidance = response["pin_guidance"]
    if not isinstance(pin_guidance, list):
        raise ComponentValidationError("Connection guidance's pin_guidance must be a list.")

    real_pin_numbers = {str(p["number"]) for p in pins}
    for entry in pin_guidance:
        entry_missing = [f for f in ("pin_number", "guidance") if not entry.get(f)]
        if entry_missing:
            raise ComponentValidationError(
                f"Connection guidance pin entry is missing required field(s): {', '.join(entry_missing)}."
            )
        if str(entry["pin_number"]) not in real_pin_numbers:
            raise ComponentValidationError(
                f"Connection guidance references pin '{entry['pin_number']}', which is not a real "
                f"pin on this part."
            )

    if not isinstance(response.get("general_notes"), str):
        raise ComponentValidationError("Connection guidance's general_notes must be a string.")

    return response


def generate_connection_guidance(
    part_number: str, package: str, pins: list, secrets: dict = None, provider: str = None, model: str = None,
) -> dict:
    """The kicad.generate_connection_guidance route -- SPEC-308's third
    named concern (decoupling, protection, power), once a part and its
    footprint are both real (PRODUCT-PLAN.md's own framing). A single
    standalone agent call, like search_components -- no deterministic
    validate DAG step, since the one real safety check here (every
    referenced pin_number is real) is cheap enough to run inline rather
    than warranting a separate handler node."""
    secrets = secrets or {}

    loader = ConfigLoader(_AGENTFLOW_DIR)
    loader.load()
    executor, provider_client = _build_agent_executor("connection_guidance", loader, secrets, provider, model)

    message = json.dumps({"part_number": part_number, "package": package, "pins": pins})
    text = asyncio.run(_run_agent_and_close(executor, message, provider_client))
    response = _extract_json(text)
    return _validate_connection_guidance(response, pins)


async def _run_workflow_and_close(executor: WorkflowExecutor, part_number: str, provider_clients: list) -> dict:
    """Runs the workflow and closes every provider client built along the
    way, all inside the same event loop -- see _build_agent_executor's
    own docstring for why this is necessary."""
    try:
        return await executor.run(initial_message=part_number)
    finally:
        for provider_client in provider_clients:
            await llm_providers._close_provider_client(provider_client)


def generate_component(part_number: str, secrets: dict = None, provider: str = None, model: str = None) -> dict:
    """The kicad.generate_component route (SPEC-202): runs the real
    extract -> validate DAG and returns the validated schema, or raises
    ComponentValidationError for any check failure. Synchronous, matching
    daemon.py's ROUTES dispatch (SPEC-102) -- the async/sync boundary is
    resolved here, the same pattern llm_providers.chat already
    established for SPEC-201.

    `provider`/`model` (SPEC-303, CTX-303.2) let the caller (daemon.py,
    from CONFIG["llm_provider"]/["llm_model"]) override the extraction
    agent's own hardcoded default -- see _build_agent_executor."""
    secrets = secrets or {}

    loader = ConfigLoader(_AGENTFLOW_DIR)
    loader.load()
    config, _ = loader.get_workflow("component_intelligence")

    provider_clients = []

    def runner_factory(node_id: str) -> NodeRunner:
        node = next(n for n in config.nodes if n.id == node_id)
        executor, provider_client = _build_agent_executor(node.agent, loader, secrets, provider, model)
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

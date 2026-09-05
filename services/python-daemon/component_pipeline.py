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
import logging
import os

from agentflow import AgentExecutor, ConfigLoader, JSONResponseError, NodeOutput, WorkflowExecutor, parse_json_response
from agentflow.workflow.node import NodeRunner

import agent_roles
import llm_providers

logger = logging.getLogger(__name__)


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
    # CTX-202.2: a real, live extraction of the ESP32-S3 (QFN-56, 7x7mm)
    # failed closed here -- not a bug in the fail-closed design itself
    # (SPEC-202 §3's own explicit choice), just a real, common package
    # this table hadn't been given yet. Same pitch range as the other
    # QFN entries above -- this table has no finer-grained real source
    # for QFN-56 specifically to narrow it further. `exposed_pad: True`:
    # a second real, live extraction found the model correctly reporting
    # a real 57th pin, "GND_PAD" -- the ESP32-S3's own datasheet numbers
    # its exposed thermal/ground pad as a real electrical contact, not a
    # hallucination. QFN-16/QFN-24 above are NOT marked this way --
    # plausibly the same real characteristic, but not verified against a
    # real datasheet, so left as a named, deliberate non-change rather
    # than a guess.
    # Third time this table has been the thing that failed a real part:
    # PDIP-8 (an alias miss), QFN-56 (CTX-202.2), and now QFN-32 -- hit
    # live while preparing the tutorial project, on an ATmega16U2-MU.
    # 0.5mm pitch on a 5x5mm body is the standard geometry for this part,
    # which sits inside the same 0.40-0.60 range every other QFN entry
    # here uses. NOT marked exposed_pad: the ATmega16U2's own datasheet
    # was not consulted, and QFN-16/QFN-24 are left unmarked for exactly
    # that reason -- a guess here widens a safety check.
    "QFN-32": {"pin_count": 32, "pitch_range_mm": (0.40, 0.60)},
    # QFN-48, hit live on an ESP32-D0WDQ6 minutes after QFN-32 -- the
    # third and fourth entries this table has been missing in one session.
    "QFN-48": {"pin_count": 48, "pitch_range_mm": (0.40, 0.60)},
    "QFN-56": {"pin_count": 56, "pitch_range_mm": (0.40, 0.60), "exposed_pad": True},
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
    """The extraction agent's response, as a schema object.

    Was a fence-stripper plus `json.loads`. Now AgentFlow's
    `parse_json_response` (0.12.0), which also handles prose around the
    value and a model that corrects itself mid-response -- shapes the
    fence-stripper turned into a parse error, and which this route then
    spent a whole retry attempt on.

    Deliberately unconstrained by type. `expect=dict` looks right from the
    annotation and is wrong: this helper is shared with `search_components`,
    whose response is legitimately a JSON array of candidates. The `-> dict`
    annotation was already describing only one of its two callers. Caught by
    `TestRealSearchComponents`, not by reading."""
    try:
        return parse_json_response(text)
    except JSONResponseError as e:
        # The response goes to the log, not to the person. Before this, a
        # truncated extraction put 500 characters of raw JSON into a red box
        # in the app -- accurate, and useless to anyone who is not holding
        # this file open.
        logger.warning("extraction returned unusable output: %s", e)

        # An unclosed brace or bracket means the model stopped mid-answer
        # rather than answering badly, and the two deserve different
        # sentences. Found live on an ESP32-D0WDQ6: 48 pins, cut off at pin
        # 31, against a max_tokens that could not hold the list.
        truncated = text.count("{") > text.count("}") or text.count("[") > text.count("]")
        detail = (
            "the model's answer was cut off before it finished"
            if truncated
            else "the model's answer was not readable as data"
        )
        raise ComponentValidationError(
            f"{_JSON_PARSE_ERROR_PREFIX}: {detail}. This usually means the part has an unusually "
            f"long pin list. Trying again often works, and the details are in the log."
        ) from e


def validate_schema(schema: dict) -> None:
    """Runs the three safety checks against an already-parsed component
    schema. Raises ComponentValidationError naming the first check that
    fails -- never returns a partial/best-effort result."""
    package = schema.get("package")
    reference = PACKAGE_REFERENCE.get(package)
    if reference is None:
        # The old wording of this told the user to "add it to
        # PACKAGE_REFERENCE" -- the name of a Python constant they cannot
        # see, in red text, in a desktop app. That is a developer's note
        # rendered as a user-facing error. What a person needs here is what
        # was not checked and what still works.
        # This message previously said "the library entry is still good".
        # There is no library entry: this raises, the extraction aborts, and
        # nothing is saved. Reassurance about a record that does not exist is
        # worse than the developer-facing text it replaced, and the guard in
        # tests/test_user_facing_errors.py could not catch it -- that check
        # reads for spec numbers and identifiers, not for truth.
        raise ComponentValidationError(
            f"Copperplane has no reference dimensions for the '{package}' package, so it cannot "
            f"check this part's pin count or spacing -- and it will not save a part it could not "
            f"check. Nothing has been added to your library. Modules and development boards hit "
            f"this most often, because their packages are descriptions rather than standard "
            f"package names."
        )

    pins = schema.get("pins", [])
    # CTX-202.2: a package with a real, documented exposed thermal/ground
    # pad (confirmed live for QFN-56 -- the ESP32-S3's own datasheet
    # numbers it as a real pin, "GND_PAD") may legitimately report either
    # the package's nominal lead count or that count plus one for the
    # pad itself. Every other package keeps the original exact-match
    # check -- this widening is real and specific to that documented
    # exception, not a general loosening.
    expected_counts = {reference["pin_count"]}
    if reference.get("exposed_pad"):
        expected_counts.add(reference["pin_count"] + 1)
    if len(pins) not in expected_counts:
        expected_desc = " or ".join(str(n) for n in sorted(expected_counts))
        raise ComponentValidationError(
            f"Package '{package}' expects {expected_desc} pins, got {len(pins)}."
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
    app_config: dict = None,
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
    entirely). The override computation itself is `llm_providers.resolve()`
    (SPEC-208 §2.6), consolidated with `chat_agents._dispatch`'s identical
    duplicate rather than kept as two copies.

    Switching `provider` without an explicit `model` does NOT keep the
    prompt file's own model default -- that default is provider-specific
    (e.g. an Anthropic model name) and is invalid for a different
    provider's API, which a real call against Google proved directly:
    an empty response, surfaced as a confusing JSON-parse error rather
    than an obviously-wrong-model error. Falls back to that new
    provider's own default model instead, the same fallback `resolve()`
    applies when `model` is falsy -- applied explicitly here since
    `config.model` would
    otherwise never be falsy.

    `app_config` (CTX-208.2, SPEC-208 §2.3.2): `daemon.CONFIG` itself --
    named `app_config` rather than `config` purely to avoid shadowing
    this function's own long-standing local `config` (the agent's own
    `AgentConfig`, from `loader.get_agent`). Passed straight through to
    `llm_providers.resolve()` and nowhere else read."""
    config, prompt_body = loader.get_agent(agent_name)
    agent_role = agent_roles.load_agent_roles(os.path.join(_AGENTFLOW_DIR, "agents")).get(agent_name, {})
    # SPEC-208 §2.6: the override-computation this used to do itself is
    # now `llm_providers.resolve()`'s job, consolidated with
    # `chat_agents._dispatch`'s identical duplicate. `model_role`
    # (CTX-208.2) routes through `app_config`'s provider_roles binding
    # when no explicit provider/model override is given.
    provider_client, resolved_provider, resolved_model = llm_providers.resolve(
        config.provider, config.model, secrets, provider=provider, model=model,
        config=app_config, model_role=agent_role.get("model_role"),
        agent_name=agent_name, requires=agent_role.get("requires"),
    )
    config = config.model_copy(update={"provider": resolved_provider, "model": resolved_model})
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


def search_components(
    query: str, secrets: dict = None, provider: str = None, model: str = None, app_config: dict = None,
) -> list:
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
    executor, provider_client = _build_agent_executor(
        "component_search", loader, secrets, provider, model, app_config=app_config,
    )

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
    app_config: dict = None,
) -> dict:
    """The kicad.generate_connection_guidance route -- SPEC-308's third
    named concern (decoupling, protection, power), once a part and its
    footprint are both real (PRODUCT-PLAN.md's own framing). A single
    standalone agent call, like search_components -- no deterministic
    validate DAG step, since the one real safety check here (every
    referenced pin_number is real) is cheap enough to run inline rather
    than warranting a separate handler node.

    CTX-206.1: the returned dict carries a `provenance` key
    (`{"provider": str, "model": str}`) alongside the validated
    response, read from `executor.config` -- the real, resolved
    provider/model after `_build_agent_executor`'s own override logic
    (Settings vs. the prompt file's own default), not just whatever the
    caller happened to pass in, which may be `None`. `AgentExecutor.config`
    is a real public property, confirmed by reading the installed
    `agentflow/agent/runtime.py` before relying on it. daemon.py's route
    persists this alongside the rest via `library_store
    .save_part_connection_guidance`, closing SPEC-206 §2.4's prerequisite
    gap; this key was not part of this function's return shape before."""
    secrets = secrets or {}

    loader = ConfigLoader(_AGENTFLOW_DIR)
    loader.load()
    executor, provider_client = _build_agent_executor(
        "connection_guidance", loader, secrets, provider, model, app_config=app_config,
    )
    resolved_provenance = {"provider": executor.config.provider, "model": executor.config.model}

    message = json.dumps({"part_number": part_number, "package": package, "pins": pins})
    text = asyncio.run(_run_agent_and_close(executor, message, provider_client))
    response = _extract_json(text)
    validated = _validate_connection_guidance(response, pins)
    validated["provenance"] = resolved_provenance
    return validated


_FOOTPRINT_QUERY_REQUIRED_FIELDS = ("query", "alternates", "reasoning")


def _validate_footprint_query_suggestion(response) -> dict:
    """This response is only ever a *search term suggestion* fed into the
    existing, already-real kicad.search_footprints/library.search_community_footprints
    routes, which the user confirms against real results themselves --
    unlike validate_schema/_validate_connection_guidance, there is no
    real-world fact to check the response against (a suggested string is
    never wrong, only more or less useful), so this only enforces the
    response's own shape, not its content."""
    if not isinstance(response, dict):
        raise ComponentValidationError("Footprint query suggestion did not return a JSON object.")

    missing = [f for f in _FOOTPRINT_QUERY_REQUIRED_FIELDS if f not in response]
    if missing:
        raise ComponentValidationError(
            f"Footprint query suggestion response is missing required field(s): {', '.join(missing)}."
        )
    if not isinstance(response["query"], str) or not response["query"].strip():
        raise ComponentValidationError("Footprint query suggestion's query must be a non-empty string.")
    if not isinstance(response["alternates"], list):
        raise ComponentValidationError("Footprint query suggestion's alternates must be a list.")
    if not isinstance(response["reasoning"], str):
        raise ComponentValidationError("Footprint query suggestion's reasoning must be a string.")

    return response


def suggest_footprint_query(
    part_number: str, manufacturer: str, package: str, secrets: dict = None, provider: str = None, model: str = None,
    app_config: dict = None,
) -> dict:
    """The kicad.suggest_footprint_query route (CTX-308.10): real user
    feedback -- a user searching for a footprint naturally tries the
    part's own name/package first, and has no reliable way to know what
    else to type if that doesn't match. A single standalone agent call,
    like generate_connection_guidance above -- this only ever suggests a
    *search term* for the user to run through the existing footprint
    search routes and confirm themselves; it never asserts a specific
    footprint exists or picks one on the user's behalf, so there is no
    hallucination risk of the kind validate_schema/_validate_connection_guidance
    guard against."""
    secrets = secrets or {}

    loader = ConfigLoader(_AGENTFLOW_DIR)
    loader.load()
    executor, provider_client = _build_agent_executor(
        "footprint_query_suggestion", loader, secrets, provider, model, app_config=app_config,
    )
    resolved_provenance = {"provider": executor.config.provider, "model": executor.config.model}

    message = json.dumps({"part_number": part_number, "manufacturer": manufacturer, "package": package})
    text = asyncio.run(_run_agent_and_close(executor, message, provider_client))
    response = _extract_json(text)
    validated = _validate_footprint_query_suggestion(response)
    validated["provenance"] = resolved_provenance
    return validated


# How many violations go into a single explain-and-suggest LLM call.
# Real, named decision (SPEC-309 §3 flagged this explicitly as
# unresolved) -- errors first, then warnings, then exclusions (the same
# real severity vocabulary kicad_cli.py's JSON reports use), so a capped
# call still covers the violations that matter most rather than an
# arbitrary prefix of the raw list. component_search's own real
# max_tokens truncation bug (CTX-308.7 Plan Drift) is exactly the failure
# mode capping the violation *count* going in is meant to avoid.
_MAX_VIOLATIONS_PER_EXPLANATION_CALL = 15
_VIOLATION_SEVERITY_ORDER = {"error": 0, "warning": 1, "exclusion": 2}


def _prioritize_violations(violations: list) -> list:
    return sorted(violations, key=lambda v: _VIOLATION_SEVERITY_ORDER.get(v.get("severity"), 99))


def _validate_board_advisor_response(response, violation_count: int) -> dict:
    """SPEC-309's own real safety check: every index the response
    references must be a real index into the violations it was given,
    and every one of those violations must get an explanation -- a
    skipped violation would silently hide a real problem from the user,
    the opposite of what this feature exists to do."""
    if not isinstance(response, dict):
        raise ComponentValidationError("Board advisor did not return a JSON object.")

    missing_top = [f for f in ("violation_explanations", "summary") if f not in response]
    if missing_top:
        raise ComponentValidationError(
            f"Board advisor response is missing required field(s): {', '.join(missing_top)}."
        )

    explanations = response["violation_explanations"]
    if not isinstance(explanations, list):
        raise ComponentValidationError("Board advisor's violation_explanations must be a list.")

    seen_indexes = set()
    for entry in explanations:
        # "index" is checked for key presence, not truthiness -- a real
        # index of 0 is falsy in Python and must not be mistaken for a
        # missing field the way `not entry.get("index")` would.
        entry_missing = [f for f in ("explanation", "suggested_fix") if not entry.get(f)]
        if "index" not in entry:
            entry_missing.append("index")
        if entry_missing:
            raise ComponentValidationError(
                f"Board advisor explanation entry is missing required field(s): {', '.join(entry_missing)}."
            )
        index = entry["index"]
        if not isinstance(index, int) or not (0 <= index < violation_count):
            raise ComponentValidationError(
                f"Board advisor references violation index {index!r}, out of range for the "
                f"{violation_count} violation(s) given."
            )
        seen_indexes.add(index)

    missing_indexes = sorted(set(range(violation_count)) - seen_indexes)
    if missing_indexes:
        raise ComponentValidationError(
            f"Board advisor did not explain violation index(es): {missing_indexes}."
        )

    if not isinstance(response.get("summary"), str):
        raise ComponentValidationError("Board advisor's summary must be a string.")

    return response


def explain_violations(
    violations: list, check_type: str, secrets: dict = None, provider: str = None, model: str = None,
    app_config: dict = None,
) -> dict:
    """The kicad.check_board/kicad.check_schematic routes' own real
    substance (SPEC-309): a single standalone agent call (like
    search_components/generate_connection_guidance -- no DAG) that turns
    KiCad's own real, structured ERC/DRC violations into plain-language
    explanation and a concrete suggested fix per violation. `check_type`
    is "erc" or "sch" -- passed straight through to the prompt so its
    own advice stays grounded in which real check produced these
    violations, never invented.

    Returns each real violation dict enriched with `explanation`/
    `suggested_fix`, plus `summary` and `truncated_count` (0 unless
    _MAX_VIOLATIONS_PER_EXPLANATION_CALL capped the real list) -- ready
    for the daemon route to return as-is, no re-indexing needed by the
    caller. A clean (empty) violations list short-circuits before any
    LLM call -- there is nothing to explain, and the honest, deterministic
    answer costs nothing, rather than spending a real network call asking
    a model to describe an empty list."""
    if not violations:
        return {"violations": [], "summary": "No violations found.", "truncated_count": 0}

    secrets = secrets or {}

    prioritized = _prioritize_violations(violations)
    truncated_count = max(0, len(prioritized) - _MAX_VIOLATIONS_PER_EXPLANATION_CALL)
    prioritized = prioritized[:_MAX_VIOLATIONS_PER_EXPLANATION_CALL]

    loader = ConfigLoader(_AGENTFLOW_DIR)
    loader.load()
    executor, provider_client = _build_agent_executor(
        "board_advisor", loader, secrets, provider, model, app_config=app_config,
    )

    indexed = [{"index": i, **v} for i, v in enumerate(prioritized)]
    message = json.dumps({"check_type": check_type, "violations": indexed})
    text = asyncio.run(_run_agent_and_close(executor, message, provider_client))
    response = _extract_json(text)
    validated = _validate_board_advisor_response(response, len(prioritized))

    explanations_by_index = {e["index"]: e for e in validated["violation_explanations"]}
    enriched = [
        {**prioritized[i], "explanation": explanations_by_index[i]["explanation"],
         "suggested_fix": explanations_by_index[i]["suggested_fix"]}
        for i in range(len(prioritized))
    ]
    return {"violations": enriched, "summary": validated["summary"], "truncated_count": truncated_count}


async def _run_workflow_and_close(executor: WorkflowExecutor, part_number: str, provider_clients: list) -> dict:
    """Runs the workflow and closes every provider client built along the
    way, all inside the same event loop -- see _build_agent_executor's
    own docstring for why this is necessary."""
    try:
        return await executor.run(initial_message=part_number)
    finally:
        for provider_client in provider_clients:
            await llm_providers._close_provider_client(provider_client)


# CTX-202.2: a real, live ESP32-S3 extraction failed with "Extraction did
# not return valid JSON" -- reproduced against the real Anthropic API,
# not assumed. Three fresh, direct calls to the extraction agent alone
# all succeeded (valid JSON, ~4400 chars, well under max_tokens), which
# ruled out truncation-at-the-token-limit as the cause: the reported
# failure was at character 2216, roughly half a complete response's real
# length, not near any token ceiling. That points at an occasional,
# non-deterministic malformed-JSON generation, not a parameter to tune --
# the real mitigation is a retry, not a bigger budget. Only retried for
# this specific failure class (the JSON-parse error `_extract_json`
# raises); any other validation failure (unrecognized package, hallucinated
# pin, missing field) is a real, deterministic problem a retry would not
# fix, and fails immediately, matching SPEC-202's own fail-closed design.
_MAX_EXTRACTION_ATTEMPTS = 2
_JSON_PARSE_ERROR_PREFIX = "Extraction did not return valid JSON"


def generate_component(
    part_number: str, secrets: dict = None, provider: str = None, model: str = None, app_config: dict = None,
) -> dict:
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

    for attempt in range(1, _MAX_EXTRACTION_ATTEMPTS + 1):
        provider_clients = []

        def runner_factory(node_id: str) -> NodeRunner:
            node = next(n for n in config.nodes if n.id == node_id)
            executor, provider_client = _build_agent_executor(
                node.agent, loader, secrets, provider, model, app_config=app_config,
            )
            provider_clients.append(provider_client)
            return NodeRunner(node, executor)

        workflow_executor = WorkflowExecutor(
            config=config,
            runner_factory=runner_factory,
            handlers={"validate_component_schema": validate_component_schema},
        )

        outputs = asyncio.run(_run_workflow_and_close(workflow_executor, part_number, provider_clients))

        validate_output = outputs["validate"]
        if not validate_output.metadata.get("error"):
            return validate_output.artifacts["schema"]

        error_text = validate_output.text.removeprefix("Error: ")
        if attempt < _MAX_EXTRACTION_ATTEMPTS and error_text.startswith(_JSON_PARSE_ERROR_PREFIX):
            logger.warning(
                "generate_component(%r): attempt %d/%d got malformed JSON, retrying: %s",
                part_number, attempt, _MAX_EXTRACTION_ATTEMPTS, error_text,
            )
            continue

        raise ComponentValidationError(error_text)

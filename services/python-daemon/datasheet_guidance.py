"""
Datasheet guidance extraction (SPEC-205): consumes CTX-205.1's real
structure pass (`datasheet_structure.extract_pages`/
`locate_candidate_sections`) and, for each real category with at least
one candidate page, runs a real AgentFlow `.workflow.md` DAG
(`agentflow/workflows/datasheet_guidance.workflow.md`) to extract Class
B (cited prose) guidance items -- SPEC-205 §2.1's "must cite" contract.

Real DAG shape, mirroring `component_pipeline.py`'s own
`component_intelligence` DAG exactly: `extract` (an agent node, calls
the configured LLM) then `validate` (a handler node, plain Python, no
LLM call). The one real difference from that precedent: AgentFlow's own
`WorkflowExecutor`/`NodeRunner` (confirmed directly against the
vendored source, `workflow/executor.py`/`workflow/node.py`) only ever
gives a handler node access to *prior node outputs* -- there is no
mechanism for a downstream handler to see the workflow's own
`initial_message` once execution has moved past the entry node. Citation
validation here genuinely needs the real page texts (external data, not
a node's own output) to check a quote actually appears where it's
cited. Resolved with a closure -- `_make_validate_handler` builds a
fresh `validate` handler function per real call, bound to that call's
own real page texts via Python closure, not AgentFlow's own (narrower)
node-output wiring. The DAG structure and execution are still 100% real
AgentFlow; only the handler's own captured inputs are plain Python,
exactly as legitimate as `component_pipeline.py`'s own inline
`runner_factory` closures already are.

Items that fail citation validation are dropped, not repaired or
promoted (SPEC-205 §2.2) -- a category with some invalid items still
returns its real, valid ones. A category with zero candidate pages
never reaches the LLM at all (matching
`component_pipeline.explain_violations`'s own "empty input, no LLM
call" precedent) -- real cost avoided, not just latency.

CTX-205.7 adds a second, single-node real workflow
(`agentflow/workflows/datasheet_guidance_synthesis.workflow.md`), run
after a category's items are validated: a plain-language summary
paragraph (SPEC-205 §2.1.1), generated strictly from that category's
own already-validated items -- never a new citable fact, never run for
a category with zero valid items. This exists because real, live user
testing of the first shipped Class B panel showed that even correctly
cited, verbatim datasheet prose is not the right reading experience for
this feature's real audience (a maker/hobbyist, not a practicing
hardware engineer) -- see SPEC-205 §1's real audience correction.
"""
import asyncio
import json
import logging
import os
import re

from agentflow import ConfigLoader, JSONResponseError, NodeOutput, WorkflowExecutor, parse_json_response
from agentflow.workflow.node import NodeRunner

import llm_providers
from component_pipeline import _build_agent_executor
from datasheet_structure import CATEGORY_PATTERNS, extract_pages, locate_candidate_sections


class DatasheetGuidanceError(Exception):
    """Raised when an extraction response can't be parsed as JSON at all --
    a real, visible pipeline failure, distinct from a real, valid empty
    result (`[]`) or from an individual item silently failing citation
    validation (dropped, not raised)."""


logger = logging.getLogger(__name__)

_AGENTFLOW_DIR = os.path.join(os.path.dirname(__file__), "agentflow")


#: Kept as a prefix constant because `_run_category_workflow` matches on it
#: to decide whether a failure is worth retrying, exactly as
#: `component_pipeline` already does.
_JSON_PARSE_ERROR_PREFIX = "Extraction did not return valid JSON"

#: One retry. The failures this recovers from are a model briefly losing the
#: output format, which does not repeat often; a longer ladder would mostly
#: buy latency and tokens on responses that were never going to parse.
_MAX_EXTRACTION_ATTEMPTS = 2


def _extract_json(text: str) -> object:
    """The extraction agent's response, as a list of items.

    Was a local fence-stripper plus `json.loads`, duplicated from
    `component_pipeline` to keep the modules independent. Both now call
    AgentFlow's `parse_json_response` (0.12.0), which handles the shapes a
    fence-stripper cannot -- prose around the value, and a model that
    produces a malformed array, notices, and writes the correct one after
    it. That last shape is why this changed: it was failing
    `datasheet.generate_guidance` outright while the right answer sat in
    the response.

    Deliberately unconstrained by type, though this route's prompt does ask
    for an array. The validate handler treats a non-list response as a real
    empty result rather than a failure -- a category with nothing in it is a
    valid outcome, and `test_014` pins that. Passing `expect=list` turns
    that documented behaviour into an error, which is a different feature
    wearing a bug fix's clothes."""
    try:
        return parse_json_response(text)
    except JSONResponseError as e:
        raise DatasheetGuidanceError(f"{_JSON_PARSE_ERROR_PREFIX}: {e}") from e


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _quote_appears_on_page(quote: str, page_text: str) -> bool:
    """The real citation check: `quote` must be a real (whitespace-
    normalized, case-insensitive) substring of `page_text` -- not an
    exact byte match, since PDF text extraction's own line-wrapping
    rarely matches a model's quoted wording exactly, but never a
    paraphrase either."""
    return _normalize_whitespace(quote).lower() in _normalize_whitespace(page_text).lower()


def _build_page_excerpt(pages_by_number: dict, page_numbers: list) -> str:
    """A real, labeled, numbered excerpt of just this category's real
    candidate pages -- the extraction agent only ever sees these pages,
    so it can only ever cite a page number that's genuinely present
    here (enforced again, deterministically, by the validate handler)."""
    sections = [f"--- Page {n} ---\n{pages_by_number.get(n, '')}" for n in page_numbers]
    return "\n\n".join(sections)


def _make_validate_handler(pages_by_number: dict, category: str, page_numbers: list):
    """Builds a real `validate` handler closure bound to this specific
    call's own real page texts and real candidate page numbers -- see
    this module's own docstring for why a closure, not AgentFlow's
    node-output wiring, is how this handler gets that data."""
    real_pages = set(page_numbers)

    async def validate_datasheet_guidance(message: str, prior_outputs: dict) -> NodeOutput:
        items = _extract_json(message)
        valid_items = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            page = item.get("page")
            quote = item.get("quote")
            if not isinstance(page, int) or page not in real_pages:
                continue
            if not isinstance(quote, str) or not quote.strip():
                continue
            if _quote_appears_on_page(quote, pages_by_number.get(page, "")):
                valid_items.append({"quote": quote, "page": page, "category": category})

        return NodeOutput(
            node_id="validate",
            agent_id="validate_datasheet_guidance",
            text=json.dumps(valid_items),
            artifacts={"items": valid_items},
        )

    return validate_datasheet_guidance


async def _run_category_workflow(
    category: str, page_numbers: list, pages_by_number: dict,
    loader: ConfigLoader, secrets: dict, provider: str, model: str, provider_clients: list,
    app_config: dict = None,
) -> list:
    """Runs the real `extract -> validate` DAG for one real category and
    returns its real, citation-valid guidance items. `provider_clients`
    is the caller's own accumulator -- appended to here, closed by the
    caller in one shared `finally` block, the same real leak-prevention
    shape `component_pipeline._run_workflow_and_close` already
    established."""
    config, _ = loader.get_workflow("datasheet_guidance")

    def runner_factory(node_id: str) -> NodeRunner:
        node = next(n for n in config.nodes if n.id == node_id)
        executor, provider_client = _build_agent_executor(
            node.agent, loader, secrets, provider, model, app_config=app_config,
        )
        provider_clients.append(provider_client)
        return NodeRunner(node, executor)

    handler = _make_validate_handler(pages_by_number, category, page_numbers)
    initial_message = f"Category: {category}\n\n{_build_page_excerpt(pages_by_number, page_numbers)}"

    # Retry a malformed response once, and only a malformed one. This is
    # `component_pipeline.generate_component`'s existing shape rather than a
    # new invention -- that route has retried extraction since SPEC-202, and
    # is the reason component generation mostly recovers from a bad response
    # while this route, which never had it, failed the whole job. A citation
    # that fails validation is not retried: that is the model being wrong
    # about the datasheet, not about JSON, and asking again invites a
    # plausible-looking second guess.
    for attempt in range(1, _MAX_EXTRACTION_ATTEMPTS + 1):
        # Built inside the loop, not once outside it: a second attempt gets a
        # fresh executor rather than re-running one that has already
        # completed a pass. `component_pipeline` does the same, and this
        # module's own convention is that each attempt's provider clients are
        # appended to the caller's accumulator and closed together.
        workflow_executor = WorkflowExecutor(
            config=config, runner_factory=runner_factory,
            handlers={"validate_datasheet_guidance": handler},
        )
        outputs = await workflow_executor.run(initial_message=initial_message)

        validate_output = outputs["validate"]
        if not validate_output.metadata.get("error"):
            return validate_output.artifacts["items"]

        error_text = validate_output.text.removeprefix("Error: ")
        if attempt < _MAX_EXTRACTION_ATTEMPTS and error_text.startswith(_JSON_PARSE_ERROR_PREFIX):
            logger.warning(
                "datasheet guidance (%s): attempt %d/%d got malformed JSON, retrying: %s",
                category, attempt, _MAX_EXTRACTION_ATTEMPTS, error_text,
            )
            continue

        raise DatasheetGuidanceError(error_text)


async def _run_synthesis_workflow(
    category: str, items: list,
    loader: ConfigLoader, secrets: dict, provider: str, model: str, provider_clients: list,
    app_config: dict = None,
) -> str:
    """Runs the real, single-node `datasheet_guidance_synthesis` workflow
    (SPEC-205 §2.1.1) over one category's already-validated items,
    returning a real plain-language summary paragraph. Never called for
    a category with zero validated items -- the caller
    (`_run_all_categories_and_close`) skips this entirely in that case,
    the same real "empty input, no LLM call" discipline
    `_run_category_workflow`'s own caller already applies."""
    config, _ = loader.get_workflow("datasheet_guidance_synthesis")

    def runner_factory(node_id: str) -> NodeRunner:
        node = next(n for n in config.nodes if n.id == node_id)
        executor, provider_client = _build_agent_executor(
            node.agent, loader, secrets, provider, model, app_config=app_config,
        )
        provider_clients.append(provider_client)
        return NodeRunner(node, executor)

    workflow_executor = WorkflowExecutor(config=config, runner_factory=runner_factory, handlers={})

    initial_message = f"Category: {category}\n\nCited excerpts:\n{json.dumps(items)}"
    outputs = await workflow_executor.run(initial_message=initial_message)

    synthesize_output = outputs["synthesize"]
    if synthesize_output.metadata.get("error"):
        raise DatasheetGuidanceError(synthesize_output.text.removeprefix("Error: "))
    return synthesize_output.text.strip()


async def _run_all_categories_and_close(
    categories_to_run: dict, pages_by_number: dict,
    loader: ConfigLoader, secrets: dict, provider: str, model: str, cancel_event=None,
    app_config: dict = None,
) -> tuple:
    """Runs every real category with candidate pages sequentially (not
    concurrently -- a real, deliberate simplification for this context;
    see this module's own Plan Drift if latency against a real
    multi-category document proves this too slow later), closing every
    provider client built along the way in one shared `finally`, the
    same real leak-prevention shape
    `component_pipeline._run_workflow_and_close` already established.

    CTX-205.3: `cancel_event` (a real `threading.Event`, matching
    `freecad_bridge._wait_with_cancellation`'s own exact check) is
    tested once per category, before that category's own workflow
    starts -- coarse-grained, not mid-LLM-call, but real: an 8-category
    document (~23s total observed) responds to cancellation within one
    category's own real runtime, not the whole document's. A cancelled
    run returns whatever real categories already completed, same as a
    normal partial short-circuit -- `daemon.py`'s own `_run_job` judges
    cancelled-vs-completed purely by `cancel_event`'s own state
    afterward, not by what this function returns.

    CTX-205.7: after a category's items are validated, its real
    plain-language summary (SPEC-205 §2.1.1) is generated in the same
    pass, in the same shared provider-client lifecycle -- never for a
    category with zero validated items, which gets `None` directly with
    no LLM call, the same real cost discipline as the extraction step's
    own zero-candidates short-circuit. Returns `(items_by_category,
    summaries_by_category)`."""
    provider_clients: list = []
    results = {}
    summaries = {}
    try:
        for category, page_numbers in categories_to_run.items():
            if cancel_event is not None and cancel_event.is_set():
                break
            items = await _run_category_workflow(
                category, page_numbers, pages_by_number, loader, secrets, provider, model, provider_clients,
                app_config=app_config,
            )
            results[category] = items
            summaries[category] = (
                await _run_synthesis_workflow(
                    category, items, loader, secrets, provider, model, provider_clients, app_config=app_config,
                )
                if items else None
            )
        return results, summaries
    finally:
        for provider_client in provider_clients:
            await llm_providers._close_provider_client(provider_client)


def generate_datasheet_guidance(
    pdf_path: str, categories: list = None, secrets: dict = None, provider: str = None, model: str = None,
    cancel_event=None, app_config: dict = None,
) -> dict:
    """The real, top-level entry point this context ships: a real
    datasheet PDF path in, real cited guidance out, grouped by category --
    `{"categories": {category: [{"quote", "page", "category"}, ...], ...},
    "summaries": {category: "plain-language paragraph" | None, ...}}`.
    Both dicts carry *every* real category (an empty list / `None` for
    one with no candidate pages or no valid items, not an omitted key --
    SPEC-205 §5's own "first-class empty state" principle applies even
    at this backend layer, before any UI exists to render it).
    `summaries` is CTX-205.7's own real plain-language layer (SPEC-205
    §2.1.1) -- generated only for a category with at least one validated
    item, never independently of `categories`, never a new citable fact.

    `categories` restricts which of `datasheet_structure.CATEGORY_PATTERNS`'s
    real categories to run (default: all of them). `cancel_event` is
    optional -- `daemon.py`'s own `_run_job` only ever passes it because
    this function's real signature declares the param (checked via
    `inspect.signature`, the same real mechanism the FreeCAD routes
    already use), so a direct, non-daemon caller (e.g. a test) never
    needs to pass one."""
    secrets = secrets or {}
    categories = categories or list(CATEGORY_PATTERNS)

    pages = extract_pages(pdf_path)
    pages_by_number = {p["page"]: p["text"] for p in pages}
    candidates = locate_candidate_sections(pages)

    categories_to_run = {c: candidates.get(c, []) for c in categories if candidates.get(c)}
    results = {c: [] for c in categories}
    summaries = {c: None for c in categories}

    if categories_to_run:
        loader = ConfigLoader(_AGENTFLOW_DIR)
        loader.load()
        run_results, run_summaries = asyncio.run(
            _run_all_categories_and_close(
                categories_to_run, pages_by_number, loader, secrets, provider, model, cancel_event,
                app_config=app_config,
            )
        )
        results.update(run_results)
        summaries.update(run_summaries)

    return {"categories": results, "summaries": summaries}

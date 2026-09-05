"""SPEC-206 §2.5/§2.8: the agent-dispatch layer -- router config, agent
construction, transcript assembly, and now real dispatch (CTX-206.6) --
plus the `SourceRef` validation model (§2.3, CTX-206.4), which has no
dependency on the router/agent layer and every assistant turn needs.

Deliberately does NOT implement one of the eight real `SourceRef` kinds
SPEC-206 §2.3 names:

*   `"check_finding"` -- ERC/DRC results (`kicad.check_schematic`/
    `kicad.check_board`) are live, on-demand calls, never persisted with
    a stable `finding_id`. A `check_finding` reference can only ever be
    validated against the SAME `chat.send` call's own fresh tool
    results (SPEC-206 §2.5), not a disk lookup this module can perform
    in isolation.

Wired into `_RESOLVERS` as a real, named gap (mapped to a resolver that
always returns `False`) rather than silently omitted --
`resolve_source_ref` treats an unresolvable-but-well-formed ref and a
not-yet-supported kind identically, per SPEC-206 §2.3's own contract
that an unresolved reference is dropped, never repaired. `"note"` used
to be deferred the same way, until `promote_turn` (CTX-206.8, SPEC-206
§2.7) gave it a real note record to resolve against -- `_resolve_note`
below is that real resolver.
"""
import asyncio
import json
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone

from agentflow import AgentExecutor, ConfigLoader, RouterEngine
from agentflow.types import Message, Role

import agent_roles
import kicad_cli
import kicad_project
try:  # optional the same way daemon.py treats it -- a board reader that
    # fails to import must not take the whole chat surface down with it.
    import kicad_board
except Exception:  # noqa: BLE001
    kicad_board = None
try:  # same treatment: SPEC-113's checks are additive to every area
    import structural_checks
except Exception:  # noqa: BLE001
    structural_checks = None
import library_store
import llm_providers
import tool_registry

logger = logging.getLogger(__name__)

_AGENTFLOW_DIR = os.path.join(os.path.dirname(__file__), "agentflow")

# SPEC-318 §2.3's own five real areas -- kept as the single source of
# truth for the "hard error, never an LLM guess" requirement (SPEC-206
# §2.5), checked here before router.prompt.md is even consulted; its own
# `llmFallback: false` is the second, belt-and-braces layer of the same
# guarantee, not the only one.
_KNOWN_AREAS = ("overview", "components", "schematic", "pcb", "enclosure")


def _resolve_datasheet_page(ref: dict) -> bool:
    """Deliberately does not re-open or re-parse the cached PDF to check
    `page` against a real page count -- the citation-time validator
    (`datasheet_guidance._make_validate_handler`) already checked the
    page was real when the reference was first created. A `content_hash`
    match here proves the cached file is byte-identical to what was
    cited then, so whatever was true about its pages then is still true
    now; a mismatch means the datasheet was regenerated and the old page
    number may have moved, which this check catches without needing to
    know anything about page counts itself."""
    part_id = ref.get("part_id")
    content_hash = ref.get("content_hash")
    if not part_id or not isinstance(ref.get("page"), int) or not content_hash:
        return False
    path = library_store.datasheet_cache_path(part_id)
    if not os.path.isfile(path):
        return False
    return library_store.content_hash_of_file(path) == content_hash


def _resolve_guidance_item(ref: dict) -> bool:
    part_id = ref.get("part_id")
    category = ref.get("category")
    quote = ref.get("quote")
    content_hash = ref.get("content_hash")
    if not (part_id and category and quote and content_hash):
        return False
    try:
        part = library_store.load_part(part_id)
    except OSError:
        return False
    guidance = part.get("design_guidance")
    if not guidance or guidance.get("content_hash") != content_hash:
        return False
    items = guidance.get("categories", {}).get(category, [])
    return any(item.get("quote") == quote for item in items)


def _resolve_connection_guidance(ref: dict) -> bool:
    part_id = ref.get("part_id")
    pin_number = ref.get("pin_number")
    if not part_id or not pin_number:
        return False
    try:
        part = library_store.load_part(part_id)
    except OSError:
        return False
    guidance = part.get("connection_guidance")
    if not guidance:
        return False
    return any(
        str(entry.get("pin_number")) == str(pin_number) for entry in guidance.get("pin_guidance", [])
    )


def _resolve_part_field(ref: dict) -> bool:
    part_id = ref.get("part_id")
    field = ref.get("field")
    if not part_id or not field:
        return False
    try:
        part = library_store.load_part(part_id)
    except OSError:
        return False
    return field in part


def _resolve_chat_turn(ref: dict) -> bool:
    scope = ref.get("scope")
    scope_id = ref.get("scope_id")
    turn_id = ref.get("turn_id")
    if not scope or not scope_id or not turn_id:
        return False
    try:
        turns = library_store.load_thread(scope, scope_id)
    except library_store.SchemaValidationError:
        return False
    return any(turn.get("turn_id") == turn_id for turn in turns)


def _resolve_project_intent(ref: dict) -> bool:
    project_name = ref.get("project_name")
    if not project_name:
        return False
    try:
        project = library_store.load_project(project_name)
    except (OSError, library_store.ProjectDirectoryMissingError):
        return False
    return bool(project.get("intent"))


def _resolve_note(ref: dict) -> bool:
    """CTX-206.8 (SPEC-206 §2.7): a real note only ever lives on a Part
    or a Project (`promote_turn`'s own two real targets) -- a `scope`
    outside those two never resolves, the same fail-closed shape every
    other resolver here uses for a malformed/unsupported input."""
    scope = ref.get("scope")
    scope_id = ref.get("scope_id")
    note_id = ref.get("note_id")
    if not scope_id or not note_id:
        return False
    try:
        if scope == "part":
            record = library_store.load_part(scope_id)
        elif scope == "project":
            record = library_store.load_project(scope_id)
        else:
            return False
    except (OSError, library_store.ProjectDirectoryMissingError):
        return False
    return any(n.get("note_id") == note_id for n in (record.get("notes") or []))


class ReviewFormatError(Exception):
    """A review response with no findings block at all.

    Deliberately an error rather than an empty result: an empty list is a
    real, honest answer ("nothing worth flagging"), and a missing block is
    the model failing to answer in the required format. Collapsing the two
    told a user their board was fine when it had not been assessed."""


def _resolve_deferred(ref: dict) -> bool:
    return False


def _resolve_check_finding(ref: dict) -> bool:
    """A citation of an ERC/DRC finding this request itself produced.

    Stubbed to `_resolve_deferred` (always False) since SPEC-206, for a good
    reason at the time: the check block was read from stored results that
    nothing ever wrote, so there was never a real finding to cite. Every
    `check_finding` ref was therefore dropped, `sources` came back empty, and
    the UI fell through to "General engineering practice -- not from this
    area's own data" beneath a finding that opened "DRC detected 2 missing
    connections". Reported directly.

    Now that `_check_status_note` runs the check, a citation resolves when the
    file it names is still on disk. That is a deliberately modest claim: it
    says the check had a real subject, not that the finding is still present
    -- the board may have been fixed since, which is exactly why nothing here
    is cached. `source_path` is written by us, never by the model, so a
    citation cannot point at a file the check never read.
    """
    if not isinstance(ref, dict):
        return False
    path = ref.get("source_path")
    return isinstance(path, str) and bool(path) and os.path.exists(path)


_RESOLVERS = {
    "datasheet_page": _resolve_datasheet_page,
    "guidance_item": _resolve_guidance_item,
    "connection_guidance": _resolve_connection_guidance,
    "part_field": _resolve_part_field,
    "chat_turn": _resolve_chat_turn,
    "project_intent": _resolve_project_intent,
    "check_finding": _resolve_check_finding,
    "note": _resolve_note,
}


def resolve_source_ref(ref: dict) -> bool:
    """SPEC-206 §2.3: `True` if `ref` resolves to a real, current record.
    A reference of an unknown `kind`, a malformed one missing a required
    field, or one that resolves but stale (a `content_hash` mismatch)
    all return `False` -- the contract does not distinguish them,
    matching `datasheet_guidance`'s own "drop, never repair" discipline
    for guidance citations, extended here to chat."""
    if not isinstance(ref, dict):
        return False
    resolver = _RESOLVERS.get(ref.get("kind"))
    if resolver is None:
        return False
    try:
        return bool(resolver(ref))
    except (TypeError, AttributeError):
        return False


def validate_source_refs(refs: list) -> tuple:
    """SPEC-206 §2.3: an assistant turn's real sources filtered down to
    only the ones that resolve, plus how many did not. `sources_dropped`
    is a real, counted fact -- an answer that arrives claiming support
    and ends with `sources: []` and `sources_dropped: 3` is materially
    different from one that never claimed any, and the UI must be able
    to say so, not silently render nothing."""
    if not isinstance(refs, list):
        return [], 0
    resolved = [ref for ref in refs if resolve_source_ref(ref)]
    return resolved, len(refs) - len(resolved)


# --- Agent dispatch (CTX-206.6, SPEC-206 §2.5) ---------------------------


class UnknownChatAreaError(Exception):
    """A hard error for an area outside the five real SPEC-318 areas --
    never an LLM guess (SPEC-206 §2.5's own explicit requirement).
    Checked here, before the router is even consulted;
    `router.prompt.md`'s own `llmFallback: false` enforces the same
    guarantee at the routing layer as a second, defensive line -- a
    well-formed caller never reaches it in practice."""


def _load_referenced_parts(project: dict) -> list:
    """Every real Part a Project references, loaded fresh -- skips a
    part_id that fails to load (e.g. removed from the library after
    being referenced) rather than failing the whole context assembly
    over one stale reference."""
    parts = []
    for part_id in project.get("parts", []):
        try:
            parts.append(library_store.load_part(part_id))
        except OSError:
            continue
    return parts


def _part_identity(part: dict) -> dict:
    return {"part_id": part["part_id"], "manufacturer": part.get("manufacturer"), "package": part.get("package")}


def _part_guidance_summary(part: dict) -> dict:
    """The real, already-generated guidance a chat agent is told it has
    up front (SPEC-318 §2.3) -- the persisted record as-is, `None`
    where nothing was ever generated (the same honest absence
    `_backfill_design_guidance`/`_backfill_connection_guidance` already
    preserve), never re-derived or re-summarized here."""
    return {
        **_part_identity(part),
        "pins": part.get("pins", []),
        "provenance": part.get("provenance", {}),
        "design_guidance": part.get("design_guidance"),
        "connection_guidance": part.get("connection_guidance"),
    }


_CHECK_AREA_LABELS = {"schematic": "ERC", "pcb": "DRC"}
# This note is read straight into an LLM context window; a real board can
# produce hundreds of findings. The COUNTS above stay exact either way.
_MAX_LIVE_FINDINGS = 25


#: How many components of a real design go into the agent's context. A big
#: board has hundreds; the point is to make every reference designator the
#: check block mentions resolvable, not to ship the whole BOM.
_MAX_CONTEXT_COMPONENTS = 80

#: The two shapes KiCad writes a reference designator in, inside a finding's
#: own item description. Schematic: `Symbol A1 Pin 8 [VIN, Power input, Line]`.
#: Board: `PTH pad 2 [Net-(U2-THRES)] of U2`. Anything else (a bare track, a
#: board-edge violation) legitimately names no component and must stay unnamed.
_SYMBOL_REF_PATTERN = re.compile(r"^Symbol (\S+) ")
_OF_REF_PATTERN = re.compile(r" of (\S+)$")


def reference_designator_in(description: str) -> str | None:
    """The component a finding's location names, or None when it names none."""
    if not description:
        return None
    for pattern in (_SYMBOL_REF_PATTERN, _OF_REF_PATTERN):
        match = pattern.search(description)
        if match:
            return match.group(1)
    return None


def _finding_for_agent(finding: dict, components: dict | None = None) -> dict:
    """One check finding, keeping WHERE it is.

    `items` used to be dropped here on the grounds that it carried "KiCad's
    internal uuids, which mean nothing to a user". The uuids do not; the rest
    of each item very much does. A real one reads:

        {"description": "PTH pad 2 [Net-(U2-THRES)] of U2",
         "pos": {"x": 99.695, "y": 68.23}}

    -- which is the pad, the net, the component, and the millimetre position
    on the board. Dropping it left the agent able to say only that two
    connections were missing, never which two or where, and the maintainer
    reported exactly that: "we didn't even tell the user where to find the
    problems on the board."
    """
    shaped = {
        "severity": finding.get("severity"),
        "type": finding.get("type"),
        "description": finding.get("description"),
        "locations": [
            _location_for_agent(i, components or {})
            for i in (finding.get("items") or [])
            if isinstance(i, dict) and i.get("description")
        ],
    }
    # A finding computed from a different file than the area's own says so.
    # SPEC-113's checks read the schematic and are reported on the PCB tab too,
    # so a citation naming the board would be pointing at the wrong file.
    if finding.get("source_path"):
        shaped["source_path"] = finding["source_path"]
    return shaped


def _location_for_agent(item: dict, components: dict) -> dict:
    """One flagged item, with the real component it names attached.

    Without this the agent is told `Symbol A1 Pin 8 [VIN, Power input, Line]`
    and nothing whatsoever about what A1 is -- so it fills the gap from the
    only other thing in its context with pins, which on the maintainer's own
    tutorial project was an unrelated NE555 sitting in the library. The
    reported explanation opened "this is the power supply input pin on the
    NE555 timer chip" on a board whose A1 is an Arduino UNO. Every other
    detail in that sentence was correctly grounded; only the part's identity
    was invented, because it was the only fact not supplied.
    """
    location = {"description": item.get("description"), "pos_mm": item.get("pos")}
    reference = reference_designator_in(item.get("description") or "")
    if reference:
        location["reference"] = reference
        component = components.get(reference)
        location["component"] = component if component else (
            f"{reference} is not in this design's component list -- say so rather "
            "than guessing what it is."
        )
    return location


def _by_reference(components: list | None) -> dict:
    """Components keyed by reference designator, for finding annotation."""
    return {
        c["reference"]: c
        for c in (components or [])
        if c.get("reference")
    }


def _design_components(path: str, area: str) -> list:
    """Every component in the linked schematic or board, from the file.

    `SPEC-325` built this and the chat prompts were never told. Until now the
    review agent was handed ERC findings that name reference designators and
    no way at all to resolve them.

    Best-effort by design: a component list that cannot be read must not cost
    the user the check that can. The caller reports the absence rather than
    silently sending an empty design.
    """
    if area == "schematic":
        return [
            {
                "reference": c.get("reference"),
                "value": c.get("value"),
                "footprint": c.get("footprint"),
            }
            for c in kicad_cli.export_schematic_bom(path)
        ]
    if kicad_board is None:
        raise RuntimeError("reading a board requires kicad_board, which failed to import")
    return [
        {
            "reference": f.get("reference"),
            "value": f.get("value"),
            "footprint": f.get("footprint"),
        }
        for f in kicad_board.read_board_footprints(path)
    ]


def _structural_findings(schematic_path: str | None) -> list:
    """SPEC-113's checks, as findings, or [] when they cannot run.

    Reported on the PCB tab as well as the Schematic tab. A symbol and its
    footprint disagreeing is a fact about the design, and the person who runs
    only the board check before ordering is exactly the person this exists for.
    Each finding carries its own `source_path`, because it was read from the
    schematic whichever tab asked for it.

    Never fatal: a schematic this cannot parse must not cost the user their
    ERC or DRC results.
    """
    if structural_checks is None or not schematic_path:
        return []
    try:
        findings = structural_checks.check_pin_counts(schematic_path)
    except Exception as exc:  # noqa: BLE001 -- additive; never breaks the check
        logger.warning("structural checks failed for %s: %s", schematic_path, exc)
        return []
    for finding in findings:
        finding["source_path"] = schematic_path
    return findings


def _check_status_note(project: dict, area: str) -> str:
    """Runs the real ERC/DRC now, rather than reporting a stored one.

    This used to read `Project.last_results[area]`, which nothing but the
    enclosure ever wrote -- so the review agent was handed "No DRC check
    result is available this session" on boards with real errors, and found
    nothing because it was shown nothing.

    Persisting the result and warning about its age was the obvious repair
    and is the wrong one. `kicad-cli` reads a **closed** `.kicad_sch` /
    `.kicad_pcb` (SPEC-325 §2.2) in about two seconds, so there is nothing
    to cache: a stored finding can be stale in ways this app cannot detect
    -- the user can run DRC in KiCad, fix everything, and never tell us --
    while a finding computed now cannot. The maintainer put it plainly:
    re-running the review would "still just show cached and potentially
    stale results", and even "nothing stood out" is misleading when no
    check was ever run.

    The one honest caveat left is that this reads the FILE, so an editor
    holding unsaved changes will differ. Said explicitly in the note rather
    than implied.

    Every failure is reported as itself, never as a clean board: no linked
    project, no such file, no `kicad-cli` installed. "We could not check"
    and "we checked and it is fine" must never look the same to the agent.
    """
    label = _CHECK_AREA_LABELS[area]
    pro_path = project.get("kicad_project_path")
    if not pro_path:
        return (
            f"No {label} check could be run: this project has no KiCad project linked, "
            "so there is no file to check. This is NOT a clean result."
        )

    try:
        files = kicad_project.resolve_project(pro_path)
        path = files["schematic_path"] if area == "schematic" else files["pcb_path"]
        if not path:
            return (
                f"No {label} check could be run: the linked KiCad project has no "
                f"{'schematic' if area == 'schematic' else 'board'} file yet. "
                "This is NOT a clean result."
            )

        try:
            components = _design_components(path, area)
        except Exception as exc:  # noqa: BLE001 -- reported, never fatal to the check
            logger.warning("component list unavailable for %s: %s", path, exc)
            components = None

        structural = _structural_findings(files.get("schematic_path"))

        if area == "schematic":
            report = kicad_cli.run_erc(path)
            findings = [v for sheet in report["sheets"] for v in sheet["violations"]]
            counts = {"violation_count": len(findings)}
        else:
            report = kicad_cli.run_drc(path, schematic_parity=True)
            findings = [
                *report["violations"],
                *report.get("unconnected_items", []),
                *report.get("schematic_parity", []),
            ]
            counts = {
                "violation_count": len(report["violations"]),
                "unconnected_count": len(report.get("unconnected_items", [])),
                "parity_count": len(report.get("schematic_parity", [])),
            }
    except Exception as exc:  # noqa: BLE001 -- reported, never mistaken for clean
        logger.warning("live %s check failed for %s: %s", label, pro_path, exc)
        return (
            f"The {label} check could not be run ({exc}). This is NOT a clean result -- "
            "say so rather than implying the design passed."
        )

    return json.dumps(
        {
            "check": label,
            "ran_now": True,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source_path": path,
            "read_from": (
                "the file on disk -- an editor holding unsaved changes will differ"
            ),
            **counts,
            "components": (
                [c for c in components[:_MAX_CONTEXT_COMPONENTS]]
                if components is not None
                else "The component list could not be read. Do not guess what any "
                     "reference designator refers to."
            ),
            "components_omitted": (
                max(0, len(components) - _MAX_CONTEXT_COMPONENTS) if components is not None else 0
            ),
            "structural_count": len(structural),
            "structural_note": (
                "Findings of type copperplane.* are this app's own, computed from the "
                "schematic and its footprints. KiCad's ERC and DRC do not report them and "
                "never will -- say where a finding came from rather than implying KiCad "
                "raised it."
            ),
            # Structural findings are appended after the cap, not merged before
            # it: a board with hundreds of DRC violations must not push out the
            # findings nothing else in the toolchain reports.
            "findings": [
                _finding_for_agent(f, _by_reference(components))
                for f in findings[:_MAX_LIVE_FINDINGS]
            ] + [
                _finding_for_agent(f, _by_reference(components)) for f in structural
            ],
            "findings_omitted": max(0, len(findings) - _MAX_LIVE_FINDINGS),
            # Which checks KiCad did not run at all. A disabled check makes a
            # board look clean for a reason that is invisible everywhere else,
            # and these settings are routinely inherited from whatever project
            # a user copied their template from.
            "ignored_checks": report.get("ignored_checks", []),
        },
        sort_keys=True,
    )


def _enclosure_fit_note(project: dict) -> dict:
    """What the parts on the board actually need, measured now.

    The enclosure agent used to get `kicad.get_component_heights`, which went
    through `kipy` and needed KiCad RUNNING; it was removed on 2026-09-02 after
    it starved the review of its tool rounds, leaving the agent with no
    physical board data at all. `SPEC-326`'s `component_envelopes` reads
    CLOSED files and returns better data than that tool ever had.

    Measured per request rather than read from `last_results`, for the same
    reason the ERC/DRC block is: a stored number goes stale the moment the user
    changes anything, and re-running the review would keep showing the old
    answer. The generated parameters are still read from storage -- they are a
    record of a real generate, not a measurement.

    Every failure is reported as itself. "We could not measure" and "it fits"
    must never look the same.
    """
    pro_path = project.get("kicad_project_path")
    if not pro_path:
        return {
            "measured": False,
            "reason": "No KiCad project is linked, so nothing about this board can be measured. "
                      "This is NOT a statement that anything fits.",
        }

    try:
        files = kicad_project.resolve_project(pro_path)
        board = files["pcb_path"] or files["schematic_path"]
        if not board:
            return {
                "measured": False,
                "reason": "The linked KiCad project has no board or schematic yet, so there is "
                          "nothing to measure. This is NOT a statement that anything fits.",
            }
        # Imported here, not at module scope: `daemon` imports this module, so
        # a top-level import would be circular. The measurement itself composes
        # kicad_board, kicad_bridge and freecad_bridge and belongs there --
        # re-implementing it here to avoid the cycle would be worse.
        import daemon

        envelopes = daemon.kicad_component_envelopes(
            sch_path=files["schematic_path"], pcb_path=files["pcb_path"],
            height_overrides=project.get("component_heights") or {},
        )
    except Exception as exc:  # noqa: BLE001 -- reported, never mistaken for a fit
        logger.warning("enclosure fit measurement failed for %s: %s", pro_path, exc)
        return {
            "measured": False,
            "reason": f"The board could not be measured ({exc}). This is NOT a statement that "
                      "anything fits.",
        }

    tallest = envelopes.get("tallest")
    return {
        "measured": True,
        "measured_from": envelopes.get("measured_from"),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "min_interior_height_mm": envelopes.get("min_interior_height_mm"),
        "tallest_component": tallest,
        "components_measured": envelopes.get("measured"),
        "components_with_supplied_height": envelopes.get("stated"),
        # SPEC-326 SS2.3: a component with no known height is NOT counted in the
        # minimum above, so the real one may be taller. Any fit claim made while
        # this is non-zero is provisional, and the agent is told so.
        "components_with_no_known_height": envelopes.get("unknown"),
        "note": (
            "Heights come from each footprint's own 3D model, or a height the user supplied. "
            "Components with no known height are not counted in the minimum, so the real "
            "minimum may be taller."
        ),
    }


def _assemble_context(area: str, scope: str, scope_id: str, project_name: str | None) -> str:
    """Builds the real, per-area context block SPEC-318 §2.3 describes
    each chat agent as already having up front -- prepended to the
    user's own message (not the system prompt, which stays the fixed
    persona/instructions from the `.prompt.md` body itself) so it is
    always fresh. `chat.send` is called fresh per turn rather than
    holding a live session, so re-assembling on every call is correct,
    not wasteful -- a stored history turn carries only its own raw
    text, never a copy of the context block that was true when it was
    asked; only the newest turn needs one."""
    if area == "components":
        part = library_store.load_part(scope_id)
        context = {"part": _part_guidance_summary(part)}
        if project_name:
            try:
                context["project_intent"] = library_store.load_project(project_name).get("intent")
            except (OSError, library_store.ProjectDirectoryMissingError):
                pass
        return json.dumps(context, sort_keys=True, default=str)

    real_project_name, _, _ = scope_id.partition(":")
    project = library_store.load_project(real_project_name)

    if area == "overview":
        context = {
            "project_intent": project.get("intent"),
            "last_results": project.get("last_results", {}),
            "export_history": project.get("export_history", []),
            "parts": [_part_identity(p) for p in _load_referenced_parts(project)],
        }
    elif area in _CHECK_AREA_LABELS:
        context = {
            "project_intent": project.get("intent"),
            "check_status": _check_status_note(project, area),
            # Named for what it actually is. As a bare `parts` key next to a
            # check block full of reference designators, this read as "the
            # components in this design" -- and the agent explained an ERC
            # finding about an Arduino's A1 as an NE555's pin 8, because an
            # NE555 was the only thing here with pins. These are Copperplane
            # library records the user attached to the project; some are on
            # the board, some are only being considered.
            "library_parts_attached_to_this_project": [
                _part_guidance_summary(p) for p in _load_referenced_parts(project)
            ],
            "library_parts_note": (
                "These are Copperplane library records the user attached to this "
                "project. A part appearing here is NOT evidence it is in the "
                "schematic or on the board. The design's real components are in "
                "check_status.components -- resolve every reference designator "
                "against that list and nothing else."
            ),
        }
    else:  # enclosure
        context = {
            "project_intent": project.get("intent"),
            # A record of a real generate, so genuinely useful -- but written
            # when the enclosure was generated, which can lag the form the user
            # is looking at. Said plainly rather than implied.
            "enclosure_parameters": (project.get("last_results") or {}).get("enclosure"),
            "fit": _enclosure_fit_note(project),
        }
    return json.dumps(context, sort_keys=True, default=str)


_CITATIONS_PATTERN = re.compile(r"<<<CITATIONS>>>(.*?)<<<END_CITATIONS>>>", re.DOTALL)
# CTX-319.1, SPEC-319 §2.1: the review-response counterpart to
# _CITATIONS_PATTERN above -- a separate trailing block, never present
# in a real chat response, so running both extractors against either
# kind of response is always safe (each simply finds no match in the
# other's own text).
_FINDINGS_PATTERN = re.compile(r"<<<FINDINGS>>>(.*?)<<<END_FINDINGS>>>", re.DOTALL)


def _extract_self_reported(text: str) -> tuple:
    """SPEC-206 §2.3's "both, layered" design (confirmed with the user):
    the model self-reports every `SourceRef` kind that cites
    pre-assembled context it was simply given up front
    (`guidance_item`, `connection_guidance`, `part_field`,
    `project_intent`) inside a structured trailing block -- chat.send
    has no other way to know which parts of that context the model
    actually relied on. `datasheet_page` refs are never self-reported;
    they're derived mechanically instead (`_mechanical_source_refs`
    below), the one kind that's a genuine fresh tool call within the
    turn rather than a citation of context handed over up front.

    Returns `(visible_text, self_reported_sources, general_practice)`.
    The citation block is always stripped from what the user sees. A
    missing or malformed block is never a raised error -- this is model
    output, and "the model forgot to cite" is a different failure from
    "the daemon is broken" -- it degrades to `general_practice=True`,
    the conservative, honest default when nothing can be confirmed as
    grounded."""
    match = _CITATIONS_PATTERN.search(text)
    if not match:
        return text.strip(), [], True
    visible = (text[: match.start()] + text[match.end() :]).strip()
    try:
        payload = json.loads(match.group(1).strip())
    except (json.JSONDecodeError, TypeError):
        return visible, [], True
    if not isinstance(payload, dict):
        return visible, [], True
    sources = payload.get("sources")
    if not isinstance(sources, list):
        sources = []
    return visible, sources, bool(payload.get("general_practice", True))


def _findings_json_without_delimiters(text: str):
    """The findings JSON when the model omitted the `<<<FINDINGS>>>` markers.

    Captured from a real run rather than guessed at: the model returned

        {"severity": "warning", "title": "...", "detail": "...", ...}

    -- the right content, correctly shaped, with no wrapper. Discarding that
    threw away a real answer over its packaging, and the user saw the raw
    check output instead of the explanation the model had actually written.

    Custom sentinels are a lot to ask of a model that is already producing
    JSON. Being tolerant here does not weaken the honesty rule that matters:
    text that yields no findings JSON at all is still not a clean board, and
    still falls back to the check's own findings.

    Returns the JSON substring, or `None` when there is none to read.
    """
    stripped = text.strip()
    if not stripped:
        return None

    # Whole response is the JSON, which is the common case.
    if stripped[0] in "[{" and stripped[-1] in "]}":
        return stripped

    # Otherwise take the outermost array, then the outermost object, that the
    # response contains -- a model that adds a sentence either side of its
    # JSON has still answered.
    for opener, closer in (("[", "]"), ("{", "}")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start != -1 and end > start:
            return stripped[start:end + 1]
    return None


def _extract_findings(text: str) -> list:
    """CTX-319.1, SPEC-319 §2.1/§2.3: parses a review response's own
    trailing `<<<FINDINGS>>>[...]<<<END_FINDINGS>>>` block -- a JSON
    array, each entry a draft `ReviewFinding` still missing `sources`/
    `area` (filled in by `review()` below, per finding, the same way
    `_enrich_source_ref` already fills in what a chat turn's own model
    output cannot supply itself). Mirrors `_extract_self_reported`'s own
    resilience contract exactly: a missing or malformed block is never a
    raised error, only an empty list -- "the model didn't return the
    format" is a different failure from "the daemon is broken." A
    malformed individual entry (missing `severity`/`title`/`detail`, or
    an unrecognized `severity`) is dropped rather than shown broken;
    `review()` does that per-entry validation, this function only
    guarantees every returned item is at least a dict."""
    match = _FINDINGS_PATTERN.search(text)
    raw = match.group(1).strip() if match else _findings_json_without_delimiters(text)
    if raw is None:
        return []
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    # A single finding object, unwrapped, is what a model actually returned
    # when asked for an array -- read as a one-item list rather than dropped.
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []
    return [f for f in payload if isinstance(f, dict)]


def _enrich_source_ref(ref) -> dict:
    """Fills in the one field the model cannot compute itself --
    `guidance_item`'s real `content_hash` -- from the Part's own
    current `design_guidance` record. Every other self-reportable kind
    (`connection_guidance`, `part_field`, `project_intent`) needs no
    enrichment; the model already has every field its own `SourceRef`
    shape requires, straight from the context it was given (SPEC-206
    §2.3)."""
    if not isinstance(ref, dict) or ref.get("kind") != "guidance_item":
        return ref
    part_id = ref.get("part_id")
    if not part_id:
        return ref
    try:
        part = library_store.load_part(part_id)
    except OSError:
        return ref
    content_hash = (part.get("design_guidance") or {}).get("content_hash")
    return {**ref, "content_hash": content_hash} if content_hash else ref


def _mechanical_source_refs(tool_calls: list) -> list:
    """SPEC-206 §2.3's `datasheet_page` kind, derived mechanically from
    real `datasheet.read_pages` tool calls -- the one `SourceRef` kind
    that's a genuine fresh tool call within this turn, not a citation of
    context assembled up front. Never trusts the model's own account of
    what it read; only a real, observed tool result produces one of these.

    `tool_calls` is `NodeOutput.metadata["tool_calls"]` as surfaced
    directly by `AgentExecutor.run()` (real, upstream `agentflow>=0.10.0`
    capability -- confirmed against the installed source; this used to
    require subscribing an `EventBus` to `TOOL_CALLED`/`TOOL_RESULT`
    before calling `run()`, since no earlier version surfaced tool calls
    on the return value itself). Each entry's `result` is the tool's
    plain JSON string return value, not a pre-parsed dict -- `tool_
    registry._wrap_route` always returns `json.dumps(result)`, so this
    re-parses it rather than needing a second, richer channel for the
    same data."""
    refs = []
    for call in tool_calls:
        if call.get("name") != "datasheet.read_pages" or call.get("is_error"):
            continue
        try:
            raw = json.loads(call.get("result") or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(raw, dict):
            continue
        content_hash = raw.get("content_hash")
        part_id = (call.get("input") or {}).get("part_id")
        if not content_hash or not part_id:
            continue
        for page in raw.get("pages", []):
            page_number = page.get("page")
            if isinstance(page_number, int):
                refs.append({
                    "kind": "datasheet_page", "part_id": part_id,
                    "page": page_number, "content_hash": content_hash,
                })
    return refs


def _history_as_messages(scope: str, scope_id: str) -> list:
    turns = library_store.load_thread(scope, scope_id)
    return [
        Message(role=Role.USER if t.get("role") == "user" else Role.ASSISTANT, content=t.get("content", ""))
        for t in turns
    ]


async def _dispatch(
    area: str, scope: str, scope_id: str, project_name: str | None, message: str,
    history: list, secrets: dict, provider: str | None, model: str | None,
    tools: "tool_registry.ToolRegistry | None" = None, config: dict | None = None,
) -> dict:
    """`tools` (CTX-319.1, SPEC-319 §2.1/§2.2): defaults to the full
    registry -- `send()`'s own call site passes nothing, unchanged from
    before this parameter existed. `review()` passes a registry with
    every `CONFIRMATION_REQUIRED_TOOLS` member left out, since a review
    has no confirmation UI to ever complete that exchange (SPEC-319
    §2.2) -- not because an unconfirmed call would otherwise do
    anything: `tool_registry._wrap_route`'s own execution-layer check
    already refuses to run one for any caller, chat included.

    `config` (CTX-208.2, SPEC-208 §2.3.2): `daemon.CONFIG` itself, passed
    through unread except by `llm_providers.resolve()` -- this module
    still has no dependency on it beyond that one call, matching
    `llm_providers`'s own existing rule."""
    loader = ConfigLoader(_AGENTFLOW_DIR)
    loader.load()
    router_config, router_prompt = loader.router
    router = RouterEngine(router_config, router_prompt=router_prompt)
    routing = await router.route("", context={"area": area})

    agent_config, prompt_body = loader.get_agent(routing.target)
    agent_role = agent_roles.load_agent_roles(os.path.join(_AGENTFLOW_DIR, "agents")).get(routing.target, {})
    # SPEC-208 §2.6: the override-computation this used to do itself is
    # now `llm_providers.resolve()`'s job, consolidated with
    # `component_pipeline._build_agent_executor`'s identical duplicate.
    # `model_role` (CTX-208.2) routes through `config`'s provider_roles
    # binding when no explicit provider/model override is given.
    provider_client, resolved_provider, resolved_model = llm_providers.resolve(
        agent_config.provider, agent_config.model, secrets, provider=provider, model=model,
        config=config, model_role=agent_role.get("model_role"),
        agent_name=routing.target, requires=agent_role.get("requires"),
    )
    # SPEC-209 §2.1: the record's vendor params ride on AgentConfig, which is
    # AgentFlow 0.11.0's own per-agent channel for them -- so this repo adds no
    # second mechanism for something the framework already carries.
    agent_config = agent_config.model_copy(update={
        "provider": resolved_provider,
        "model": resolved_model,
        "params": llm_providers.record_params(config, resolved_provider),
    })

    executor = AgentExecutor(
        config=agent_config, prompt_body=prompt_body, llm=provider_client,
        tools=tools if tools is not None else tool_registry.build_tool_registry(),
    )

    context_block = _assemble_context(area, scope, scope_id, project_name)
    full_message = f"Context:\n{context_block}\n\nUser message:\n{message}"

    try:
        output = await executor.run(message=full_message, history=history)
    finally:
        await llm_providers._close_provider_client(provider_client)

    tool_calls_raw = output.metadata.get("tool_calls", [])

    visible_text, self_reported, general_practice = _extract_self_reported(output.text)
    enriched = [_enrich_source_ref(ref) for ref in self_reported]
    resolved, dropped = validate_source_refs(_mechanical_source_refs(tool_calls_raw) + enriched)

    tool_calls = [
        {"name": tc.get("name"), "input": tc.get("input", {}), "result_digest": (tc.get("result") or "")[:200]}
        for tc in tool_calls_raw
    ]

    return {
        "agent": routing.target,
        "text": visible_text,
        "sources": resolved,
        "sources_dropped": dropped,
        "general_practice": general_practice,
        "tool_calls": tool_calls,
        # CTX-319.1: the untruncated, unparsed tool-call list -- review()
        # needs this (not the digest-truncated `tool_calls` above) to
        # feed `_mechanical_source_refs`, which re-parses each call's own
        # full JSON `result` itself.
        "tool_calls_raw": tool_calls_raw,
        "provenance": {"provider": agent_config.provider, "model": agent_config.model},
    }


def _make_turn(
    role: str, content: str, agent: str | None = None, sources: list | None = None,
    sources_dropped: int = 0, general_practice: bool = False, tool_calls: list | None = None,
    provenance: dict | None = None,
) -> dict:
    return {
        "turn_id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "sources": sources or [],
        "sources_dropped": sources_dropped,
        "general_practice": general_practice,
        "tool_calls": tool_calls or [],
        "provenance": provenance,
        "promoted_note_id": None,
    }


def send(
    scope: str, scope_id: str, area: str, message: str, project_name: str | None = None,
    secrets: dict | None = None, provider: str | None = None, model: str | None = None,
    config: dict | None = None,
) -> dict:
    """The real `chat.send` route body (SPEC-206 §2.5): appends the
    user turn, dispatches to the routed agent with this thread's real
    prior history, validates every source the turn claims (mechanical +
    self-reported, per this module's own citation functions above),
    appends the assistant turn, and returns it. Synchronous wrapper
    around the real async dispatch, matching `component_pipeline.py`'s
    own `asyncio.run(...)` precedent for every single-shot agent call
    already in this codebase.

    Deliberately does not thread a `cancel_event` through, despite
    SPEC-206 §2.5's own text naming it -- verified directly against
    every other single-shot agent-call route already in `daemon.py`
    (`kicad.generate_connection_guidance`, `kicad.suggest_footprint_
    query`, `kicad.generate_component`): none of them do either, only
    the genuinely multi-call routes (`datasheet.generate_guidance`,
    `freecad.generate_enclosure`) do, since those have a real, natural
    per-item checkpoint a single agent turn's own internal tool-loop
    does not."""
    if area not in _KNOWN_AREAS:
        raise UnknownChatAreaError(f"'{area}' is not a real chat area. Expected one of {', '.join(_KNOWN_AREAS)}.")
    secrets = secrets or {}

    history = _history_as_messages(scope, scope_id)

    user_turn = _make_turn(role="user", content=message)
    library_store.append_thread_turn(scope, scope_id, user_turn)

    result = asyncio.run(
        _dispatch(area, scope, scope_id, project_name, message, history, secrets, provider, model, config=config)
    )

    assistant_turn = _make_turn(
        role="assistant", content=result["text"], agent=result["agent"],
        sources=result["sources"], sources_dropped=result["sources_dropped"],
        general_practice=result["general_practice"], tool_calls=result["tool_calls"],
        provenance=result["provenance"],
    )
    library_store.append_thread_turn(scope, scope_id, assistant_turn)
    return assistant_turn


# CTX-319.1, SPEC-319 §2.1: a single, area-agnostic instruction --
# per-area framing lives in each `chat_*.prompt.md`'s own new "Review
# format" section, matching the existing "Citation format" section's
# own per-agent-appropriate-subset convention, not a second prompt file
# per area.
# The message the model actually receives. It used to defer entirely -- "in
# the format described in your own instructions" -- to a system prompt that is
# now well over a hundred lines, with the format two thirds of the way down.
# Responses came back with no block at all. The requirement is stated here, in
# the request itself, because that is the text nearest the model's answer.
_REVIEW_PROMPT = (
    "Review this area for anything worth flagging -- a real risk, a gap, or a suggestion -- "
    "using only what you're actually grounded in.\n\n"
    "Every finding in the check block you were given is worth flagging: explain each one in "
    "plain language for a maker who does not know the abbreviations, and say where on the board "
    "it is, using that finding's own `locations`.\n\n"
    "Answer with ONLY this block and nothing else -- no preamble, no prose before or after:\n\n"
    "<<<FINDINGS>>>\n"
    '[{"severity": "info" | "suggestion" | "warning", "title": "...", "detail": "...", '
    '"sources": [...], "general_practice": true|false}]\n'
    "<<<END_FINDINGS>>>\n\n"
    "An empty array is a normal, honest result when nothing stands out -- but it is wrong if the "
    "check block listed anything. A reply without the block cannot be read at all."
)
_REVIEW_SEVERITIES = ("info", "suggestion", "warning")


_UNEXPLAINED_PREFIX = (
    "Reported by KiCad's own check. The plain-language explanation could not be "
    "generated this time, so this is the raw finding: "
)

#: SPEC-113's findings are not KiCad's, and the fallback used to say they were.
#: Attributing them to a checker that does not report them is the exact
#: confusion the spec exists to prevent, arriving through the back door.
_UNEXPLAINED_STRUCTURAL_PREFIX = (
    "Found by Copperplane, not by KiCad -- ERC and DRC do not report this. The "
    "plain-language explanation could not be generated this time, so this is the "
    "raw finding: "
)

#: Findings this app computed itself. Their `type` is namespaced so the source
#: is unambiguous without matching on wording.
_STRUCTURAL_TYPE_PREFIX = "copperplane."


def _findings_from_fit_alone(scope_id: str, project_name: str | None) -> list | None:
    """The enclosure's measured fit, as a finding, with no model prose.

    Same contract as `_findings_from_check_alone` one area over: the
    measurement is deterministic and has already run, so a model that answers
    unreadably should not cost the user the numbers.

    It matters more here than it does for a board check. A weak model asked to
    review an enclosure will happily invent one -- a real captured response
    described "a USB connector with a height of 4.7mm" on a board that has no
    USB connector, alongside a wall thickness and standoff height that were
    never generated. A deterministic finding is not just a fallback; it is the
    floor under a surface whose whole purpose is to avoid confident advice from
    no data (SPEC-331 §1).
    """
    real_project_name, _, _ = scope_id.partition(":")
    try:
        project = library_store.load_project(project_name or real_project_name)
    except Exception:  # noqa: BLE001 -- nothing to fall back on
        return None

    fit = _enclosure_fit_note(project)
    if not fit.get("measured"):
        # Not a fit verdict, and not silently a clean one either.
        return [{
            "severity": "warning",
            "title": "The enclosure could not be checked",
            "detail": fit.get("reason", "The board could not be measured."),
            "sources": [],
            "general_practice": False,
            "area": "enclosure",
        }]

    needed = fit.get("min_interior_height_mm")
    unknown = fit.get("components_with_no_known_height") or 0
    params = (project.get("last_results") or {}).get("enclosure") or {}
    generated = params.get("height_mm")
    tallest = (fit.get("tallest_component") or {}).get("reference")

    findings = []
    if needed is not None and generated is not None:
        short = generated < needed
        findings.append({
            "severity": "warning" if short else "info",
            "title": ("The enclosure is shorter than the parts need"
                      if short else "The enclosure clears the parts that have been measured"),
            "detail": (
                f"The last enclosure generated is {generated}mm inside, and the tallest measured "
                f"part{f' ({tallest})' if tallest else ''} needs {needed}mm."
            ),
            "sources": [], "general_practice": False, "area": "enclosure",
        })
    elif needed is not None:
        findings.append({
            "severity": "info",
            "title": "No enclosure has been generated yet",
            "detail": (
                f"The parts on this board need at least {needed}mm of interior height"
                f"{f', set by {tallest}' if tallest else ''}. Generate an enclosure to compare."
            ),
            "sources": [], "general_practice": False, "area": "enclosure",
        })

    if unknown:
        # SPEC-326 SS2.3: unmeasured parts are not in the minimum, so no fit
        # claim above is final while this is non-zero.
        findings.append({
            "severity": "warning",
            "title": f"{unknown} component{'s' if unknown != 1 else ''} have no known height",
            "detail": (
                "They are not counted in the minimum above, so the real minimum may be taller. "
                "Supply a height for them on the Schematic tab to firm this up."
            ),
            "sources": [], "general_practice": False, "area": "enclosure",
        })
    return findings


def _findings_from_check_alone(area: str, scope_id: str, project_name: str | None) -> list | None:
    """The check's own findings, as review findings, with no model prose.

    Used when the model answers without its findings block. The check is
    deterministic and has already run; discarding it because the wording
    failed would make a user re-run everything to recover data this process is
    already holding.

    Returns `None` -- meaning "there is genuinely nothing to fall back on" --
    for an area with no check, or a project whose check could not run at all.
    That case is a real error and is raised by the caller, because it is the
    one where the board really has not been assessed.
    """
    if area == "enclosure":
        return _findings_from_fit_alone(scope_id, project_name)
    if area not in _CHECK_AREA_LABELS:
        return None

    real_project_name, _, _ = scope_id.partition(":")
    try:
        project = library_store.load_project(project_name or real_project_name)
    except Exception:  # noqa: BLE001 -- no project is a real "nothing to fall back on"
        return None

    note = _check_status_note(project, area)
    try:
        parsed = json.loads(note)
    except json.JSONDecodeError:
        # The note is prose, which is what `_check_status_note` returns when
        # the check could NOT be run. Not a clean result, and not a fallback.
        return None

    label = parsed.get("check", _CHECK_AREA_LABELS[area])
    findings = []
    for raw in parsed.get("findings", []):
        where = ", ".join(
            loc["description"] for loc in (raw.get("locations") or []) if loc.get("description")
        )
        findings.append({
            # KiCad's own severity vocabulary is not this app's: it says
            # "error"/"warning", the review surface says info/suggestion/
            # warning. Everything real maps to `warning` rather than being
            # invented into a finer grade we did not measure.
            "severity": "warning",
            "title": raw.get("description") or f"{label} finding",
            "detail": (
                _UNEXPLAINED_STRUCTURAL_PREFIX
                if str(raw.get("type") or "").startswith(_STRUCTURAL_TYPE_PREFIX)
                else _UNEXPLAINED_PREFIX
            ) + (
                f"{raw.get('description')}. Where: {where}." if where
                else f"{raw.get('description')}."
            ),
            "sources": validate_source_refs(
                [{
                    "kind": "check_finding",
                    "source_path": raw.get("source_path") or parsed.get("source_path"),
                }]
            )[0],
            # Straight from the check, so not general practice at all.
            "general_practice": False,
            "area": area,
        })
    return findings


def review(
    scope: str, scope_id: str, area: str, project_name: str | None = None,
    secrets: dict | None = None, provider: str | None = None, model: str | None = None,
    config: dict | None = None,
) -> list:
    """The real `chat.review` route body (CTX-319.1, SPEC-319 §2.1): the
    seam `SPEC-318` §2.5 defined but did not build. Reuses `_dispatch()`
    exactly as chat does -- same router, same per-area agent config,
    same context assembly -- with three real differences from `send()`:
    a fixed internal prompt instead of user text, no history (a review
    has no turn of its own to remember, and must not see an unrelated
    question's own framing), and a read-only-filtered tool registry
    (`CONFIRMATION_REQUIRED_TOOLS` excluded, SPEC-319 §2.2). Never
    touches the conversation thread at all -- a review is a flow step
    with a typed result, not a turn (`PRODUCT-PLAN.md` §3.3), so nothing
    here calls `append_thread_turn`."""
    if area not in _KNOWN_AREAS:
        raise UnknownChatAreaError(f"'{area}' is not a real chat area. Expected one of {', '.join(_KNOWN_AREAS)}.")
    secrets = secrets or {}

    read_only_tools = tool_registry.build_tool_registry(exclude=tool_registry.CONFIRMATION_REQUIRED_TOOLS)

    result = asyncio.run(_dispatch(
        area, scope, scope_id, project_name, _REVIEW_PROMPT, [], secrets, provider, model,
        tools=read_only_tools, config=config,
    ))

    # An absent FINDINGS block is NOT a clean review -- but it is also not a
    # reason to throw away the check. "Try again" was the first answer here and
    # it was the wrong one: the ERC/DRC is on demand and deterministic, it has
    # already run, and only the model's FORMATTING failed. Asking the user to
    # re-run costs another check plus another LLM call to recompute findings
    # that are sitting right here.
    #
    # So the findings survive the prose failing, exactly as they do in
    # `daemon.kicad_check_board`'s `_explain_or_report_plainly`: KiCad's output
    # is a fact about the user's board, the explanation of it is not. Only when
    # there is no check to fall back on -- an unlinked project, an area with no
    # check at all -- is this a real error.
    if _FINDINGS_PATTERN.search(result["text"]) is None \
            and _findings_json_without_delimiters(result["text"]) is None:
        # Why, when we can tell. agentflow returns ACCUMULATED TOOL RESULTS as
        # its text when an agent exhausts `max_tool_rounds` without answering,
        # so a tool that always fails silently turns into "no findings block".
        # That is exactly what happened here: `kicad.get_component_heights`
        # needs KiCad RUNNING, the PCB and Enclosure tabs stopped requiring it,
        # and the tool then failed on every call until the rounds ran out.
        # Logged rather than swallowed, so the next instance of this shape is
        # one grep away instead of another round of guessing.
        # A block that STARTED and never finished is truncation, not a model
        # ignoring the format -- worth saying separately, because the two have
        # opposite fixes (a bigger token budget vs. clearer instructions).
        if "<<<FINDINGS>>>" in result["text"]:
            logger.warning(
                "review(%s): findings block was started but never terminated -- the response was "
                "cut off at %s characters. This is a token-budget problem, not a format problem. "
                "Gemini charges a thinking model's reasoning against max_output_tokens, so an "
                "agent's max_tokens has to cover both.",
                area, len(result["text"]),
            )
        logger.warning(
            "review(%s) produced no findings block after %s tool call(s): %s",
            area,
            len(result.get("tool_calls_raw") or []),
            [tc.get("name") for tc in (result.get("tool_calls_raw") or [])],
        )
        # The model's ACTUAL words, written where they can be read. Three
        # rounds of fixing this have been guesses at what the model returned,
        # because the daemon's stderr goes to a parent process that has no
        # console when the app is launched from Finder. A log line nobody can
        # read is not a diagnostic.
        try:
            debug_path = os.path.join(tempfile.gettempdir(), "copperplane-review-debug.txt")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(f"area={area} scope_id={scope_id}\n")
                f.write(f"tool_calls={[tc.get('name') for tc in (result.get('tool_calls_raw') or [])]}\n")
                f.write(f"text_length={len(result.get('text') or '')}\n")
                f.write("--- raw model text ---\n")
                f.write(result.get("text") or "<empty>")
            logger.warning("review(%s): raw model text written to %s", area, debug_path)
        except OSError:
            pass
        fallback = _findings_from_check_alone(area, scope_id, project_name)
        if fallback is not None:
            return fallback
        raise ReviewFormatError(
            "The review came back without its findings block, so it could not be read. "
            "This is NOT a clean result -- the area has not been assessed."
        )

    findings = []
    for raw in _extract_findings(result["text"]):
        severity = raw.get("severity")
        title = raw.get("title")
        detail = raw.get("detail")
        if severity not in _REVIEW_SEVERITIES or not isinstance(title, str) or not title.strip() \
                or not isinstance(detail, str) or not detail.strip():
            # A malformed individual finding is dropped, not shown broken --
            # the same "model output can be wrong, the daemon staying up is
            # not the same claim as the model being right" contract
            # _extract_self_reported already applies to a whole turn.
            continue

        self_reported = raw.get("sources")
        if not isinstance(self_reported, list):
            self_reported = []
        enriched = [_enrich_source_ref(ref) for ref in self_reported]
        resolved, _dropped = validate_source_refs(
            _mechanical_source_refs(result["tool_calls_raw"]) + enriched
        )

        findings.append({
            "severity": severity,
            "title": title.strip(),
            "detail": detail.strip(),
            "sources": resolved,
            "general_practice": bool(raw.get("general_practice", True)),
            "area": area,
        })

    return findings


# --- Promotion (CTX-206.8, SPEC-206 §2.7) ---------------------------------


class UnknownPromotionTargetError(Exception):
    """`target_scope` must be `'part'` or `'project'` -- a note only
    ever lives on one of those two real record types."""


class TurnNotFoundError(Exception):
    """No turn with that `turn_id` exists in the named thread."""


class NotAssistantTurnError(Exception):
    """Only an assistant turn -- a settled answer -- can be promoted to
    a note; a user's own question isn't a conclusion to promote."""


def promote_turn(scope: str, scope_id: str, turn_id: str, target_scope: str, target_id: str) -> dict:
    """The chat.promote_turn route body (SPEC-206 §2.7): "the actual
    answer to answer consistency" -- moves a settled conclusion out of
    a transcript and into a durable record later conversations retrieve
    as fact (`context_index.py`'s own already-wired `note` chunk
    extractor picks it up the moment it's real). Copies the turn's own
    **already-validated** `sources` verbatim -- `chat.send` already ran
    them through `validate_source_refs` when the turn was first created;
    this never re-validates them a second time.

    Always user-initiated, never automatic (SPEC-206 §2.7's own explicit
    requirement) -- this function has no caller anywhere in this
    codebase except the real `chat.promote_turn` route a human action
    triggers; no agent code path calls this on its own judgement.

    Deliberately does not block re-promoting an already-promoted turn --
    a user might legitimately want the same settled answer to become a
    note on a second target (e.g. a Part and the Project it's used in);
    the decision of where a conclusion belongs is the user's, not
    something this function should second-guess by refusing a repeat."""
    if target_scope not in ("part", "project"):
        raise UnknownPromotionTargetError(
            f"'{target_scope}' is not a real promotion target ('part' or 'project')."
        )

    turns = library_store.load_thread(scope, scope_id)
    turn = next((t for t in turns if t.get("turn_id") == turn_id), None)
    if turn is None:
        raise TurnNotFoundError(f"No turn '{turn_id}' found in thread '{scope}:{scope_id}'.")
    if turn.get("role") != "assistant":
        raise NotAssistantTurnError("Only an assistant turn can be promoted to a note.")

    note = {
        "note_id": str(uuid.uuid4()),
        "text": turn.get("content", ""),
        "sources": turn.get("sources", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "origin": {"scope": scope, "scope_id": scope_id, "turn_id": turn_id},
        "provenance": turn.get("provenance"),
    }

    if target_scope == "part":
        library_store.add_part_note(target_id, note)
    else:
        library_store.add_project_note(target_id, note)

    library_store.update_thread_turn(scope, scope_id, turn_id, {"promoted_note_id": note["note_id"]})

    return note

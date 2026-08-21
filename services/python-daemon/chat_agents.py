"""SPEC-206 §2.5/§2.8: the agent-dispatch layer -- router config, agent
construction, transcript assembly -- lives here once it's built
(CTX-206.5+). This file starts with just the `SourceRef` validation model
(§2.3), since it has no dependency on the router/agent layer and every
future assistant turn needs it (CTX-206.4).

Deliberately does NOT implement two of the eight real `SourceRef` kinds
SPEC-206 §2.3 names:

*   `"check_finding"` -- ERC/DRC results (`kicad.check_schematic`/
    `kicad.check_board`) are live, on-demand calls, never persisted with
    a stable `finding_id`. A `check_finding` reference can only ever be
    validated against the SAME `chat.send` call's own fresh tool
    results (SPEC-206 §2.5), not a disk lookup this module can perform
    in isolation.
*   `"note"` -- `chat.promote_turn` (SPEC-206 §2.7) hasn't shipped yet;
    there is no note record anywhere to resolve against.

Both are wired into `_RESOLVERS` as real, named gaps (mapped to a
resolver that always returns `False`) rather than silently omitted --
`resolve_source_ref` treats an unresolvable-but-well-formed ref and a
not-yet-supported kind identically, per SPEC-206 §2.3's own contract
that an unresolved reference is dropped, never repaired. Adding a real
resolver for either later is a pure addition to `_RESOLVERS`, not a
rewrite of anything here.
"""
import os

import library_store


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


def _resolve_deferred(ref: dict) -> bool:
    return False


_RESOLVERS = {
    "datasheet_page": _resolve_datasheet_page,
    "guidance_item": _resolve_guidance_item,
    "connection_guidance": _resolve_connection_guidance,
    "part_field": _resolve_part_field,
    "chat_turn": _resolve_chat_turn,
    "project_intent": _resolve_project_intent,
    "check_finding": _resolve_deferred,
    "note": _resolve_deferred,
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

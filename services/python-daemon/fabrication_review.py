"""Check a board against the house it is actually going to be ordered from.

CTX-114.1 Phases 3 to 5, implementing `SPEC-114` sections 2.2, 2.3, 2.8 and the
`## 5. User & Interaction` contract.

The output this module exists to produce is the **before and after**: this board
passes with KiCad's defaults, and here is what it looks like against the house
you chose. On the example board that is 4 findings becoming 27, and every one of
the new ones is something a fab would build without comment rather than reject.

Two honesty rules run through all of it, both from measurement rather than
preference:

*   **Nothing is reported as checked unless it was.** A rule the project has set
    to `ignore` does not run (section 2.2, Limit 1), a field with no DRC
    constraint class cannot run (section 2.6), and a sidecar KiCad discarded did
    not run at all (Limit 2). Each of those is named in the result. The one
    output this feature may never produce is a confident summary drawn from
    rules that were never active.
*   **Nothing here says the board is good to order.** Section 3 is explicit. The
    result is "here is what your chosen house publishes, and here is where your
    board sits against it".

`stdout` is the JSON-RPC wire (`CLAUDE.md`), so nothing here ever prints.
"""

import json
import logging
import os

import capability_profile
import kicad_cli
import kicad_dru

logger = logging.getLogger(__name__)

# Severity ranking for the review, section 2.9's proposed ordering. "Would this
# have been built silently wrong" comes first, because it is the class the user
# had no way to know about and the entire argument for the feature. Rejection
# comes second: painful, but the fab tells them. Cosmetic last.
BUILT_SILENTLY_WRONG = "built_silently_wrong"
WOULD_BE_REJECTED = "would_be_rejected"
COSMETIC = "cosmetic"

_RANK = {BUILT_SILENTLY_WRONG: 0, WOULD_BE_REJECTED: 1, COSMETIC: 2}

# Which class each violation type falls into. Grouped from what a board house
# actually does with each, not from KiCad's own severity: KiCad reports an
# annular-ring shortfall and a silkscreen overlap at the same severity, and they
# are entirely different problems for the person paying for the board.
_OUTCOME_BY_TYPE = {
    # Built, shipped, and intermittently wrong. The whole pitch.
    "annular_width": BUILT_SILENTLY_WRONG,
    "hole_to_hole": BUILT_SILENTLY_WRONG,
    "connection_width": BUILT_SILENTLY_WRONG,
    "copper_edge_clearance": BUILT_SILENTLY_WRONG,
    "clearance": BUILT_SILENTLY_WRONG,
    "track_width": BUILT_SILENTLY_WRONG,
    # A fab would come back and ask, or refuse.
    "drill_out_of_range": WOULD_BE_REJECTED,
    "invalid_outline": WOULD_BE_REJECTED,
    "courtyards_overlap": WOULD_BE_REJECTED,
    # Comes back looking wrong, works fine.
    "silk_overlap": COSMETIC,
    "silk_over_copper": COSMETIC,
    "text_height": COSMETIC,
    "text_thickness": COSMETIC,
}


def classify(violation: dict) -> str:
    """What the board house would actually do with this finding.

    Unknown types rank as `WOULD_BE_REJECTED` rather than cosmetic: the safe
    direction for an unrecognised finding is to show it, not to bury it."""
    return _OUTCOME_BY_TYPE.get(violation.get("type"), WOULD_BE_REJECTED)


def _sort_key(violation: dict):
    return (_RANK[classify(violation)], violation.get("type", ""))


def rank_findings(violations) -> list:
    """Order findings so the ones that matter most are not buried.

    27 findings is reviewable but not self-organising (section 2.9)."""
    return sorted(violations, key=_sort_key)


def ignored_checks(pcb_path: str, report: dict = None) -> list:
    """Which checks the project has switched off, as `{key, description}` dicts.

    Limit 1 means the app cannot turn these back on from a sidecar, so the only
    honest move is to say which ones are off. Preferred source is the DRC
    report's own `ignored_checks`, which KiCad fills in and `SPEC-332` already
    renders; the `.kicad_pro` severity table is the fallback for a report that
    does not carry it.

    KiCad's own entries are `{"key": ..., "description": ...}`, confirmed by
    reading a real report rather than assumed -- the first version of this took
    them for plain strings and every caller downstream broke on a dict. The
    description is worth keeping: "Footprint has no courtyard defined" means
    something to the user in a way that `missing_courtyard` does not."""
    if report is not None and report.get("ignored_checks"):
        normalized = []
        for entry in report["ignored_checks"]:
            if isinstance(entry, dict):
                normalized.append({
                    "key": entry.get("key", ""),
                    "description": entry.get("description", ""),
                })
            else:
                normalized.append({"key": str(entry), "description": ""})
        return normalized

    pro_path = os.path.splitext(pcb_path)[0] + ".kicad_pro"
    if not os.path.exists(pro_path):
        return []
    try:
        with open(pro_path, encoding="utf-8") as handle:
            pro = json.load(handle)
    except (OSError, ValueError):
        logger.warning("Could not read %s to list ignored checks", pro_path)
        return []
    severities = (
        pro.get("board", {}).get("design_settings", {}).get("rule_severities", {}) or {}
    )
    return [
        {"key": name, "description": ""}
        for name, value in sorted(severities.items()) if value == "ignore"
    ]


# A constraint class and the check KiCad gates it under are NOT the same name,
# and assuming they were made this check silently miss four of ten fields. The
# mapping is `SPEC-114` section 2.1's own measured "violation type KiCad
# reported" column, cross-checked against the real `rule_severities` keys in the
# example project's `.kicad_pro`. `silk_clearance` maps to two keys, so a rule
# is only fully gated when every key it reports under is ignored.
_SEVERITY_KEYS_BY_CONSTRAINT = {
    "track_width": ("track_width",),
    "clearance": ("clearance",),
    "annular_width": ("annular_width",),
    "hole_size": ("drill_out_of_range",),
    "hole_to_hole": ("hole_to_hole",),
    "text_height": ("text_height",),
    "text_thickness": ("text_thickness",),
    "edge_clearance": ("copper_edge_clearance",),
    "silk_clearance": ("silk_overlap", "silk_over_copper"),
    "physical_clearance": ("clearance",),
    "courtyard_clearance": ("courtyards_overlap",),
    "connection_width": ("connection_width",),
}


def severity_keys_for(constraint: str) -> tuple:
    """The `.kicad_pro` severity keys a constraint class reports under."""
    return _SEVERITY_KEYS_BY_CONSTRAINT.get(constraint, (constraint,))


def _gated_rules(profile: dict, ignored: list) -> list:
    """Rules this profile sets that the project has switched off anyway.

    Reported rather than worked around: writing `.kicad_pro` to re-enable them
    is explicitly out of scope for v1 (section 2.2)."""
    gated = []
    ignored_keys = {entry["key"] for entry in ignored}
    for field in capability_profile.enforceable_fields(profile):
        constraint, _, rule_name = capability_profile.ENFORCEABLE_FIELDS[field]
        keys = severity_keys_for(constraint)
        blocked = [k for k in keys if k in ignored_keys]
        if not blocked:
            continue
        gated.append({
            "field": field,
            "constraint": constraint,
            "rule": rule_name,
            "ignored_keys": blocked,
            # A rule reporting under two keys with only one ignored still finds
            # some of its violations. Saying "partly" is more use than a flat
            # "off", which would overstate what was lost.
            "fully_gated": len(blocked) == len(keys),
        })
    return gated


def baseline(pcb_path: str) -> dict:
    """The board as KiCad checks it today, with no profile applied.

    Deliberately run with any generated sidecar moved aside: a leftover file
    from an earlier run would quietly make the "before" side of the comparison
    into another "after", and the whole proof surface would be a tautology."""
    sidecar = kicad_dru.sidecar_path_for(pcb_path)
    stashed = None
    if os.path.exists(sidecar) and kicad_dru.is_generated(sidecar):
        with open(sidecar, encoding="utf-8") as handle:
            stashed = handle.read()
        os.remove(sidecar)
    try:
        return kicad_cli.run_drc(pcb_path)
    finally:
        if stashed is not None:
            with open(sidecar, "w", encoding="utf-8") as handle:
                handle.write(stashed)


def review(pcb_path: str, profile: dict) -> dict:
    """The whole feature, end to end: before, after, and what was not checked.

    Raises `kicad_dru.SidecarDiscarded` when the generated rules did not take
    effect. That is deliberately not softened into a warning field -- a review
    built on inactive rules is worse than no review, because it reports a
    strengthened check while the board is unexamined."""
    capability_profile.assert_rules_are_generatable(profile)
    rules = capability_profile.to_rules(profile)

    before = baseline(pcb_path)
    applied = kicad_dru.write_and_verify(pcb_path, rules)
    after = applied["report"]

    ignored = ignored_checks(pcb_path, after)
    ours = [v for v in after.get("violations", []) if "rule '" in v.get("description", "")]

    counts = {}
    for violation in after.get("violations", []):
        counts[classify(violation)] = counts.get(classify(violation), 0) + 1

    return {
        "house_name": profile.get("house_name"),
        "verification_state": applied["state"],
        "before_count": len(before.get("violations", [])),
        "after_count": len(after.get("violations", [])),
        "findings": rank_findings(after.get("violations", [])),
        "profile_findings_count": len(ours),
        "counts_by_outcome": counts,
        "rule_hits": applied["hits"],
        # Everything below is the honesty surface. Each entry is something the
        # user might reasonably assume was checked and was not.
        "not_checked": {
            "ignored_by_project": ignored,
            "profile_rules_gated_off": _gated_rules(profile, ignored),
            "recorded_but_unenforceable": capability_profile.describe_unenforceable(profile),
        },
        "profile_is_stale": capability_profile.is_stale(profile),
        "unconfirmed_fields": capability_profile.unconfirmed_fields(profile),
    }


def summarize(result: dict) -> str:
    """One plain sentence for the review surface.

    Never says the board is good to order (section 3)."""
    before, after = result["before_count"], result["after_count"]
    house = result["house_name"]
    if result["verification_state"] == kicad_dru.INDETERMINATE:
        return (
            f"Could not confirm the {house} rules took effect on this board, so this result "
            f"should not be relied on."
        )
    delta = after - before
    if delta <= 0:
        return (
            f"Against {house}'s published capabilities, this board shows the same {after} "
            f"findings KiCad's own defaults do."
        )
    silent = result["counts_by_outcome"].get(BUILT_SILENTLY_WRONG, 0)
    tail = (
        f", {silent} of them the kind a fab would build without comment"
        if silent else ""
    )
    return (
        f"KiCad's defaults find {before} issues on this board. Against {house}'s published "
        f"capabilities it shows {after}{tail}."
    )

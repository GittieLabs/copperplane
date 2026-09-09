"""Fabrication capability profiles -- SPEC-114 section 2.6, CTX-114.1 Phase 2.

A `CapabilityProfile` records what a board house publishes it can build: minimum
trace width, minimum annular ring, minimum drill, and so on. It is a real record
with **per-field provenance** -- value, source URL, the date it was recorded, and
whether the user has confirmed it -- mirroring the provenance `library_store`
already enforces on `Part`, for the same two reasons: trust and attribution.

Three rules from the spec are enforced here rather than left as convention:

*   **Every field is optional, and an absent field produces no rule** (section
    2.6). A profile that does not name a minimum drill must not silently inherit
    a guess -- the app would be inventing a number the fab never published and
    then reporting findings against it.
*   **Mask dam and mask expansion are recorded but never enforced.** Section 2.1
    measured that they have no matching DRC constraint class at all, so they are
    displayed with their provenance and excluded from rule generation. Saying so
    beats dropping them quietly.
*   **A profile is a historical record, not a live feed** (section 2.9). When a
    house changes its published numbers, an existing project's profile still
    says what was actually checked. Nothing here updates itself.

`stdout` is the JSON-RPC wire (`CLAUDE.md`), so nothing here ever prints.
"""

import datetime
import logging

import kicad_dru

logger = logging.getLogger(__name__)


class ProfileValidationError(Exception):
    """A profile is malformed in a way that would produce dishonest output."""


# Each entry maps a profile field to the DRC constraint class that enforces it
# and the expression shape that class takes. Only classes SPEC-114 section 2.1
# actually measured firing appear here -- `kicad_dru` refuses the rest anyway,
# and duplicating an unconfirmed class here would just move the lie upstream.
ENFORCEABLE_FIELDS = {
    "min_track_width": ("track_width", "min", "min-track-width"),
    "min_clearance": ("clearance", "min", "min-clearance"),
    "min_annular_ring": ("annular_width", "min", "min-annular-ring"),
    "min_drill": ("hole_size", "min", "min-drill"),
    "min_hole_to_hole": ("hole_to_hole", "min", "min-hole-to-hole"),
    "min_silk_clearance": ("silk_clearance", "min", "min-silk-clearance"),
    "min_text_height": ("text_height", "min", "min-text-height"),
    "min_text_thickness": ("text_thickness", "min", "min-text-thickness"),
    "min_edge_clearance": ("edge_clearance", "min", "min-edge-clearance"),
    "min_courtyard_clearance": ("courtyard_clearance", "min", "min-courtyard-clearance"),
}

# Recorded, shown, and never checked. Section 2.6: no DRC constraint class
# exists for either, so a profile carrying them is telling the user something
# true that the review cannot act on. That gap is stated, not hidden.
RECORDED_ONLY_FIELDS = ("min_mask_dam", "min_mask_expansion")

# The build context the numbers belong to. Not constraints -- a 4-layer number
# quoted against a 2-layer order is the kind of mismatch that makes a profile
# worse than none.
CONTEXT_FIELDS = ("layer_count", "copper_weight_oz", "board_thickness_mm")

PROVENANCE_REQUIRED_KEYS = ("source_url", "recorded_on", "confirmed_by_user")

#: A template is a starting point, never a board house (`SPEC-342` section 2.5).
#: It names no vendor, so every field in it would carry `confirmed_by_user:
#: false` forever -- there is no published page for anyone to check it against.
#: It must be cloned before it can be used, and the clone is a real house.
TEMPLATE_KEY = "is_template"


def is_template(profile: dict) -> bool:
    return bool(profile.get(TEMPLATE_KEY))


#: A house that came with the app, or was imported from a published set, rather
#: than one the user wrote. Editing one never overwrites it: the edit becomes a
#: copy, so the original stays intact and deleting the copy is a reset.
SHIPPED_KEY = "is_shipped"

#: On a copy, the id of the shipped house it came from. What makes "reset this
#: back to how it shipped" a real operation rather than a re-download.
CLONED_FROM_KEY = "cloned_from"


def is_shipped(profile: dict) -> bool:
    return bool(profile.get(SHIPPED_KEY))

# The project's own KiCad setting for each field, by its `.kicad_pro` key.
#
# MEASURED 2026-09-08, and the reason this mapping exists at all: a sidecar rule
# does not combine with the board's own constraint, it REPLACES it. A rule
# looser than the project's own setting therefore *hides real violations*. On
# the example board, a sidecar `annular_width` of 0.05mm against a board setup
# requiring 0.1mm took four genuine errors to ZERO.
#
# That is the exact failure `SPEC-114` section 3 forbids -- "the app must never
# be the reason a board comes back wrong" -- and the bundled generic profile
# was looser than KiCad's own defaults on two fields, so it was live.
BOARD_SETUP_KEYS = {
    "min_track_width": "min_track_width",
    "min_clearance": "min_clearance",
    "min_annular_ring": "min_via_annular_width",
    "min_drill": "min_through_hole_diameter",
    "min_hole_to_hole": "min_hole_to_hole",
    "min_edge_clearance": "min_copper_edge_clearance",
    "min_silk_clearance": "min_silk_clearance",
    "min_text_height": "min_text_height",
    "min_text_thickness": "min_text_thickness",
}

ALL_VALUE_FIELDS = tuple(ENFORCEABLE_FIELDS) + RECORDED_ONLY_FIELDS


def _validate_provenance(profile: dict) -> None:
    """Every *value* field present must say where it came from.

    Deliberately mirrors `library_store._validate_part_provenance`: a record
    that cannot say where its numbers came from is one the app must not act on.
    Context fields are exempt -- they describe the order, not a published
    capability, and the user sets them directly."""
    provenance = profile.get("provenance")
    if not isinstance(provenance, dict):
        raise ProfileValidationError(
            "CapabilityProfile.provenance is required and must be a dict keyed by field name."
        )
    for field in ALL_VALUE_FIELDS:
        if profile.get(field) is None:
            continue
        entry = provenance.get(field)
        if not isinstance(entry, dict):
            raise ProfileValidationError(
                f"This profile gives a value for {field} but does not say where it came from. "
                f"Copperplane will not check your board against a number it cannot attribute."
            )
        missing = [k for k in PROVENANCE_REQUIRED_KEYS if k not in entry]
        if missing:
            raise ProfileValidationError(
                f"Provenance for {field} is missing {', '.join(missing)}. Every number this app "
                f"checks against has to carry its source, the date it was recorded, and whether "
                f"you have confirmed it."
            )


def validate(profile: dict) -> dict:
    """Validate and return the profile, or raise `ProfileValidationError`."""
    if not isinstance(profile, dict):
        raise ProfileValidationError("A capability profile must be a dict.")
    if not profile.get("house_name"):
        raise ProfileValidationError(
            "A capability profile has to name the board house it describes -- an unattributed "
            "set of numbers is exactly what this feature exists to avoid."
        )
    for field in ALL_VALUE_FIELDS:
        value = profile.get(field)
        if value is None:
            continue
        if not isinstance(value, (int, float)) or value <= 0:
            raise ProfileValidationError(
                f"{field} must be a positive measurement in millimetres, got {value!r}."
            )
    _validate_provenance(profile)
    return profile


def enforceable_fields(profile: dict) -> list:
    """The fields this profile sets that can actually become a DRC rule."""
    return [f for f in ENFORCEABLE_FIELDS if profile.get(f) is not None]


def recorded_but_unenforceable(profile: dict) -> list:
    """Fields the profile sets that no DRC constraint class can check.

    Surfaced so the review can say which of the user's chosen numbers it did
    not check, rather than implying it checked all of them."""
    return [f for f in RECORDED_ONLY_FIELDS if profile.get(f) is not None]


def compare_to_board_setup(profile: dict, board_rules: dict) -> dict:
    """Where the house is stricter than the project, and where it is not.

    Returns `{field: {"house", "project", "house_is_stricter"}}` for every field
    both sides define. This is what lets the app say which of the user's own
    KiCad settings are already tighter than their fab requires -- and, more
    importantly, stops it emitting a rule that would relax one."""
    comparison = {}
    for field, pro_key in BOARD_SETUP_KEYS.items():
        house = profile.get(field)
        project = board_rules.get(pro_key)
        if house is None or not isinstance(project, (int, float)):
            continue
        comparison[field] = {
            "house": house,
            "project": project,
            # Equal counts as "not stricter": emitting a duplicate rule buys
            # nothing and only adds a way to get it wrong.
            "house_is_stricter": house > project,
        }
    return comparison


def to_rules(profile: dict, severity: str = "warning", board_rules: dict = None) -> list:
    """Turn a profile into `kicad_dru` rule tuples.

    An absent field produces no rule -- section 2.6, and the single most
    important line in this module. The alternative is inventing a limit the
    board house never published and reporting the user's board against it.

    Generated rules are warnings by default so that KiCad's own findings stay
    errors, giving the review an honest visual split between "your fab would
    not build this" and "KiCad's own rules" without inventing a marker
    (section 2.3)."""
    validate(profile)
    comparison = compare_to_board_setup(profile, board_rules or {})
    rules = []
    for field in ENFORCEABLE_FIELDS:
        value = profile.get(field)
        if value is None:
            continue
        # Never emit a rule the project's own setting already beats. A sidecar
        # rule replaces the board constraint rather than adding to it, so a
        # looser one silently switches off a check the user already had.
        entry = comparison.get(field)
        if entry and not entry["house_is_stricter"]:
            continue
        constraint, keyword, rule_name = ENFORCEABLE_FIELDS[field]
        rules.append((rule_name, constraint, f"{keyword} {value}mm", severity))
    return rules


def describe_unenforceable(profile: dict) -> list:
    """Human-readable notes for each recorded-but-unenforceable field."""
    notes = []
    for field in recorded_but_unenforceable(profile):
        notes.append(
            f"{field.replace('_', ' ')} is recorded as {profile[field]}mm but cannot be checked: "
            f"KiCad's design rules have no constraint for it, so this number is shown for your "
            f"reference and was not applied to your board."
        )
    return notes


def field_provenance(profile: dict, field: str) -> dict:
    """The provenance entry for one field, or an empty dict."""
    return (profile.get("provenance") or {}).get(field, {})


def _provenance_for(source_url: str, recorded_on: str, fields) -> dict:
    return {
        field: {
            "source_url": source_url,
            "recorded_on": recorded_on,
            "confirmed_by_user": False,
        }
        for field in fields
    }


def starter_profile(house_name: str, source_url: str, recorded_on: str, **values) -> dict:
    """Build a bundled starter profile with uniform provenance.

    Section 2.7: bundled numbers each carry the date they were recorded and a
    link to the published page, and are never presented as current. Everything
    starts `confirmed_by_user: False` precisely so the UI can say so."""
    unknown = set(values) - set(ALL_VALUE_FIELDS) - set(CONTEXT_FIELDS)
    if unknown:
        raise ProfileValidationError(
            f"Unknown capability field(s): {', '.join(sorted(unknown))}."
        )
    profile = {"house_name": house_name, "schema_version": 1}
    profile.update(values)
    value_fields = [f for f in ALL_VALUE_FIELDS if profile.get(f) is not None]
    profile["provenance"] = _provenance_for(source_url, recorded_on, value_fields)
    return validate(profile)


def clone(profile: dict, house_name: str, house_id: str, recorded_on: str,
          overrides: dict = None) -> dict:
    """Copy a house under a new name, overriding the fields that differ.

    `SPEC-342` section 2.2 calls this the important operation, and the reason is
    arithmetic: most houses differ from a standard process in two or three
    numbers, not nine. Cloning and overriding is a thirty-second job; typing
    nine numbers is a data-entry session, and one abandoned halfway leaves a
    profile that is wrong in a way the app cannot detect.

    **Confirmation is never inherited.** Every field the clone did not change
    comes back `confirmed_by_user: False` with the clone's own `recorded_on`.
    Carrying someone else's confirmation forward is precisely the attribution
    failure per-field provenance was built to prevent (`SPEC-114` section 2.6):
    the new record would claim a human had checked a number against this house's
    published page when nobody had."""
    overrides = overrides or {}
    unknown = set(overrides) - set(ALL_VALUE_FIELDS) - set(CONTEXT_FIELDS)
    if unknown:
        raise ProfileValidationError(
            f"Unknown capability field(s): {', '.join(sorted(unknown))}."
        )

    cloned = {
        **{k: v for k, v in profile.items()
           if k not in ("provenance", "house_name", "house_id", "schema_version")},
        **overrides,
        "house_name": house_name,
        "house_id": house_id,
        "schema_version": 1,
    }
    # A clone is always a real house, and always the user's own. This is the
    # only way one comes into existence from the bundled starting point
    # (`SPEC-342` section 2.5), and the only way a shipped house becomes
    # editable (section 2.6).
    cloned.pop(TEMPLATE_KEY, None)
    cloned.pop(SHIPPED_KEY, None)
    if profile.get("house_id") and is_shipped(profile):
        cloned[CLONED_FROM_KEY] = profile["house_id"]

    provenance = {}
    for field in ALL_VALUE_FIELDS:
        if cloned.get(field) is None:
            continue
        source = field_provenance(profile, field)
        changed = field in overrides
        provenance[field] = {
            # A changed number is the user's own and has no external source
            # until they give it one; an unchanged one keeps the trail it came
            # from, so the clone can still say where the figure originated.
            "source_url": "" if changed else source.get("source_url", ""),
            "recorded_on": recorded_on,
            "confirmed_by_user": False,
        }
    cloned["provenance"] = provenance
    return validate(cloned)


def is_stale(profile: dict, today: str = None, max_age_days: int = 365) -> bool:
    """True when the newest recorded-on date is older than `max_age_days`.

    Section 3: the failure mode is a user ordering against numbers the app
    implied were current. This does not update anything -- staleness is
    reported, never silently repaired."""
    dates = [
        entry.get("recorded_on")
        for entry in (profile.get("provenance") or {}).values()
        if isinstance(entry, dict) and entry.get("recorded_on")
    ]
    if not dates:
        return True
    reference = datetime.date.fromisoformat(today) if today else datetime.date.today()
    try:
        newest = max(datetime.date.fromisoformat(d) for d in dates)
    except ValueError:
        return True
    return (reference - newest).days > max_age_days


def unconfirmed_fields(profile: dict) -> list:
    """Fields the user has not personally confirmed."""
    return sorted(
        field for field in ALL_VALUE_FIELDS
        if profile.get(field) is not None
        and not field_provenance(profile, field).get("confirmed_by_user")
    )


def assert_rules_are_generatable(profile: dict) -> None:
    """Fail before writing if the profile would produce an unusable rule set.

    `kicad_dru.render_sidecar` refuses unconfirmed constraint classes, but that
    error would surface mid-write. Checking here keeps the failure in the layer
    that can explain it."""
    for _, constraint, _, _ in to_rules(profile):
        if constraint not in kicad_dru.CONFIRMED_CONSTRAINTS:
            raise ProfileValidationError(
                f"{constraint} has never been confirmed to fire in this app's own "
                f"measurements, so it will not be written into a design rule file."
            )

"""The consideration record and its trigger discipline -- `SPEC-210`.

A **consideration** is the unit this family generalises. `SPEC-113` computes one
class of finding, `SPEC-332` explains ERC's vocabulary, `SPEC-334` decodes
footprint names, `SPEC-114`/`340`/`342` check manufacturability, `SPEC-328` asks
what the user is building. Five surfaces, five findings shapes, five explanation
paths. This is the shape they should have shared.

**The whole safety property is one sentence** (`SPEC-210` §2.2): no consideration
exists without a trigger that names something real in the project. Without it the
family degenerates into a generative best-practices essay, which is exactly what a
language model produces fluently and wrongly.

That rule is enforced here at construction rather than described in prose,
because a rule written only in prose is one the next caller bypasses. This repo
has paid for that twice already -- `SPEC-342` §2.6's read-only flag that nothing
ever set, and `CTX-326.4`'s placeholder volumes drawn on the two parts that did
not need them.
"""

from datetime import datetime, timezone

#: `SPEC-210` §2.1. The class decides whether a consideration may be raised
#: unprompted -- see `may_raise_unprompted`.
#:
#:   * `computed`  -- read or calculated from files on disk. True or false.
#:   * `cited`     -- relays a fact with a source: a standard, a datasheet page,
#:                    a board house's published limit.
#:   * `judgement` -- an opinion. Legitimate, and never volunteered.
COMPUTED = "computed"
CITED = "cited"
JUDGEMENT = "judgement"
CLAIM_CLASSES = (COMPUTED, CITED, JUDGEMENT)

#: `SPEC-210` §2.3.
RAISED = "raised"
ANSWERED = "answered"
SATISFIED = "satisfied"
DISMISSED = "dismissed"
STATES = (RAISED, ANSWERED, SATISFIED, DISMISSED)

#: `SPEC-113`'s convention, inherited rather than reinvented: a type starting
#: `copperplane.` is this app's own claim and never KiCad's. `chat_agents`
#: already tells the model what the prefix means, so a consideration arriving
#: with it is understood by a surface that predates it.
TYPE_PREFIX = "copperplane."


class ConsiderationError(ValueError):
    """A consideration that would not have been safe to raise."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConsiderationError(message)


def make(
    *,
    id: str,
    domain: str,
    claim_class: str,
    trigger: dict,
    explanation: str,
    source: dict = None,
    arithmetic: dict = None,
    state: str = RAISED,
) -> dict:
    """Build a consideration, or refuse to.

    Every refusal here is `SPEC-210` §2.2 or §2.1 enforced. They are keyword-only
    because a positional call site that silently shifts `source` into `trigger`
    would produce a consideration that passes every check and names the wrong
    thing.

    `trigger` must name something real: `{"kind": ..., "ref": ...}` where `ref`
    is a reference designator, a net name, an intent field, a footprint id --
    something a user can go and look at. A trigger with no `ref` is the failure
    this whole rule exists to prevent, because a claim anchored to nothing is
    indistinguishable from a claim invented.
    """
    _require(bool(id), "A consideration needs an id.")
    _require(bool(domain), "A consideration needs a domain, so a pack is addressable.")
    _require(
        claim_class in CLAIM_CLASSES,
        f"claim_class must be one of {', '.join(CLAIM_CLASSES)} -- got {claim_class!r}.",
    )
    _require(state in STATES, f"state must be one of {', '.join(STATES)} -- got {state!r}.")
    _require(bool(explanation), "A consideration with no explanation teaches nothing.")

    # SPEC-210 §2.2, the safety property.
    _require(
        isinstance(trigger, dict) and bool(trigger.get("ref")) and bool(trigger.get("kind")),
        "A consideration needs a trigger naming something real in this project -- "
        "a reference designator, a net, an intent field. Without one it is a "
        "best-practices essay wearing a finding's clothes.",
    )

    # SPEC-210 §2.1: "Empty is only legal for a computed claim." Enforced in both
    # directions -- a computed claim carrying a source is also wrong, because it
    # implies an authority the calculation does not have and did not need.
    if claim_class == CITED:
        _require(
            isinstance(source, dict) and bool(source.get("ref")),
            "A cited claim must say where the fact came from. This is the same "
            "rigour Part provenance already enforces, for the same reason: a "
            "claim relayed without its source cannot be checked by the person "
            "least able to check it.",
        )
    elif claim_class == COMPUTED:
        _require(
            source is None,
            "A computed claim carries no source -- it IS the source. Attaching "
            "one implies an authority the calculation neither has nor needs.",
        )

    return {
        "id": id,
        "type": id if id.startswith(TYPE_PREFIX) else TYPE_PREFIX + id,
        "domain": domain,
        "claim_class": claim_class,
        "trigger": dict(trigger),
        "source": dict(source) if source else None,
        # SPEC-210 §2.0.1: where a claim rests on a calculation, the calculation
        # itself, shown. Not an optional extra -- for a cited claim built on a
        # standard's formula it is most of what makes the claim checkable.
        "arithmetic": dict(arithmetic) if arithmetic else None,
        "explanation": explanation,
        "state": state,
        "raised_at": datetime.now(timezone.utc).isoformat(),
    }


def may_raise_unprompted(consideration: dict) -> bool:
    """`SPEC-210` §1's initiative rule.

    A computed or cited claim may be volunteered; a judgement waits to be asked.
    This is the line between `SPEC-113` correctly raising D1 unbidden -- the
    underlying claim is falsifiable -- and the same surface announcing "you
    should use a switching regulator here", which is an opinion nobody invited.

    Decided here rather than at each call site, so a new pack cannot get it
    wrong by omission.
    """
    return consideration.get("claim_class") in (COMPUTED, CITED)


def raisable(considerations: list, asked: bool = False) -> list:
    """The considerations a surface may show right now.

    `asked=True` when the user has asked -- then judgements are included, because
    the rule is about initiative, not about hiding anything. A judgement the user
    asked for is exactly what a judgement is for.
    """
    if asked:
        return list(considerations)
    return [c for c in considerations if may_raise_unprompted(c)]

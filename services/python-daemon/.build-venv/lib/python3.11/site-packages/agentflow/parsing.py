"""
Reading JSON out of a model response that was supposed to be JSON.

A model told to "return a JSON array and nothing else" complies almost
every time. The remainder is what this module exists for, and in practice
the failures are not random noise -- they are a small set of recognisable
shapes:

*   The value wrapped in a markdown fence, despite being asked not to.
*   A sentence of preamble before it, or a summary after it.
*   A self-correction: a malformed first attempt, a line of prose noticing
    the mistake, and then the correct value. Real example, captured from a
    live extraction run::

        ["Figure 13-1 shows a typical application circuit...","page":8]

        Wait, must output JSON array only.

        [{"quote":"Figure 13-1 shows a typical application circuit...","page":8}]

    A caller doing ``json.loads(response)`` fails on that, having been
    handed the right answer.

What this module does not do is repair invalid JSON. A response with a
brace missing is not quietly patched up into something plausible -- it
raises, because guessing at what a model meant to say is how a citation
ends up attached to the wrong page number. Recovery from that belongs to
the caller, which can retry the call; there is nothing to recover here.
"""
import json
from typing import Any

__all__ = ["JSONResponseError", "parse_json_response"]

#: How much of the response to quote back in an error. Enough to see the
#: shape of what went wrong in a log; not so much that a 40kB response
#: buries everything around it.
_EXCERPT_CHARS = 500

_OPENERS = {"[": "]", "{": "}"}


class JSONResponseError(ValueError):
    """No JSON value could be found in a model's response.

    Carries the offending text as ``response_text``. That matters more than
    it looks: ``json.JSONDecodeError`` alone reports something like
    "Expecting ',' delimiter: line 1 column 9", which tells you a response
    was malformed but nothing whatsoever about how -- and these failures are
    intermittent, so there is often no second chance to look.
    """

    def __init__(self, message: str, *, response_text: str = "") -> None:
        super().__init__(message)
        self.response_text = response_text


def _span_of_balanced_value(text: str, start: int) -> int | None:
    """Index just past the value opening at ``start``, or None if it never
    closes.

    Bracket counting has to understand strings, or a brace inside a quoted
    datasheet excerpt closes the object early and the scan reports a value
    that stops mid-sentence.
    """
    stack = [_OPENERS[text[start]]]
    in_string = False
    escaped = False

    for i in range(start + 1, len(text)):
        ch = text[i]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch in _OPENERS:
            stack.append(_OPENERS[ch])
        elif ch in ("]", "}"):
            if not stack or ch != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return i + 1

    return None


def _candidates(text: str) -> list[str]:
    """Every top-level ``[...]`` or ``{...}`` region, in the order found.

    Only arrays and objects: those are the shapes an "output JSON"
    instruction produces, and scanning for bare scalars as well would find
    a "candidate" in ordinary prose. Nothing here is parsed yet -- a region
    that balances is not necessarily valid JSON, and both get filtered by
    the caller.

    Scanning stops at an opener that never closes, rather than descending
    into it. That matters for a truncated response: given
    ``[{"a": 1}, {"b": `` -- an array cut off mid-flight -- descending would
    find the one complete object inside and return it, and the caller would
    receive a plausible single-item result with no indication that the rest
    was lost. For extracted citations that is the worst available outcome.
    The cost of this rule is that prose containing an unmatched brace before
    the real value makes the whole response unreadable; that fails loudly,
    which is the side to err on.
    """
    found = []
    i = 0
    while i < len(text):
        if text[i] in _OPENERS:
            end = _span_of_balanced_value(text, i)
            if end is None:
                break
            found.append(text[i:end])
            i = end
            continue
        i += 1
    return found


def parse_json_response(
    text: str,
    *,
    expect: type | tuple[type, ...] | None = None,
) -> Any:
    """The JSON value in a model's response.

    Args:
        text: The response, as the model returned it.
        expect: Optionally the type the value must be -- typically ``list``
            when a prompt asked for an array. Candidates of the wrong type
            are skipped rather than returned, so a stray object in a
            model's preamble cannot stand in for the array that follows it.

    Returns:
        The parsed value.

    Raises:
        JSONResponseError: No candidate parsed, or none matched ``expect``.

    When several candidates parse, the **last** one wins. That is the
    direction a self-correcting model moves in: the bad attempt comes
    first and the correction follows it. A model does not go back and
    revise what it has already written.
    """
    stripped = text.strip()

    if not stripped:
        raise JSONResponseError("the model returned an empty response", response_text=text)

    # The overwhelmingly common case: the model did exactly as asked.
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        pass
    else:
        if expect is None or isinstance(value, expect):
            return value

    matched = None
    for candidate in _candidates(stripped):
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if expect is None or isinstance(value, expect):
            matched = value

    if matched is not None:
        return matched

    excerpt = stripped[:_EXCERPT_CHARS]
    if len(stripped) > _EXCERPT_CHARS:
        excerpt += "..."

    wanted = ""
    if expect is not None:
        names = expect.__name__ if isinstance(expect, type) else "/".join(t.__name__ for t in expect)
        wanted = f" of type {names}"

    raise JSONResponseError(
        f"no JSON value{wanted} found in the model's response: {excerpt!r}",
        response_text=text,
    )

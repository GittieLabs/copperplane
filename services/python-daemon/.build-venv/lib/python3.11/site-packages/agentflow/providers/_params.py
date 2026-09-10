"""Verbatim passthrough of caller-supplied vendor parameters.

Vendors add parameters faster than any framework can name them -- reasoning
effort, thinking budgets, and whatever comes next -- and predicting which
model supports which is not a problem AgentFlow can win. So `chat(params=...)`
forwards a dict straight to the vendor SDK and the caller owns correctness: a
parameter a model ignores is the caller's business, not an AgentFlow error.

What is NOT the caller's business is silently redirecting the call. A `params`
entry that collides with a key AgentFlow itself sets -- the model, the
conversation, the system prompt, the tool definitions -- would change what is
being asked rather than how, with nothing in the response to say so. Those are
refused loudly instead of merged.
"""
from __future__ import annotations

from typing import Any


def merge_params(
    kwargs: dict[str, Any],
    params: dict[str, Any] | None,
    *,
    provider: str,
) -> dict[str, Any]:
    """Merge `params` into `kwargs`, refusing any key `kwargs` already holds.

    Returns `kwargs` (mutated in place, and returned for call-site clarity).

    Raises:
        ValueError: if `params` names a key AgentFlow already set, listing
            every offending key rather than only the first -- a caller
            passing two bad keys should learn both in one run.
        TypeError: if `params` is not a mapping.
    """
    if not params:
        return kwargs
    if not isinstance(params, dict):
        raise TypeError(
            f"{provider}: params must be a dict of vendor arguments, got {type(params).__name__}"
        )

    reserved = sorted(k for k in params if k in kwargs)
    if reserved:
        raise ValueError(
            f"{provider}: params may not override AgentFlow's own arguments: "
            f"{', '.join(reserved)}. Set these through the agent's configuration "
            f"(model, max_tokens, temperature) rather than params, so there is one "
            f"source of truth for each."
        )

    kwargs.update(params)
    return kwargs

"""
LLM provider abstraction (SPEC-201): a thin wrapper around AgentFlow's
(`gittielabs-agentflow`) provider classes -- AnthropicProvider,
GoogleGenAIProvider, and OpenAICompatProvider, which also covers OpenAI
itself, Perplexity, and Ollama, each just a different `base_url`.

Provider SDK classes are imported lazily, inside `_build_provider`, only
once a specific provider is actually selected -- never at daemon startup
-- so a provider SDK import never delays the `daemon.ready` handshake
(SPEC-107) for a provider the current session never configures.

This module is deliberately provider-agnostic and has no dependency on
`daemon.py`'s `CONFIG` -- callers resolve the provider name/API key/model
themselves (from `CONFIG`, in `daemon.py`'s case) and pass them in
explicitly, the same pattern `kicad_bridge`/`freecad_bridge` already use.
"""
import asyncio
import logging
import os
from typing import Any, NotRequired, TypedDict

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Raised for any provider-construction or call failure -- a clean,
    specific daemon error instead of a raw SDK traceback reaching the
    frontend."""


# Ollama and Perplexity both speak the OpenAI-compatible chat completions
# format (SPEC-201 §2) -- routed through the same OpenAICompatProvider as
# real OpenAI itself, just pointed at a different base_url.
_OLLAMA_BASE_URL = "http://localhost:11434/v1"
_PERPLEXITY_BASE_URL = "https://api.perplexity.ai"

# The underlying openai-python client requires a non-empty api_key string
# even though a local Ollama server doesn't actually check it.
_OLLAMA_PLACEHOLDER_API_KEY = "ollama"

# Deliberately not AgentFlow's own per-provider defaults, even though
# they're now the same values as of gittielabs-agentflow==0.8.2 --
# every default here has been confirmed against each provider's real,
# currently-available models via a live API call, not assumed from a
# library default or from memory (see CTX-201.1 and CTX-202.1 Plan
# Drift, and the 2026-08-10 upstream AgentFlow fix that made
# claude-sonnet-5 usable at all: it rejects an explicit `temperature`
# and needs a `-low`/`-medium`/`-high` model-name suffix to opt into
# extended thinking -- see agentflow's AnthropicProvider). `google`
# uses Google's own stable rolling alias rather than a dated snapshot
# so it doesn't go stale the same way `gemini-2.5-flash-preview` (a
# former default here) did -- confirmed 404 before being replaced.
_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "google": "gemini-flash-latest",
    "openai": "gpt-4o",
    "perplexity": "sonar",
    "ollama": "llama3.2:1b",
}

# daemon.py's llm_chat route falls back to this when no provider is
# configured (CONFIG["llm_provider"] unset) and none was passed
# explicitly -- SPEC-303 (the settings UI that would let a human choose)
# doesn't exist yet, and component_extraction.prompt.md already defaults
# to this same provider for kicad.generate_component, so this isn't a
# new app-wide convention, just applying the existing one consistently.
_DEFAULT_PROVIDER = "anthropic"


# ---------------------------------------------------------------------------
# SPEC-208: provider records replace the hardcoded if-chain above. A record
# is `{id, kind, base_url, api_key_ref, models, capabilities}` -- `kind`
# (not `id`) selects which AgentFlow SDK class gets constructed, so any
# OpenAI-compatible server is expressible as a record without a code
# change. `models` is role-keyed (`reasoning`/`fast`, SPEC-208 §2.3) --
# CTX-208.1 seeds both roles with today's single per-provider default
# (see `_preset_records` below) since no agent declares a role yet;
# CTX-208.2 is what actually differentiates them per prompt file.
# ---------------------------------------------------------------------------


class ProviderRecord(TypedDict):
    id: str
    kind: str  # "anthropic" | "openai_compat" | "google"
    base_url: str | None
    api_key_ref: str | None  # a key name in the secrets dict, never a key
    models: dict[str, str]  # role -> model name
    capabilities: dict[str, bool]
    # SPEC-209 §2.1: vendor arguments forwarded verbatim to the SDK call,
    # for anything AgentFlow does not name itself -- reasoning effort,
    # thinking budgets, whatever a vendor ships next. Optional; absent and
    # empty behave identically. AgentFlow refuses any key it sets itself
    # (model, messages, system, tools) with a ValueError naming it, so a
    # passthrough can never silently redirect a call.
    params: NotRequired[dict[str, Any]]


# `managed` is reserved for SPEC-207's locked, code-constructed record --
# never accepted from config.json (SPEC-208 §2.2.3). No preset claims it
# yet; SPEC-207 adds the real record once its gateway base URL exists.
_RESERVED_PROVIDER_IDS = frozenset({"managed"})

# SPEC-207 §2.1: the gateway's base URL is a build-time constant, never a
# config.json field (a settable managed endpoint would let a user's own
# subscription token be pointed at an attacker-chosen host). **No
# hardcoded production fallback is set here.** The real GittieLabs
# gateway is SPEC-404's own external system and does not exist yet as of
# this phase -- inventing a plausible-looking production domain now would
# be worse than an honest "not configured in this build" error, since it
# could be mistaken for a real endpoint or accidentally contacted.
# Development against a local/staging gateway sets this env var; a real
# release build's own hardcoded value is added once the gateway is real.
_MANAGED_GATEWAY_ENV_VAR = "HAS_MANAGED_GATEWAY_URL"

# SPEC-207 §2.4: no live gateway exists to measure against in this
# environment (same external-system gap as the base URL above). Reasoned
# from openai-python's own default (600s read/write) plus real headroom
# for "the gateway adds a hop and may itself be retrying upstream" --
# not a live-measured value. Revisit once a real gateway exists to time.
_MANAGED_TIMEOUT_SECONDS = 900.0

_MANAGED_MAX_RETRIES = 2
# SPEC-207 §2.3: 503 (managed_upstream_unavailable) retries with backoff;
# 429 (managed_rate_limited) retries honoring the gateway's own
# Retry-After value instead. Never 401/402 -- see _ManagedProviderWrapper.
_MANAGED_BACKOFF_BASE_SECONDS = 1.0


class ManagedProviderError(LLMProviderError):
    """SPEC-207 §2.3: a structured, gateway-specific error -- `code` is
    one of the six values that row names, never prose a caller would
    have to string-match. `extra` carries the one real per-code payload
    field SPEC-207 defines (`reset_at` for `managed_quota_exhausted`,
    `retry_after` for `managed_rate_limited`), empty otherwise. Raised
    only for a request that actually reached the managed gateway --
    never for a vendor-direct provider's own, unrelated HTTP error."""

    def __init__(self, code: str, message: str, *, extra: dict | None = None):
        super().__init__(message)
        self.code = code
        self.extra = extra or {}


def _preset_records() -> dict[str, "ProviderRecord"]:
    """Today's five if-chain providers, reseeded as ordinary (editable)
    records with today's exact values -- SPEC-208 §2.2.2. Built fresh on
    every call (a handful of small dicts) so nothing here is a shared
    mutable global a caller could accidentally mutate across calls."""
    return {
        "anthropic": {
            "id": "anthropic", "kind": "anthropic", "base_url": None,
            "api_key_ref": "anthropic_api_key",
            "models": {"reasoning": _DEFAULT_MODELS["anthropic"], "fast": _DEFAULT_MODELS["anthropic"]},
            "capabilities": {"tool_use": True, "strict_json": True},
        },
        "google": {
            "id": "google", "kind": "google", "base_url": None,
            "api_key_ref": "google_api_key",
            "models": {"reasoning": _DEFAULT_MODELS["google"], "fast": _DEFAULT_MODELS["google"]},
            "capabilities": {"tool_use": True, "strict_json": True},
        },
        "openai": {
            "id": "openai", "kind": "openai_compat", "base_url": None,
            "api_key_ref": "openai_api_key",
            "models": {"reasoning": _DEFAULT_MODELS["openai"], "fast": _DEFAULT_MODELS["openai"]},
            "capabilities": {"tool_use": True, "strict_json": True},
        },
        "perplexity": {
            "id": "perplexity", "kind": "openai_compat", "base_url": _PERPLEXITY_BASE_URL,
            "api_key_ref": "perplexity_api_key",
            "models": {"reasoning": _DEFAULT_MODELS["perplexity"], "fast": _DEFAULT_MODELS["perplexity"]},
            "capabilities": {"tool_use": False, "strict_json": False},
        },
        "ollama": {
            "id": "ollama", "kind": "openai_compat", "base_url": _OLLAMA_BASE_URL,
            # No real key concept -- _build_provider_from_record substitutes
            # _OLLAMA_PLACEHOLDER_API_KEY for this record specifically.
            "api_key_ref": None,
            "models": {"reasoning": _DEFAULT_MODELS["ollama"], "fast": _DEFAULT_MODELS["ollama"]},
            # SPEC-208 §3: llama3.2:1b cannot reliably tool-call or hold a
            # strict-JSON contract -- known, not yet verified-and-replaced
            # (§2.2.2 requires a live call against a real local server,
            # unavailable in this environment; see CTX-208.1 Plan Drift).
            "capabilities": {"tool_use": False, "strict_json": False},
        },
        "managed": {
            "id": "managed", "kind": "openai_compat",
            "base_url": os.environ.get(_MANAGED_GATEWAY_ENV_VAR),
            "api_key_ref": "managed_token",
            # SPEC-207 §2.1: "the daemon must not validate a Managed model
            # name" -- no default alias is invented here. A role bound to
            # `managed` with no explicit model override is a real
            # LLMProviderError (SPEC-208 §2.3.2's existing "no model for
            # role" rule), not a guessed alias name.
            "models": {},
            # The gateway proxies to real hosted vendor APIs (SPEC-404
            # §2.2) -- both capabilities are real there, unlike Ollama's
            # honestly-declared gaps above.
            "capabilities": {"tool_use": True, "strict_json": True},
        },
    }


def _map_managed_error(exc: Exception) -> "ManagedProviderError | None":
    """SPEC-207 §2.3: translates a real `openai` SDK exception (the
    gateway is `openai_compat`-shaped by contract, SPEC-404 §2.3) into
    the six-row structured taxonomy -- verified directly against the
    installed SDK's own `_make_status_error` (401/403/404/409/422 ->
    named classes, 429 -> `RateLimitError`, >=500 -> `InternalServerError`,
    anything else -> a bare `APIStatusError` with `.status_code` still
    set). Returns `None` for anything that isn't one of these -- the
    caller re-raises the original exception unchanged in that case."""
    import openai

    if isinstance(exc, openai.APIConnectionError):
        return ManagedProviderError(
            "managed_unreachable",
            "Can't reach the managed service. Your network or the service is down.",
        )

    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        body = exc.body if isinstance(exc.body, dict) else {}

        if status == 401:
            return ManagedProviderError(
                "managed_auth_invalid",
                "Your Copperplane account couldn't be verified.",
            )
        if status == 402:
            return ManagedProviderError(
                "managed_quota_exhausted",
                "You've used this month's allowance.",
                extra={"reset_at": body.get("reset_at")},
            )
        if status == 429:
            retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
            return ManagedProviderError(
                "managed_rate_limited",
                "The managed service is rate-limiting requests.",
                extra={"retry_after": retry_after},
            )
        if status == 503:
            return ManagedProviderError(
                "managed_upstream_unavailable",
                "The model provider is having trouble. This isn't your account.",
            )
        return ManagedProviderError("managed_error", f"Managed request failed (status {status}).")

    return None


class _ManagedProviderWrapper:
    """SPEC-207 §2.2.1: the managed branch and its error mapping live
    here, wrapping whatever real `openai_compat` client
    `_build_provider_from_record` already built for the `managed` record
    -- transparent to every caller of `.chat(...)`, whether that's
    `llm_providers.chat()`'s own code or AgentFlow's `AgentExecutor`
    calling the provider client directly (SPEC-207 §2.2.1's own named
    three-call-site problem: anything added only inside `chat()` is
    invisible to the other two).

    Retries `managed_upstream_unavailable` (503) with linear backoff and
    `managed_rate_limited` (429) honoring the gateway's own `Retry-After`
    -- never `managed_auth_invalid`/`managed_quota_exhausted`, where a
    retry cannot change the outcome before the account is fixed or the
    period resets (SPEC-207 §2.3's own retry policy)."""

    def __init__(self, inner):
        self._inner = inner
        # `_close_provider_client` (CTX-201.1) reaches into `.aio`/`.close()`
        # on whatever's at `._client` -- delegate so cleanup still works
        # for the wrapped client exactly as it would for the real one.
        self._client = getattr(inner, "_client", None)

    async def chat(self, messages, system: str = "", **kwargs):
        attempt = 0
        while True:
            try:
                return await self._inner.chat(messages, system=system, **kwargs)
            except Exception as exc:
                mapped = _map_managed_error(exc)
                if mapped is None:
                    raise

                if mapped.code == "managed_upstream_unavailable" and attempt < _MANAGED_MAX_RETRIES:
                    attempt += 1
                    await asyncio.sleep(_MANAGED_BACKOFF_BASE_SECONDS * attempt)
                    continue

                if mapped.code == "managed_rate_limited" and attempt < _MANAGED_MAX_RETRIES:
                    retry_after = mapped.extra.get("retry_after")
                    if retry_after is not None:
                        try:
                            attempt += 1
                            await asyncio.sleep(float(retry_after))
                            continue
                        except (TypeError, ValueError):
                            pass  # an unparsable Retry-After falls through to raising below

                raise mapped from exc


def _build_provider_from_record(record: "ProviderRecord", api_key: str, model: str | None):
    """The kind-based constructor SPEC-208 §2.2.1 replaces the if-chain
    with. `_build_provider` below is now a thin, id-based lookup on top of
    this -- the one place that still resolves a bare provider *name*
    rather than a full record, kept only for direct callers
    (`llm_providers.chat()`, and this module's own existing test suite)
    that have no `ProviderRecord` to hand it."""
    kind = record["kind"]
    resolved_model = model or record["models"].get("reasoning") or record["models"].get("fast")

    if not api_key and record["id"] == "ollama":
        api_key = _OLLAMA_PLACEHOLDER_API_KEY

    if kind == "anthropic":
        from agentflow import AnthropicProvider

        return AnthropicProvider(api_key=api_key, model=resolved_model)

    if kind == "google":
        from agentflow import GoogleGenAIProvider

        return GoogleGenAIProvider(api_key=api_key, model=resolved_model)

    if kind == "openai_compat":
        from agentflow import OpenAICompatProvider

        if record["id"] == "managed" and not record["base_url"]:
            raise LLMProviderError(
                f"The managed provider has no gateway configured in this build "
                f"(set {_MANAGED_GATEWAY_ENV_VAR} for local development)."
            )

        kwargs: dict[str, Any] = {"api_key": api_key, "model": resolved_model}
        if record["base_url"]:
            kwargs["base_url"] = record["base_url"]
        client = OpenAICompatProvider(**kwargs)

        if record["id"] == "managed":
            client._client.timeout = _MANAGED_TIMEOUT_SECONDS
            return _ManagedProviderWrapper(client)

        return client

    raise LLMProviderError(f"Unknown provider kind: {kind!r} (record id={record['id']!r})")


def _build_provider(provider: str, api_key: str, model: str | None):
    """Constructs the AgentFlow provider class for `provider`, by id,
    against the built-in presets only (no `config.json`-authored records
    -- callers that need those go through `resolve()` instead). Raises
    `LLMProviderError` for an unrecognized provider name -- a clean,
    specific error rather than a KeyError/AttributeError reaching the
    caller. Behavior-preserving refactor of the old if-chain (SPEC-208
    §2.2.1): same construction, same error, same base URLs, for every
    existing caller and this module's own pre-SPEC-208 test suite."""
    record = _preset_records().get(provider)
    if record is None:
        raise LLMProviderError(f"Unknown LLM provider: {provider}")
    return _build_provider_from_record(record, api_key, model)


def _resolve_provider_records(config: dict | None) -> dict[str, "ProviderRecord"]:
    """Preset records, overlaid with any `config.json`-authored `providers`
    entries (SPEC-208 §2.2.1) -- a user record can add a new id or replace
    a preset's id outright ("editable, removable, and copyable"). An entry
    claiming the reserved `managed` id is ignored with a logged warning,
    never merged (SPEC-208 §2.2.3) -- `managed` is SPEC-207's own
    code-constructed record, not yet added by this phase."""
    records = _preset_records()
    for entry in (config or {}).get("providers") or []:
        record_id = entry.get("id")
        if not record_id:
            continue
        if record_id in _RESERVED_PROVIDER_IDS:
            logger.warning(
                "config.json provider record id=%r is reserved and was ignored (not merged)", record_id
            )
            continue
        records[record_id] = entry
    return records


def _resolve_api_key(record: "ProviderRecord", secrets: dict) -> str:
    ref = record.get("api_key_ref")
    if ref is None:
        return ""
    return secrets.get(ref, "")


def migrate_legacy_config(config: dict | None) -> dict:
    """SPEC-208 §2.5: a `config` with `llm_provider` set and no
    `provider_roles` is read as binding both roles to the preset with
    that id, using `llm_model` for the `reasoning` role if it's set (the
    `fast` role keeps that preset's own untouched default -- SPEC-208's
    own wording draws this line specifically for `reasoning`). A `config`
    that already has `provider_roles` set is returned unchanged -- real
    configuration always wins over anything synthesized here. Never
    mutates its input; returns a new dict.

    This is what SPEC-208 §2.3.2 means by "the seeded records mean a
    fresh install is fully configured": by the time `resolve()` looks at
    `provider_roles`, it is never actually empty, even for a `config.json`
    that predates SPEC-208 entirely (`llm_provider`/`llm_model` both
    unset) -- that case binds both roles to `_DEFAULT_PROVIDER`, the same
    built-in default `daemon.py`'s own pre-SPEC-208 fallback already
    used."""
    config = dict(config or {})
    if config.get("provider_roles"):
        return config

    legacy_provider = config.get("llm_provider") or _DEFAULT_PROVIDER
    legacy_model = config.get("llm_model")

    config["provider_roles"] = {"reasoning": legacy_provider, "fast": legacy_provider}

    if legacy_model:
        preset = _preset_records().get(legacy_provider)
        models = dict(preset["models"]) if preset else {}
        models["reasoning"] = legacy_model
        override_record: ProviderRecord = {
            "id": legacy_provider,
            "kind": preset["kind"] if preset else "anthropic",
            "base_url": preset["base_url"] if preset else None,
            "api_key_ref": preset["api_key_ref"] if preset else f"{legacy_provider}_api_key",
            "models": models,
            "capabilities": preset["capabilities"] if preset else {"tool_use": True, "strict_json": True},
        }
        providers = [p for p in (config.get("providers") or []) if p.get("id") != legacy_provider]
        providers.append(override_record)
        config["providers"] = providers

    return config


# SPEC-208 §2.4: (record id, agent name) pairs already preflight-checked
# this session -- keyed on the *agent*, not the `(record, role)` pair the
# spec's own prose suggests, because two agents sharing a role do not
# necessarily share `requires` (this repo's own data: every "fast"-role
# chat agent needs `tool_use`, but `datasheet_guidance_synthesis` -- also
# "fast" -- needs neither). Caching by role alone would let one agent's
# passing check wrongly exempt a different agent's real, unchecked
# requirement against the same record.
_preflight_checked: set[tuple[str, str]] = set()


def _check_capabilities(agent_name: str | None, requires: list[str] | None, record: "ProviderRecord") -> None:
    """SPEC-208 §2.4: before the first call of a session for a given
    (record, agent), checks the agent's declared `requires` against the
    record's declared `capabilities` -- a mismatch is a real
    `LLMProviderError` naming the agent, the requirement, and the record,
    never a silent degrade. A declaration is a claim, not a measurement
    (SPEC-208 §2.4's own explicit caveat) -- this catches an honest
    mismatch (a record that admits it can't tool-call), not an optimistic
    one."""
    if not requires or not agent_name:
        return

    cache_key = (record["id"], agent_name)
    if cache_key in _preflight_checked:
        return

    capabilities = record.get("capabilities") or {}
    missing = [r for r in requires if not capabilities.get(r)]
    if missing:
        raise LLMProviderError(
            f"Agent {agent_name!r} requires {missing}, but provider record {record['id']!r} "
            f"does not declare {'it' if len(missing) == 1 else 'them'}. Bind this agent's role to "
            f"a different provider, or fix that record's declared capabilities."
        )

    _preflight_checked.add(cache_key)


def record_params(config: dict | None, provider_id: str) -> dict:
    """The vendor `params` a provider record carries (SPEC-209 §2.1).

    A separate lookup rather than a fourth element on `resolve()`'s return
    tuple: widening that arity would break every existing caller for a
    value most of them do not want, and `resolve()`'s three-tuple is
    SPEC-208 §2.6's own documented contract.

    Always a dict. Absent and empty are the same answer, because
    AgentFlow treats a falsy `params` as "send nothing" -- so a record
    that has never been given params and one whose params were cleared
    produce an identical request.
    """
    records = _resolve_provider_records(migrate_legacy_config(config or {}))
    record = records.get(provider_id)
    return dict(record.get("params") or {}) if record else {}


def resolve(
    default_provider: str,
    default_model: str,
    secrets: dict,
    provider: str | None = None,
    model: str | None = None,
    config: dict | None = None,
    model_role: str | None = None,
    agent_name: str | None = None,
    requires: list[str] | None = None,
) -> tuple[Any, str, str]:
    """The single provider-construction entry point SPEC-208 §2.6 asks
    for, consolidating what `chat_agents._dispatch` and
    `component_pipeline._build_agent_executor` each used to compute (and
    duplicate) themselves. Returns `(provider_client, resolved_provider,
    resolved_model)`.

    Resolution order (SPEC-208 §2.3.2), first hit wins:
    1. An explicit per-call `provider`/`model` (SPEC-303, CTX-303.2) --
       unchanged precedence from before this function existed. Switching
       `provider` without an explicit `model` does NOT keep the old
       provider's model -- it falls back to the new provider's own
       default, exactly as today's `_DEFAULT_MODELS.get(provider,
       config.model)` behaved (a cross-provider model name is invalid and
       previously produced a confusing empty-response error).
    2. `model_role` (CTX-208.2, from the `.prompt.md` sidecar,
       `agent_roles.py`) resolved through `config`'s (migrated)
       `provider_roles` map to a record, then that record's own model for
       the role. A role bound to an unknown provider id, or a record with
       no model for that role, is a real `LLMProviderError` -- never a
       silent fall-through, per SPEC-208 §2.3.2's own explicit rule.
    3. `default_provider`/`default_model` -- the caller's own default (an
       agent's `.prompt.md` frontmatter default, or a direct caller with
       no role concept at all).

    `agent_name`/`requires` (CTX-208.3, SPEC-208 §2.4): the resolved
    record's `capabilities` are checked against `requires` before any
    provider client is constructed -- see `_check_capabilities`."""
    migrated = migrate_legacy_config(config)
    records = _resolve_provider_records(migrated)

    if provider:
        resolved_provider = provider
    elif model_role:
        bound_id = (migrated.get("provider_roles") or {}).get(model_role)
        if not bound_id:
            raise LLMProviderError(f"No provider bound to model_role={model_role!r}.")
        resolved_provider = bound_id
    else:
        resolved_provider = default_provider

    record = records.get(resolved_provider)
    if record is None:
        raise LLMProviderError(f"Unknown LLM provider: {resolved_provider}")

    if model:
        resolved_model = model
    elif provider:
        resolved_model = record["models"].get("reasoning") or record["models"].get("fast") or default_model
    elif model_role:
        resolved_model = record["models"].get(model_role)
        if not resolved_model:
            raise LLMProviderError(f"Provider {resolved_provider!r} has no model configured for role {model_role!r}.")
    else:
        resolved_model = default_model

    _check_capabilities(agent_name, requires, record)

    api_key = _resolve_api_key(record, secrets)
    provider_client = _build_provider_from_record(record, api_key, resolved_model)
    return provider_client, resolved_provider, resolved_model


async def _close_provider_client(provider_client) -> None:
    """Closes whichever real async SDK client (`openai.AsyncOpenAI`,
    `anthropic.AsyncAnthropic`, `google.genai.Client`'s async sub-client)
    AgentFlow's provider wraps in its private `_client`. Without this,
    each `asyncio.run()` call below tears down its event loop while the
    underlying HTTP client still has connections open, producing a real
    (if harmless) `RuntimeError: Event loop is closed` on cleanup --
    caught by running the real provider calls in `TestRealProviderCalls`,
    not by inspection (CTX-201.1 Plan Drift)."""
    client = getattr(provider_client, "_client", None)
    if client is None:
        return

    aio = getattr(client, "aio", None)
    if aio is not None and hasattr(aio, "aclose"):
        await aio.aclose()
    elif hasattr(client, "close"):
        await client.close()


async def _chat_and_close(provider_client, messages, system: str, params: dict | None = None):
    """Runs the chat call and closes the client within the *same* event
    loop, so cleanup never has to happen after `asyncio.run()` has
    already closed it.

    `params` (SPEC-209 §2.1) reaches AgentFlow 0.11.0's own verbatim
    passthrough. `None` and `{}` are the same request -- AgentFlow treats
    a falsy value as "send nothing" -- so a record with an empty params
    dict is indistinguishable from one with none."""
    try:
        return await provider_client.chat(messages, system=system, params=params or None)
    finally:
        await _close_provider_client(provider_client)


def _resolved_model_for(provider: str, model: str | None) -> str | None:
    """The model `_build_provider`/`_build_provider_from_record` would
    actually construct the provider with, given an explicit `model`
    override or none -- computed independently rather than returned by
    `_build_provider` itself, so `chat()`'s new `model` field in its
    return dict (SPEC-207 §2.2) doesn't require changing `_build_provider`'s
    existing, separately-tested return contract (a bare provider client,
    asserted directly by `TestBuildProvider`)."""
    if model:
        return model
    record = _preset_records().get(provider)
    if record is None:
        return None
    return record["models"].get("reasoning") or record["models"].get("fast")


def chat(
    prompt: str,
    provider: str,
    api_key: str = "",
    model: str | None = None,
    system: str = "",
    history: list[dict] | None = None,
    params: dict[str, Any] | None = None,
) -> dict:
    """Sends one prompt to `provider` and returns `{"text": str, "usage":
    {"input_tokens": int, "output_tokens": int} | None, "model": str |
    None}` (SPEC-207 §2.2) -- a breaking change from the bare `str` this
    returned before, landed as its own context ahead of SPEC-207's
    managed branch per that spec's own explicit sequencing.

    **AgentFlow already reports token usage on every provider** --
    verified directly against the installed source: `providers/
    anthropic.py`, `openai_compat.py`, and `google_genai.py` all
    normalise their own vendor response into the same
    `AgentResponse.usage = {"input_tokens": int, "output_tokens": int}`
    shape (Google's raw response carries a third `thinking_tokens` key,
    dropped here for a return shape that doesn't vary by provider). What
    was missing was never AgentFlow's own reporting -- it was this
    function discarding `response.usage`/`response` entirely and
    returning only `.text`. `usage` is `None` only if a provider reports
    an empty usage dict (observed: Google, when `response.usage_metadata`
    itself is absent), never a fabricated `{0, 0}`.

    `history` (SPEC-302), each entry `{"role": "user"|"assistant", "content": str}`, is prepended
    to `prompt` as prior turns in the same conversation -- the raw provider's own `chat(messages:
    list[Message], ...)` already accepts a full conversation natively (verified against the
    installed package before adding this); this does not go through AgentFlow's `AgentExecutor`
    (which has its own, different `history` mechanism this function never touches). Omitting
    `history` behaves exactly as before: a single-message conversation.

    Synchronous on purpose: `daemon.py`'s `ROUTES` dispatch (SPEC-102) is
    synchronous, so this function -- not every caller -- is the one place
    the sync/async boundary with AgentFlow's `async def chat()` gets
    resolved, via `asyncio.run`.
    """
    from agentflow import Message
    from agentflow.types import Role

    try:
        provider_client = _build_provider(provider, api_key, model)
    except LLMProviderError:
        raise
    except Exception as e:
        raise LLMProviderError(f"Could not construct the '{provider}' provider: {e}") from e

    messages = [
        Message(role=Role(turn["role"]), content=turn["content"]) for turn in (history or [])
    ]
    messages.append(Message(role=Role.USER, content=prompt))

    try:
        response = asyncio.run(_chat_and_close(provider_client, messages, system, params))
    except Exception as e:
        raise LLMProviderError(f"'{provider}' chat call failed: {e}") from e

    usage = None
    if response.usage:
        usage = {
            "input_tokens": response.usage.get("input_tokens", 0),
            "output_tokens": response.usage.get("output_tokens", 0),
        }

    return {
        "text": response.text,
        "usage": usage,
        "model": _resolved_model_for(provider, model),
    }


# ---------------------------------------------------------------------------
# SPEC-324: model identity verification.
#
# SPEC-322 §1 declined this on the grounds that "the app does not know a
# vendor's model list". That premise was false and unchecked: probed
# directly against the installed SDKs on 2026-08-27, every `kind` this
# repo has can list models, and anthropic/openai can retrieve one by id --
# an existence check that costs no tokens, unlike a completion.
#
# Every function here is reached only from an ASYNC_ROUTES-registered
# route. These make real network calls, and CTX-314.2 records the real bug
# from getting that wrong: a GitHub-calling route left out of ASYNC_ROUTES
# blocks the daemon's whole request path while it runs.
#
# SDK imports are lazy and every failure is caught, because a missing SDK,
# a bad key, an unreachable host and a server with no /v1/models endpoint
# are all ordinary states this must report rather than raise on. The UI
# needs the reason, not a stack trace.
# ---------------------------------------------------------------------------


def _list_anthropic(api_key: str, base_url: str | None) -> list[str]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, **({"base_url": base_url} if base_url else {}))
    return [m.id for m in client.models.list()]


def _list_openai_compat(api_key: str, base_url: str | None) -> list[str]:
    import openai

    client = openai.OpenAI(api_key=api_key, **({"base_url": base_url} if base_url else {}))
    return [m.id for m in client.models.list()]


def _list_google(api_key: str, base_url: str | None) -> list[str]:
    from google import genai

    # `name` comes back fully qualified ("models/gemini-..."); the bare id is
    # what a user types and what `models` on a record holds, so strip it.
    return [
        (m.name or "").removeprefix("models/")
        for m in genai.Client(api_key=api_key).models.list()
        if m.name
    ]


# Kept as a dict rather than an if-chain so a test can substitute one entry
# without patching import machinery, and so an unknown kind is a data
# question rather than a missing branch.
_MODEL_LISTERS = {
    "anthropic": _list_anthropic,
    "openai_compat": _list_openai_compat,
    "google": _list_google,
}


def list_models(record: "ProviderRecord", api_key: str) -> dict:
    """Models this provider actually reports.

    Returns `{"supported": bool, "models": [...], "reason": str | None}`.
    `supported: False` is a real answer, never an exception -- an
    `openai_compat` record may point at a server with no `/v1/models` at
    all, which is ordinary and must not read as a failure of the app.
    """
    lister = _MODEL_LISTERS.get(record["kind"])
    if lister is None:
        return {"supported": False, "models": [], "reason": f"unknown provider kind {record['kind']!r}"}

    if not api_key and record["id"] != "ollama":
        return {"supported": False, "models": [], "reason": "no API key is configured for this provider"}

    try:
        models = sorted({m for m in lister(api_key or _OLLAMA_PLACEHOLDER_API_KEY, record["base_url"]) if m})
    except ImportError as exc:
        return {"supported": False, "models": [], "reason": f"the SDK for this provider is not installed ({exc})"}
    except Exception as exc:  # noqa: BLE001 -- every failure is a reportable state
        return {"supported": False, "models": [], "reason": f"{type(exc).__name__}: {exc}"}

    return {"supported": True, "models": models, "reason": None}


# CTX-321.3: the common local endpoint. Named as a constant rather than
# typed into the UI so the editor's suggestion and the ollama preset's own
# base_url cannot drift apart.
LOCAL_OLLAMA_BASE_URL = _OLLAMA_BASE_URL


def probe_endpoint(base_url: str) -> dict:
    """Is something OpenAI-compatible answering at `base_url`?

    Returns `{"reachable": bool, "models": [...], "reason": str | None}`.

    Exists because a NEW `openai_compat` record starts with a blank base
    URL, and blank means the OpenAI SDK's own default -- api.openai.com.
    Nothing told a user that a local server lives somewhere else, so the
    editor could not offer what `list_models` would happily have listed.

    Takes a URL rather than a provider id on purpose: the record being
    configured does not exist yet, so `_resolve_record_and_key` has
    nothing to resolve. No API key is sent -- this probes unauthenticated
    local servers, and a placeholder key is used exactly as the ollama
    record does.

    Never raises. An unreachable host is the ordinary answer here, not an
    error: most of the time nothing is listening and the editor simply
    says nothing."""
    base_url = (base_url or "").strip()
    if not base_url:
        return {"reachable": False, "models": [], "reason": "no base URL given"}
    try:
        models = sorted({m for m in _list_openai_compat(_OLLAMA_PLACEHOLDER_API_KEY, base_url) if m})
    except ImportError as exc:
        return {"reachable": False, "models": [], "reason": f"the OpenAI SDK is not installed ({exc})"}
    except Exception as exc:  # noqa: BLE001 -- nothing listening is an ordinary state
        return {"reachable": False, "models": [], "reason": f"{type(exc).__name__}: {exc}"}
    return {"reachable": True, "models": models, "reason": None}


def validate_model(record: "ProviderRecord", api_key: str, model: str) -> dict:
    """Whether `model` resolves on this provider.

    Returns `{"valid": bool, "reason": str}`. Deliberately does NOT send a
    completion: `models.list` is an existence check that costs no tokens,
    and SPEC-324 §3 names quota as a real cost even for a cheap check.

    A provider that cannot list is reported as unknown rather than invalid.
    Claiming a model is wrong because the server has no `/v1/models` would
    be worse than saying nothing -- SPEC-324 §2.2 keeps free text as the
    floor precisely for that case.
    """
    model = (model or "").strip()
    if not model:
        return {"valid": False, "reason": "no model id given"}

    listed = list_models(record, api_key)
    if not listed["supported"]:
        return {"valid": False, "reason": f"could not check: {listed['reason']}"}

    if model in listed["models"]:
        return {"valid": True, "reason": f"{model} is available on {record['id']}"}

    return {
        "valid": False,
        "reason": (
            f"{record['id']} did not list {model}. It may still work -- a private deployment or a "
            f"model newer than this provider's own list will not appear here."
        ),
    }

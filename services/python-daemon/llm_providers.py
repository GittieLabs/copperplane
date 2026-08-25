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
from typing import Any, TypedDict

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


# `managed` is reserved for SPEC-207's locked, code-constructed record --
# never accepted from config.json (SPEC-208 §2.2.3). No preset claims it
# yet; SPEC-207 adds the real record once its gateway base URL exists.
_RESERVED_PROVIDER_IDS = frozenset({"managed"})


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
    }


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

        kwargs: dict[str, Any] = {"api_key": api_key, "model": resolved_model}
        if record["base_url"]:
            kwargs["base_url"] = record["base_url"]
        return OpenAICompatProvider(**kwargs)

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


def resolve(
    default_provider: str,
    default_model: str,
    secrets: dict,
    provider: str | None = None,
    model: str | None = None,
    config: dict | None = None,
    model_role: str | None = None,
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
       no role concept at all)."""
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


async def _chat_and_close(provider_client, messages, system: str):
    """Runs the chat call and closes the client within the *same* event
    loop, so cleanup never has to happen after `asyncio.run()` has
    already closed it."""
    try:
        return await provider_client.chat(messages, system=system)
    finally:
        await _close_provider_client(provider_client)


def chat(
    prompt: str,
    provider: str,
    api_key: str = "",
    model: str | None = None,
    system: str = "",
    history: list[dict] | None = None,
) -> str:
    """Sends one prompt to `provider` and returns its text response.

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
        response = asyncio.run(_chat_and_close(provider_client, messages, system))
    except Exception as e:
        raise LLMProviderError(f"'{provider}' chat call failed: {e}") from e

    return response.text

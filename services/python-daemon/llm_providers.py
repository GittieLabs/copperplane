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


def _build_provider(provider: str, api_key: str, model: str | None):
    """Constructs the AgentFlow provider class for `provider`. Raises
    `LLMProviderError` for an unrecognized provider name -- a clean,
    specific error rather than a KeyError/AttributeError reaching the
    caller."""
    if provider == "anthropic":
        from agentflow import AnthropicProvider

        return AnthropicProvider(api_key=api_key, model=model or _DEFAULT_MODELS["anthropic"])

    if provider == "google":
        from agentflow import GoogleGenAIProvider

        return GoogleGenAIProvider(api_key=api_key, model=model or _DEFAULT_MODELS["google"])

    if provider == "openai":
        from agentflow import OpenAICompatProvider

        return OpenAICompatProvider(api_key=api_key, model=model or _DEFAULT_MODELS["openai"])

    if provider == "perplexity":
        from agentflow import OpenAICompatProvider

        return OpenAICompatProvider(
            api_key=api_key,
            model=model or _DEFAULT_MODELS["perplexity"],
            base_url=_PERPLEXITY_BASE_URL,
        )

    if provider == "ollama":
        from agentflow import OpenAICompatProvider

        return OpenAICompatProvider(
            api_key=api_key or _OLLAMA_PLACEHOLDER_API_KEY,
            model=model or _DEFAULT_MODELS["ollama"],
            base_url=_OLLAMA_BASE_URL,
        )

    raise LLMProviderError(f"Unknown LLM provider: {provider}")


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

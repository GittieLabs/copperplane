import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _load_dotenv_local() -> None:
    """Loads KEY=VALUE lines from the repo root's .env.local into
    os.environ, for these real-provider tests only. This is a local
    dev/test convenience, not a production code path -- SPEC-106 owns
    the real, OS-keychain-backed secret mechanism the daemon itself uses;
    this file is gitignored and never read by daemon.py."""
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env.local'))
    if not os.path.exists(path):
        return

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv_local()

import llm_providers
from llm_providers import LLMProviderError, _build_provider, chat


class TestBuildProvider(unittest.TestCase):

    def test_001_anthropic_is_constructed_with_the_given_api_key(self):
        """TEST-001: _build_provider constructs a real AnthropicProvider
        (construction itself makes no network call)."""
        from agentflow import AnthropicProvider

        provider = _build_provider("anthropic", "sk-fake-key", None)
        self.assertIsInstance(provider, AnthropicProvider)

    def test_002_google_is_constructed_with_the_given_api_key(self):
        """TEST-001: _build_provider constructs a real GoogleGenAIProvider."""
        from agentflow import GoogleGenAIProvider

        provider = _build_provider("google", "fake-key", None)
        self.assertIsInstance(provider, GoogleGenAIProvider)

    def test_003_ollama_points_at_the_local_openai_compatible_endpoint(self):
        """TEST-001: the 'ollama' provider name routes through
        OpenAICompatProvider pointed at Ollama's own local endpoint, not
        real OpenAI's."""
        from agentflow import OpenAICompatProvider

        provider = _build_provider("ollama", "", None)
        self.assertIsInstance(provider, OpenAICompatProvider)
        self.assertEqual(str(provider._client.base_url).rstrip('/'), llm_providers._OLLAMA_BASE_URL.rstrip('/'))

    def test_004_perplexity_points_at_perplexitys_endpoint(self):
        """TEST-001: the 'perplexity' provider name routes through
        OpenAICompatProvider pointed at Perplexity's own endpoint."""
        from agentflow import OpenAICompatProvider

        provider = _build_provider("perplexity", "pplx-fake", None)
        self.assertIsInstance(provider, OpenAICompatProvider)
        self.assertEqual(str(provider._client.base_url).rstrip('/'), llm_providers._PERPLEXITY_BASE_URL.rstrip('/'))

    def test_005_openai_uses_the_real_default_endpoint(self):
        """TEST-001: the 'openai' provider name leaves base_url unset,
        so the underlying openai-python client defaults to real OpenAI's
        own API, not a proxied/local endpoint."""
        from agentflow import OpenAICompatProvider

        provider = _build_provider("openai", "sk-fake", None)
        self.assertIsInstance(provider, OpenAICompatProvider)
        self.assertIn("api.openai.com", str(provider._client.base_url))

    def test_006_unknown_provider_raises_a_clean_error(self):
        """TEST-001: an unrecognized provider name raises LLMProviderError,
        not a raw KeyError/AttributeError."""
        with self.assertRaises(LLMProviderError):
            _build_provider("carrier-pigeon", "key", None)


class TestRealProviderCalls(unittest.TestCase):
    """Real, non-mocked calls to each configured provider -- CLAUDE.md's
    'verify for real' norm. Each skips itself cleanly (not a failure) when
    its own API key isn't available in this environment (e.g. in CI, which
    has none of these configured), same pattern as CTX-103.1/104.1."""

    _PROMPT = "Reply with exactly one word: pong"

    def test_001_real_anthropic_chat(self):
        """TEST-002."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        text = chat(self._PROMPT, provider="anthropic", api_key=api_key)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text.strip()), 0)

    def test_002_real_google_chat(self):
        """TEST-002."""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            self.skipTest("GOOGLE_API_KEY not set. Add it to .env.local to run this test for real.")

        text = chat(self._PROMPT, provider="google", api_key=api_key)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text.strip()), 0)

    def test_003_real_perplexity_chat(self):
        """TEST-002."""
        api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            self.skipTest("PERPLEXITY_API_KEY not set. Add it to .env.local to run this test for real.")

        text = chat(self._PROMPT, provider="perplexity", api_key=api_key)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text.strip()), 0)

    def test_004_real_ollama_chat(self):
        """TEST-002: no API key needed -- a real, locally running Ollama
        server. Skips itself if Ollama isn't reachable on this machine,
        e.g. in CI, where it isn't installed at all."""
        import httpx

        try:
            httpx.get("http://localhost:11434/api/version", timeout=1.0).raise_for_status()
        except Exception:
            self.skipTest("No local Ollama server reachable at localhost:11434.")

        text = chat(self._PROMPT, provider="ollama")
        self.assertIsInstance(text, str)
        self.assertGreater(len(text.strip()), 0)

    def test_005_real_openai_chat_not_verified_no_key_available(self):
        """TEST-002: not verified for real in this session -- no real
        OpenAI API key was available (see CTX-201.1 Plan Drift). Guards
        against a short placeholder value accidentally being treated as
        real."""
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if len(api_key) < 20:
            self.skipTest("No real OPENAI_API_KEY available -- not verified for real in this session.")

        text = chat(self._PROMPT, provider="openai", api_key=api_key)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text.strip()), 0)


class TestHistory(unittest.TestCase):
    """SPEC-302: `chat()`'s `history` parameter -- a real capability the
    raw provider's own `chat(messages: list[Message], ...)` already
    supports natively; this is this module exposing it, not a new
    AgentFlow capability (see CTX-302.1 Plan Drift Deviation 1)."""

    def _mock_provider_and_capture(self):
        """Mocks _build_provider to return a fake provider client whose
        .chat() records the exact `messages` list it was called with,
        and returns a minimal real-shaped response."""
        from unittest.mock import AsyncMock, MagicMock, patch

        captured = {}

        async def fake_chat(messages, system=""):
            captured["messages"] = messages
            response = MagicMock()
            response.text = "ok"
            return response

        mock_client = MagicMock()
        mock_client.chat = fake_chat
        mock_client._client = None  # short-circuits _close_provider_client's cleanup

        patcher = patch("llm_providers._build_provider", return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return captured

    def test_001_omitting_history_matches_the_pre_existing_single_message_behavior(self):
        """TEST-003: a regression check -- every existing caller omits
        history and must see exactly the same message list as before
        this parameter existed."""
        from agentflow.types import Message, Role

        captured = self._mock_provider_and_capture()
        chat("hello", provider="anthropic", api_key="test-key")

        self.assertEqual(captured["messages"], [Message(role=Role.USER, content="hello")])

    def test_002_history_is_prepended_before_the_new_prompt(self):
        """TEST-003: history entries become real Message objects, in
        order, before the new prompt's own message."""
        from agentflow.types import Message, Role

        captured = self._mock_provider_and_capture()
        chat(
            "what's my favorite number?",
            provider="anthropic",
            api_key="test-key",
            history=[
                {"role": "user", "content": "my favorite number is 42"},
                {"role": "assistant", "content": "got it, 42"},
            ],
        )

        self.assertEqual(
            captured["messages"],
            [
                Message(role=Role.USER, content="my favorite number is 42"),
                Message(role=Role.ASSISTANT, content="got it, 42"),
                Message(role=Role.USER, content="what's my favorite number?"),
            ],
        )

    def test_003_a_real_multi_turn_call_actually_uses_prior_context(self):
        """TEST-003: real, live proof -- not just that the right objects
        get constructed, but that a real model call with `history` set
        answers using information *only* the history turn established.
        Skips cleanly without a real ANTHROPIC_API_KEY."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        text = chat(
            "What is my favorite number? Reply with only the number.",
            provider="anthropic",
            api_key=api_key,
            history=[
                {"role": "user", "content": "My favorite number is 42."},
                {"role": "assistant", "content": "Got it, I'll remember that."},
            ],
        )
        self.assertIn("42", text)


if __name__ == '__main__':
    unittest.main()

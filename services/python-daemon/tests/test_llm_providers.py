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
from llm_providers import LLMProviderError, _build_provider, chat, resolve


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

    def _assert_real_usage_shape(self, result: dict, expected_provider_default_model: bool = True) -> None:
        """CTX-207.1 (SPEC-207 §2.2): a real, live call must report real
        non-zero usage -- not just a well-typed empty dict. Verified live
        rather than assumed from AgentFlow's own already-checked source,
        since a provider's SDK version drifting could silently zero this
        out without any test catching it."""
        self.assertIsInstance(result, dict)
        self.assertIsInstance(result["text"], str)
        self.assertGreater(len(result["text"].strip()), 0)
        self.assertIsNotNone(result["usage"], "a real call must report real usage, not None")
        self.assertGreater(result["usage"]["input_tokens"], 0)
        self.assertGreater(result["usage"]["output_tokens"], 0)
        if expected_provider_default_model:
            self.assertIsInstance(result["model"], str)
            self.assertGreater(len(result["model"]), 0)

    def test_001_real_anthropic_chat(self):
        """TEST-002."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        result = chat(self._PROMPT, provider="anthropic", api_key=api_key)
        self._assert_real_usage_shape(result)

    def test_002_real_google_chat(self):
        """TEST-002."""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            self.skipTest("GOOGLE_API_KEY not set. Add it to .env.local to run this test for real.")

        result = chat(self._PROMPT, provider="google", api_key=api_key)
        self._assert_real_usage_shape(result)

    def test_003_real_perplexity_chat(self):
        """TEST-002."""
        api_key = os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            self.skipTest("PERPLEXITY_API_KEY not set. Add it to .env.local to run this test for real.")

        result = chat(self._PROMPT, provider="perplexity", api_key=api_key)
        self._assert_real_usage_shape(result)

    def test_004_real_ollama_chat(self):
        """TEST-002: no API key needed -- a real, locally running Ollama
        server. Skips itself if Ollama isn't reachable on this machine,
        e.g. in CI, where it isn't installed at all."""
        import httpx

        try:
            httpx.get("http://localhost:11434/api/version", timeout=1.0).raise_for_status()
        except Exception:
            self.skipTest("No local Ollama server reachable at localhost:11434.")

        result = chat(self._PROMPT, provider="ollama")
        self._assert_real_usage_shape(result)

    def test_005_real_openai_chat_not_verified_no_key_available(self):
        """TEST-002: not verified for real in this session -- no real
        OpenAI API key was available (see CTX-201.1 Plan Drift). Guards
        against a short placeholder value accidentally being treated as
        real."""
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if len(api_key) < 20:
            self.skipTest("No real OPENAI_API_KEY available -- not verified for real in this session.")

        result = chat(self._PROMPT, provider="openai", api_key=api_key)
        self._assert_real_usage_shape(result)


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

        async def fake_chat(messages, system="", params=None):
            captured["messages"] = messages
            response = MagicMock()
            response.text = "ok"
            response.usage = {"input_tokens": 5, "output_tokens": 1}
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

        result = chat(
            "What is my favorite number? Reply with only the number.",
            provider="anthropic",
            api_key=api_key,
            history=[
                {"role": "user", "content": "My favorite number is 42."},
                {"role": "assistant", "content": "Got it, I'll remember that."},
            ],
        )
        self.assertIn("42", result["text"])


class TestPresetRecords(unittest.TestCase):
    """SPEC-208 §2.2.2: today's five if-chain providers, reseeded as
    records with today's exact values."""

    def test_001_every_known_provider_has_a_preset_record(self):
        records = llm_providers._preset_records()
        self.assertEqual(set(records.keys()), {"anthropic", "google", "openai", "perplexity", "ollama", "managed"})

    def test_002_kind_matches_which_sdk_each_provider_used_before(self):
        records = llm_providers._preset_records()
        self.assertEqual(records["anthropic"]["kind"], "anthropic")
        self.assertEqual(records["google"]["kind"], "google")
        for name in ("openai", "perplexity", "ollama"):
            self.assertEqual(records[name]["kind"], "openai_compat")

    def test_003_base_urls_match_todays_constants(self):
        records = llm_providers._preset_records()
        self.assertIsNone(records["openai"]["base_url"])
        self.assertEqual(records["perplexity"]["base_url"], llm_providers._PERPLEXITY_BASE_URL)
        self.assertEqual(records["ollama"]["base_url"], llm_providers._OLLAMA_BASE_URL)

    def test_004_api_key_refs_match_known_secret_key_names(self):
        records = llm_providers._preset_records()
        self.assertEqual(records["anthropic"]["api_key_ref"], "anthropic_api_key")
        self.assertEqual(records["google"]["api_key_ref"], "google_api_key")
        self.assertEqual(records["openai"]["api_key_ref"], "openai_api_key")
        self.assertEqual(records["perplexity"]["api_key_ref"], "perplexity_api_key")
        self.assertIsNone(records["ollama"]["api_key_ref"], "ollama has no real key concept")

    def test_005_mutating_one_calls_result_never_leaks_into_the_next(self):
        first = llm_providers._preset_records()
        first["anthropic"]["base_url"] = "https://attacker.example"
        second = llm_providers._preset_records()
        self.assertIsNone(second["anthropic"]["base_url"])


class TestBuildProviderFromRecord(unittest.TestCase):
    """SPEC-208 §2.2.1: the kind-based constructor. Mirrors
    TestBuildProvider's own assertions but via a record, confirming
    `_build_provider` (name-based) and `_build_provider_from_record`
    (record-based) agree."""

    def test_001_unknown_kind_raises_a_clean_error(self):
        bad_record: llm_providers.ProviderRecord = {
            "id": "x", "kind": "carrier-pigeon", "base_url": None,
            "api_key_ref": None, "models": {}, "capabilities": {},
        }
        with self.assertRaises(LLMProviderError):
            llm_providers._build_provider_from_record(bad_record, "key", None)

    def test_002_ollama_record_gets_the_placeholder_key_when_none_given(self):
        from agentflow import OpenAICompatProvider

        record = llm_providers._preset_records()["ollama"]
        provider = llm_providers._build_provider_from_record(record, "", None)
        self.assertIsInstance(provider, OpenAICompatProvider)

    def test_003_an_explicit_model_wins_over_the_records_own_default(self):
        from agentflow import AnthropicProvider

        record = llm_providers._preset_records()["anthropic"]
        provider = llm_providers._build_provider_from_record(record, "key", "claude-sonnet-5-low")
        self.assertIsInstance(provider, AnthropicProvider)
        self.assertEqual(provider._model, "claude-sonnet-5-low")


class TestResolveProviderRecords(unittest.TestCase):
    """SPEC-208 §2.2.1/§2.2.3: config.json-authored records overlay the
    presets; the reserved `managed` id is never merged."""

    def test_001_no_config_returns_only_presets(self):
        records = llm_providers._resolve_provider_records(None)
        self.assertEqual(set(records.keys()), {"anthropic", "google", "openai", "perplexity", "ollama", "managed"})

    def test_002_a_new_id_is_added_alongside_the_presets(self):
        config = {"providers": [{"id": "workshop-ollama", "kind": "openai_compat", "base_url": "http://nuc.local:11434/v1"}]}
        records = llm_providers._resolve_provider_records(config)
        self.assertIn("workshop-ollama", records)
        self.assertIn("anthropic", records, "presets must still be present")

    def test_003_a_record_reusing_a_preset_id_replaces_it(self):
        config = {"providers": [{"id": "anthropic", "kind": "openai_compat", "base_url": "http://localhost:9999/v1"}]}
        records = llm_providers._resolve_provider_records(config)
        self.assertEqual(records["anthropic"]["kind"], "openai_compat")
        self.assertEqual(records["anthropic"]["base_url"], "http://localhost:9999/v1")

    def test_004_an_entry_claiming_the_reserved_managed_id_is_ignored(self):
        config = {"providers": [{"id": "managed", "kind": "openai_compat", "base_url": "http://attacker.example/v1"}]}
        records = llm_providers._resolve_provider_records(config)
        self.assertNotEqual(
            records["managed"]["base_url"], "http://attacker.example/v1",
            "a config.json entry must never override the locked managed record",
        )

    def test_005_an_entry_with_no_id_is_skipped_rather_than_crashing(self):
        config = {"providers": [{"kind": "openai_compat", "base_url": "http://x"}]}
        records = llm_providers._resolve_provider_records(config)
        self.assertEqual(set(records.keys()), {"anthropic", "google", "openai", "perplexity", "ollama", "managed"})


class TestResolve(unittest.TestCase):
    """SPEC-208 §2.6: the single provider-construction entry point that
    replaces the duplicated override blocks in chat_agents._dispatch and
    component_pipeline._build_agent_executor."""

    def test_001_no_override_uses_the_callers_own_default(self):
        _, resolved_provider, resolved_model = resolve(
            "anthropic", "claude-sonnet-4-6", {"anthropic_api_key": "sk-fake"},
        )
        self.assertEqual(resolved_provider, "anthropic")
        self.assertEqual(resolved_model, "claude-sonnet-4-6")

    def test_002_an_explicit_model_override_wins_regardless_of_provider(self):
        _, resolved_provider, resolved_model = resolve(
            "anthropic", "claude-sonnet-4-6", {"anthropic_api_key": "sk-fake"}, model="claude-sonnet-5-low",
        )
        self.assertEqual(resolved_provider, "anthropic")
        self.assertEqual(resolved_model, "claude-sonnet-5-low")

    def test_003_switching_provider_without_a_model_falls_back_to_the_new_providers_own_default(self):
        """Regression check for the real bug CTX-303.2 found against a
        live Google call: keeping the old provider's model name across a
        provider switch is invalid, not just suboptimal."""
        _, resolved_provider, resolved_model = resolve(
            "anthropic", "claude-sonnet-4-6", {"google_api_key": "fake"}, provider="google",
        )
        self.assertEqual(resolved_provider, "google")
        self.assertEqual(resolved_model, llm_providers._DEFAULT_MODELS["google"])

    def test_004_an_unknown_explicit_provider_override_raises(self):
        with self.assertRaises(LLMProviderError):
            resolve("anthropic", "claude-sonnet-4-6", {}, provider="carrier-pigeon")

    def test_005_the_api_key_is_looked_up_by_the_resolved_records_own_ref(self):
        from unittest.mock import patch

        captured = {}

        def fake_build(record, api_key, model):
            captured["api_key"] = api_key
            return object()

        with patch("llm_providers._build_provider_from_record", side_effect=fake_build):
            resolve("google", "gemini-flash-latest", {"google_api_key": "the-real-key", "anthropic_api_key": "wrong-one"})

        self.assertEqual(captured["api_key"], "the-real-key")

    def test_006_a_config_json_authored_record_is_reachable(self):
        config = {
            "providers": [{
                "id": "workshop-ollama", "kind": "openai_compat",
                "base_url": "http://nuc.local:11434/v1", "api_key_ref": "workshop_key",
                "models": {"reasoning": "qwen2.5:32b", "fast": "qwen2.5:7b"},
                "capabilities": {"tool_use": True, "strict_json": True},
            }],
        }
        from agentflow import OpenAICompatProvider

        provider_client, resolved_provider, resolved_model = resolve(
            "anthropic", "claude-sonnet-4-6", {"workshop_key": "fake-key"}, provider="workshop-ollama", config=config,
        )
        self.assertEqual(resolved_provider, "workshop-ollama")
        self.assertEqual(resolved_model, "qwen2.5:32b")
        self.assertIsInstance(provider_client, OpenAICompatProvider)

    def test_007_the_reserved_managed_id_cannot_be_reached_via_an_explicit_override(self):
        config = {"providers": [{"id": "managed", "kind": "openai_compat", "base_url": "http://attacker.example/v1"}]}
        with self.assertRaises(LLMProviderError):
            resolve("anthropic", "claude-sonnet-4-6", {}, provider="managed", config=config)


class TestMigrateLegacyConfig(unittest.TestCase):
    """SPEC-208 §2.5: a config.json predating SPEC-208 (llm_provider/
    llm_model, no provider_roles) is read as binding both roles to that
    provider, using llm_model for the reasoning role specifically."""

    def test_001_none_config_binds_both_roles_to_the_built_in_default(self):
        migrated = llm_providers.migrate_legacy_config(None)
        self.assertEqual(
            migrated["provider_roles"], {"reasoning": llm_providers._DEFAULT_PROVIDER, "fast": llm_providers._DEFAULT_PROVIDER}
        )

    def test_002_llm_provider_only_binds_both_roles_to_it_unchanged(self):
        migrated = llm_providers.migrate_legacy_config({"llm_provider": "google"})
        self.assertEqual(migrated["provider_roles"], {"reasoning": "google", "fast": "google"})
        self.assertNotIn("providers", migrated, "no llm_model means no override record is needed")

    def test_003_llm_model_overrides_only_the_reasoning_role_for_that_provider(self):
        migrated = llm_providers.migrate_legacy_config({"llm_provider": "anthropic", "llm_model": "claude-sonnet-5-low"})
        override = next(p for p in migrated["providers"] if p["id"] == "anthropic")
        self.assertEqual(override["models"]["reasoning"], "claude-sonnet-5-low")
        self.assertEqual(override["models"]["fast"], llm_providers._DEFAULT_MODELS["anthropic"], "fast keeps the preset's own default")

    def test_004_an_existing_provider_roles_map_is_returned_unchanged(self):
        config = {"llm_provider": "google", "provider_roles": {"reasoning": "anthropic", "fast": "ollama"}}
        migrated = llm_providers.migrate_legacy_config(config)
        self.assertEqual(migrated["provider_roles"], {"reasoning": "anthropic", "fast": "ollama"})

    def test_005_never_mutates_its_input(self):
        original = {"llm_provider": "google"}
        llm_providers.migrate_legacy_config(original)
        self.assertEqual(original, {"llm_provider": "google"})


class TestResolveModelRole(unittest.TestCase):
    """SPEC-208 §2.3.2: resolution order step 2 -- model_role, resolved
    through config's (migrated) provider_roles map."""

    def test_001_an_unconfigured_install_resolves_via_the_built_in_default_provider(self):
        _, resolved_provider, resolved_model = resolve(
            "anthropic", "claude-sonnet-4-6", {"anthropic_api_key": "sk-fake"}, model_role="fast", config={},
        )
        self.assertEqual(resolved_provider, llm_providers._DEFAULT_PROVIDER)
        self.assertEqual(resolved_model, llm_providers._DEFAULT_MODELS[llm_providers._DEFAULT_PROVIDER])

    def test_002_a_real_provider_roles_binding_is_honored_per_role(self):
        config = {"provider_roles": {"reasoning": "anthropic", "fast": "google"}}
        _, resolved_provider, resolved_model = resolve(
            "anthropic", "claude-sonnet-4-6", {"google_api_key": "fake"}, model_role="fast", config=config,
        )
        self.assertEqual(resolved_provider, "google")
        self.assertEqual(resolved_model, llm_providers._DEFAULT_MODELS["google"])

    def test_003_a_role_bound_to_an_unknown_provider_id_is_a_real_error_not_a_silent_fallback(self):
        config = {"provider_roles": {"reasoning": "does-not-exist", "fast": "anthropic"}}
        with self.assertRaises(LLMProviderError):
            resolve("anthropic", "claude-sonnet-4-6", {}, model_role="reasoning", config=config)

    def test_004_a_record_with_no_model_for_the_requested_role_is_a_real_error(self):
        config = {
            "providers": [{"id": "custom", "kind": "openai_compat", "base_url": "http://x", "models": {"fast": "small-model"}}],
            "provider_roles": {"reasoning": "custom", "fast": "custom"},
        }
        with self.assertRaises(LLMProviderError):
            resolve("anthropic", "claude-sonnet-4-6", {}, model_role="reasoning", config=config)

    def test_005_an_explicit_provider_override_wins_over_model_role(self):
        """Resolution order step 1 beats step 2 -- a Settings-level
        provider override applies wholesale, unaware of any role."""
        config = {"provider_roles": {"reasoning": "anthropic", "fast": "anthropic"}}
        _, resolved_provider, resolved_model = resolve(
            "anthropic", "claude-sonnet-4-6", {"google_api_key": "fake"},
            provider="google", model_role="reasoning", config=config,
        )
        self.assertEqual(resolved_provider, "google")
        self.assertEqual(resolved_model, llm_providers._DEFAULT_MODELS["google"])

    def test_006_llm_model_migration_reaches_a_real_reasoning_role_call(self):
        """End-to-end: a config.json from before SPEC-208 (llm_provider +
        llm_model set, no provider_roles) still routes a reasoning-role
        agent to the user's own chosen model, via migration."""
        config = {"llm_provider": "anthropic", "llm_model": "claude-sonnet-5-low"}
        _, resolved_provider, resolved_model = resolve(
            "anthropic", "claude-sonnet-4-6", {"anthropic_api_key": "sk-fake"}, model_role="reasoning", config=config,
        )
        self.assertEqual(resolved_provider, "anthropic")
        self.assertEqual(resolved_model, "claude-sonnet-5-low")

    def test_007_llm_model_migration_does_not_leak_into_the_fast_role(self):
        config = {"llm_provider": "anthropic", "llm_model": "claude-sonnet-5-low"}
        _, resolved_provider, resolved_model = resolve(
            "anthropic", "claude-sonnet-4-6", {"anthropic_api_key": "sk-fake"}, model_role="fast", config=config,
        )
        self.assertEqual(resolved_model, llm_providers._DEFAULT_MODELS["anthropic"])


class TestCheckCapabilities(unittest.TestCase):
    """SPEC-208 §2.4: an agent's requires checked against a provider
    record's declared capabilities, before any provider client is built."""

    def setUp(self):
        llm_providers._preflight_checked.clear()

    def _record(self, **capabilities) -> "llm_providers.ProviderRecord":
        return {
            "id": "test-record", "kind": "anthropic", "base_url": None, "api_key_ref": None,
            "models": {"reasoning": "m", "fast": "m"}, "capabilities": capabilities,
        }

    def test_001_no_requires_is_a_no_op(self):
        llm_providers._check_capabilities("some_agent", None, self._record())
        llm_providers._check_capabilities("some_agent", [], self._record())

    def test_002_no_agent_name_is_a_no_op_even_with_requires(self):
        llm_providers._check_capabilities(None, ["tool_use"], self._record())

    def test_003_a_satisfied_requirement_raises_nothing(self):
        llm_providers._check_capabilities("chat_overview", ["tool_use"], self._record(tool_use=True))

    def test_004_a_missing_capability_raises_naming_the_agent_requirement_and_record(self):
        with self.assertRaises(LLMProviderError) as ctx:
            llm_providers._check_capabilities("chat_overview", ["tool_use"], self._record(tool_use=False))
        message = str(ctx.exception)
        self.assertIn("chat_overview", message)
        self.assertIn("tool_use", message)
        self.assertIn("test-record", message)

    def test_005_an_undeclared_capability_key_counts_as_not_offered(self):
        with self.assertRaises(LLMProviderError):
            llm_providers._check_capabilities("component_extraction", ["strict_json"], self._record(tool_use=True))

    def test_006_a_passed_check_is_cached_per_record_and_agent(self):
        from unittest.mock import patch

        record = self._record(tool_use=True)
        llm_providers._check_capabilities("chat_overview", ["tool_use"], record)
        self.assertIn(("test-record", "chat_overview"), llm_providers._preflight_checked)

        # A second call against a record whose capabilities have since
        # regressed does NOT re-raise -- cached per (record id, agent),
        # matching "before the first call of a session".
        with patch.dict(record, {"capabilities": {"tool_use": False}}):
            llm_providers._check_capabilities("chat_overview", ["tool_use"], record)

    def test_007_caching_is_per_agent_not_per_role_or_record_alone(self):
        """Regression check for the exact bug a (record, role) cache key
        would have: two agents sharing a role/record but NOT sharing
        requires must each be checked independently."""
        record = self._record(tool_use=False)
        # chat_overview has no requires met yet -- checking a DIFFERENT
        # agent (datasheet_guidance_synthesis, real requires=[]) against
        # the same record first must not exempt chat_overview afterward.
        llm_providers._check_capabilities("datasheet_guidance_synthesis", [], record)
        with self.assertRaises(LLMProviderError):
            llm_providers._check_capabilities("chat_overview", ["tool_use"], record)

    def test_008_resolve_raises_before_constructing_a_provider_for_a_failed_preflight(self):
        config = {
            "providers": [{
                "id": "weak-local", "kind": "openai_compat", "base_url": "http://localhost:9999/v1",
                "models": {"reasoning": "tiny", "fast": "tiny"}, "capabilities": {"tool_use": False, "strict_json": False},
            }],
            "provider_roles": {"reasoning": "weak-local", "fast": "weak-local"},
        }
        with self.assertRaises(LLMProviderError):
            resolve(
                "anthropic", "claude-sonnet-4-6", {}, model_role="fast", config=config,
                agent_name="chat_overview", requires=["tool_use"],
            )

    def test_009_resolve_succeeds_when_the_bound_record_declares_the_requirement(self):
        config = {
            "providers": [{
                "id": "capable-local", "kind": "openai_compat", "base_url": "http://localhost:9999/v1",
                "api_key_ref": "capable_local_key",
                "models": {"reasoning": "big", "fast": "big"}, "capabilities": {"tool_use": True, "strict_json": True},
            }],
            "provider_roles": {"reasoning": "capable-local", "fast": "capable-local"},
        }
        _, resolved_provider, _ = resolve(
            "anthropic", "claude-sonnet-4-6", {"capable_local_key": "fake"}, model_role="fast", config=config,
            agent_name="chat_overview", requires=["tool_use"],
        )
        self.assertEqual(resolved_provider, "capable-local")


def _fake_status_error(status: int, body: dict | None = None, headers: dict | None = None):
    """A real `openai.APIStatusError` (or the real subclass the SDK's own
    `_make_status_error` would construct for `status`) built against a
    real `httpx.Response` -- SPEC-207 §2.5: no test may contact the real
    gateway, so this is the stub HTTP layer standing in for one, not a
    mock of `_map_managed_error` itself."""
    import httpx
    import openai

    request = httpx.Request("POST", "https://managed.example/v1/chat/completions")
    response = httpx.Response(status, request=request, json=body or {}, headers=headers or {})

    if status == 401:
        return openai.AuthenticationError(f"status {status}", response=response, body=body)
    if status == 429:
        return openai.RateLimitError(f"status {status}", response=response, body=body)
    if status >= 500:
        return openai.InternalServerError(f"status {status}", response=response, body=body)
    return openai.APIStatusError(f"status {status}", response=response, body=body)


def _fake_connection_error():
    import httpx
    import openai

    request = httpx.Request("POST", "https://managed.example/v1/chat/completions")
    return openai.APIConnectionError(message="Connection error.", request=request)


class TestMapManagedError(unittest.TestCase):
    """SPEC-207 §2.3: gateway HTTP status -> structured error code, built
    against real openai SDK exception instances (SPEC-207 §2.5's stub
    HTTP layer), never a live gateway."""

    def test_001_401_maps_to_managed_auth_invalid(self):
        mapped = llm_providers._map_managed_error(_fake_status_error(401))
        self.assertEqual(mapped.code, "managed_auth_invalid")

    def test_002_402_maps_to_managed_quota_exhausted_carrying_reset_at(self):
        mapped = llm_providers._map_managed_error(_fake_status_error(402, body={"reset_at": "2026-09-01T00:00:00Z"}))
        self.assertEqual(mapped.code, "managed_quota_exhausted")
        self.assertEqual(mapped.extra["reset_at"], "2026-09-01T00:00:00Z")

    def test_003_429_maps_to_managed_rate_limited_carrying_retry_after(self):
        mapped = llm_providers._map_managed_error(_fake_status_error(429, headers={"Retry-After": "12"}))
        self.assertEqual(mapped.code, "managed_rate_limited")
        self.assertEqual(mapped.extra["retry_after"], "12")

    def test_004_503_maps_to_managed_upstream_unavailable(self):
        mapped = llm_providers._map_managed_error(_fake_status_error(503))
        self.assertEqual(mapped.code, "managed_upstream_unavailable")

    def test_005_an_unmapped_status_falls_back_to_managed_error(self):
        mapped = llm_providers._map_managed_error(_fake_status_error(418))
        self.assertEqual(mapped.code, "managed_error")

    def test_006_a_connection_failure_maps_to_managed_unreachable(self):
        mapped = llm_providers._map_managed_error(_fake_connection_error())
        self.assertEqual(mapped.code, "managed_unreachable")

    def test_007_an_unrelated_exception_is_not_mapped(self):
        self.assertIsNone(llm_providers._map_managed_error(ValueError("not a managed error at all")))


class TestManagedProviderWrapper(unittest.IsolatedAsyncioTestCase):
    """SPEC-207 §2.3's retry policy: 503 retries with backoff, 429
    retries honoring Retry-After, 401/402 never retry."""

    def _wrapper_around(self, side_effects):
        from unittest.mock import AsyncMock

        inner = AsyncMock()
        inner.chat.side_effect = side_effects
        inner._client = "the-real-client"
        wrapper = llm_providers._ManagedProviderWrapper(inner)
        return wrapper, inner

    async def test_001_a_success_on_the_first_try_returns_immediately(self):
        wrapper, inner = self._wrapper_around(["ok"])
        result = await wrapper.chat([])
        self.assertEqual(result, "ok")
        self.assertEqual(inner.chat.call_count, 1)

    async def test_002_delegates_close_via_the_real_inner_client(self):
        wrapper, _ = self._wrapper_around(["ok"])
        self.assertEqual(wrapper._client, "the-real-client")

    async def test_003_a_401_is_never_retried(self):
        wrapper, inner = self._wrapper_around([_fake_status_error(401)])
        with self.assertRaises(llm_providers.ManagedProviderError) as ctx:
            await wrapper.chat([])
        self.assertEqual(ctx.exception.code, "managed_auth_invalid")
        self.assertEqual(inner.chat.call_count, 1)

    async def test_004_a_402_is_never_retried(self):
        wrapper, inner = self._wrapper_around([_fake_status_error(402)])
        with self.assertRaises(llm_providers.ManagedProviderError) as ctx:
            await wrapper.chat([])
        self.assertEqual(ctx.exception.code, "managed_quota_exhausted")
        self.assertEqual(inner.chat.call_count, 1)

    async def test_005_a_503_retries_then_succeeds(self):
        wrapper, inner = self._wrapper_around([_fake_status_error(503), _fake_status_error(503), "ok"])
        llm_providers._MANAGED_BACKOFF_BASE_SECONDS = 0.0  # don't actually sleep in tests
        result = await wrapper.chat([])
        self.assertEqual(result, "ok")
        self.assertEqual(inner.chat.call_count, 3)

    async def test_006_a_503_that_never_recovers_raises_after_max_retries(self):
        llm_providers._MANAGED_BACKOFF_BASE_SECONDS = 0.0
        wrapper, inner = self._wrapper_around(
            [_fake_status_error(503) for _ in range(llm_providers._MANAGED_MAX_RETRIES + 1)]
        )
        with self.assertRaises(llm_providers.ManagedProviderError) as ctx:
            await wrapper.chat([])
        self.assertEqual(ctx.exception.code, "managed_upstream_unavailable")
        self.assertEqual(inner.chat.call_count, llm_providers._MANAGED_MAX_RETRIES + 1)

    async def test_007_a_429_retries_honoring_retry_after_then_succeeds(self):
        wrapper, inner = self._wrapper_around(
            [_fake_status_error(429, headers={"Retry-After": "0"}), "ok"]
        )
        result = await wrapper.chat([])
        self.assertEqual(result, "ok")
        self.assertEqual(inner.chat.call_count, 2)

    async def test_008_an_unrelated_exception_propagates_unchanged(self):
        wrapper, _ = self._wrapper_around([ValueError("boom")])
        with self.assertRaises(ValueError):
            await wrapper.chat([])


class TestManagedPresetConstruction(unittest.TestCase):
    """SPEC-207 §2.1/§2.4: the locked preset itself -- no config.json
    override reachable (proven above), no hardcoded default model
    (SPEC-207 §2.1's own "must not validate a Managed model name"), and a
    real timeout applied post-construction."""

    def test_001_managed_has_no_default_models_for_either_role(self):
        record = llm_providers._preset_records()["managed"]
        self.assertEqual(record["models"], {})

    def test_002_constructing_managed_with_no_gateway_configured_raises_clearly(self):
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(llm_providers._MANAGED_GATEWAY_ENV_VAR, None)
            record = dict(llm_providers._preset_records()["managed"])
            with self.assertRaises(LLMProviderError):
                llm_providers._build_provider_from_record(record, "a-real-token", "has-standard")

    def test_003_a_configured_gateway_constructs_a_wrapped_client_with_the_real_timeout(self):
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {llm_providers._MANAGED_GATEWAY_ENV_VAR: "http://localhost:9999/v1"}):
            record = llm_providers._resolve_provider_records(None)["managed"]
            client = llm_providers._build_provider_from_record(record, "a-real-token", "has-standard")

        self.assertIsInstance(client, llm_providers._ManagedProviderWrapper)
        self.assertEqual(client._client.timeout, llm_providers._MANAGED_TIMEOUT_SECONDS)

    def test_004_resolve_raises_when_managed_is_bound_with_no_explicit_model(self):
        """SPEC-208 §2.3.2's existing "no model for role" rule, applied to
        managed's deliberately-empty models map -- an alias must be
        supplied explicitly (SPEC-320's job, once it exists), never
        guessed."""
        config = {"provider_roles": {"reasoning": "managed", "fast": "managed"}}
        with self.assertRaises(LLMProviderError):
            resolve("anthropic", "claude-sonnet-4-6", {}, model_role="reasoning", config=config)


if __name__ == '__main__':
    unittest.main()


class TestDeltaConfigAndMovingDefaults(unittest.TestCase):
    """CTX-209.2. Before this, a config entry REPLACED its preset, so the
    first Settings save froze every shipped default into an install
    permanently and no release could move one. Verified against a real
    install on 2026-08-31: all five presets written out verbatim.
    """

    def _preset(self, pid="google"):
        return llm_providers._resolve_provider_records({})[pid]

    def test_030_an_absent_field_resolves_to_the_shipped_value(self):
        """The property the whole design rests on: absent means "use what
        shipped", which is what makes a default movable at all."""
        cfg = {"providers": [{"id": "google"}]}
        got = llm_providers._resolve_provider_records(cfg)["google"]
        self.assertEqual(self._preset()["models"], got["models"])
        self.assertEqual(self._preset()["kind"], got["kind"])

    def test_031_a_delta_overrides_only_the_field_it_names(self):
        cfg = {"providers": [{"id": "google", "base_url": "https://proxy.internal/v1"}]}
        got = llm_providers._resolve_provider_records(cfg)["google"]
        self.assertEqual("https://proxy.internal/v1", got["base_url"])
        self.assertEqual(self._preset()["models"], got["models"])

    def test_032_nested_models_merge_per_key_not_wholesale(self):
        """Replacing `models` outright would re-freeze the role the user
        never touched -- the same defect one level down."""
        cfg = {"providers": [{"id": "google", "models": {"reasoning": "gemini-3-pro"}}]}
        got = llm_providers._resolve_provider_records(cfg)["google"]
        self.assertEqual("gemini-3-pro", got["models"]["reasoning"])
        self.assertEqual(self._preset()["models"]["fast"], got["models"]["fast"])

    def test_033_a_user_added_record_with_no_preset_is_unchanged(self):
        entry = {"id": "mine", "kind": "openai_compat", "base_url": "http://x/v1",
                 "api_key_ref": None, "models": {"reasoning": "m"}, "capabilities": {}}
        got = llm_providers._resolve_provider_records({"providers": [entry]})["mine"]
        self.assertEqual(entry, got)

    def test_034_a_record_identical_to_its_preset_reduces_to_just_its_id(self):
        """So "identical to shipped" has exactly one representation."""
        self.assertEqual({"id": "google"},
                         llm_providers.provider_delta(dict(self._preset()), self._preset()))

    def test_035_a_delta_keeps_only_what_differs(self):
        entry = {**self._preset(), "models": {**self._preset()["models"], "reasoning": "gemini-3-pro"}}
        self.assertEqual({"id": "google", "models": {"reasoning": "gemini-3-pro"}},
                         llm_providers.provider_delta(entry, self._preset()))

    def test_036_delta_then_merge_round_trips_to_the_original(self):
        """The two halves are inverses. If they ever disagree, a save
        silently changes configuration the user did not touch."""
        entry = {**self._preset(), "base_url": "https://proxy/v1",
                 "models": {**self._preset()["models"], "fast": "gemini-flash-8b"}}
        delta = llm_providers.provider_delta(entry, self._preset())
        merged = llm_providers._merge_over_preset(self._preset(), delta)
        self.assertEqual(entry, merged)

    def test_037_a_record_with_no_preset_deltas_to_itself_whole(self):
        entry = {"id": "mine", "kind": "openai_compat", "models": {"reasoning": "m"}}
        self.assertEqual(entry, llm_providers.provider_delta(entry, None))

    def test_038_a_changed_preset_reaches_an_install_that_never_overrode_it(self):
        """The point of the exercise, stated as a test: this is exactly
        what could not happen before."""
        cfg = {"providers": [{"id": "google"}]}
        real = llm_providers._preset_records
        try:
            def shifted():
                records = real()
                records["google"] = {**records["google"],
                                     "models": {"reasoning": "gemini-4", "fast": "gemini-4-flash"}}
                return records
            llm_providers._preset_records = shifted
            got = llm_providers._resolve_provider_records(cfg)["google"]
        finally:
            llm_providers._preset_records = real
        self.assertEqual("gemini-4", got["models"]["reasoning"])

    def test_039_a_full_legacy_record_still_resolves_identically(self):
        """Backwards compatibility: every config.json on disk today holds
        whole records. Reading one must not change behaviour, or the fix
        would break the installs it exists to unfreeze."""
        whole = dict(self._preset())
        self.assertEqual(
            llm_providers._resolve_provider_records({"providers": [whole]})["google"],
            llm_providers._resolve_provider_records({"providers": [{"id": "google"}]})["google"],
        )

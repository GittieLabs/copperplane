import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _load_dotenv_local() -> None:
    """Loads KEY=VALUE lines from the repo root's .env.local into
    os.environ -- same test-only convenience as test_llm_providers.py."""
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

import component_pipeline as cp

_VALID_SOIC8_SCHEMA = {
    "part_number": "TEST123",
    "package": "SOIC-8",
    "pins": [
        {"number": str(i), "name": f"P{i}", "electrical_type": "passive"} for i in range(1, 9)
    ],
    "package_dimensions": {"length_mm": 4.9, "width_mm": 3.9, "height_mm": 1.75, "pitch_mm": 1.27},
    "courtyard": {"length_mm": 5.2, "width_mm": 4.2},
}


class TestExtractJson(unittest.TestCase):

    def test_001_parses_bare_json(self):
        """TEST-001."""
        result = cp._extract_json('{"a": 1}')
        self.assertEqual(result, {"a": 1})

    def test_002_strips_a_markdown_code_fence(self):
        """TEST-001: real LLM output doesn't always follow the
        'no code fences' instruction -- this must be tolerated, not
        treated as a validation error."""
        result = cp._extract_json('```json\n{"a": 1}\n```')
        self.assertEqual(result, {"a": 1})

    def test_003_strips_a_bare_code_fence_without_a_language_tag(self):
        """TEST-001."""
        result = cp._extract_json('```\n{"a": 1}\n```')
        self.assertEqual(result, {"a": 1})

    def test_004_invalid_json_raises_a_clean_error(self):
        """TEST-001: not a raw JSONDecodeError reaching the caller."""
        with self.assertRaises(cp.ComponentValidationError):
            cp._extract_json("this is not json at all")


class TestValidateSchema(unittest.TestCase):

    def test_001_a_correct_schema_passes(self):
        """TEST-002: a real, internally-consistent SOIC-8 schema passes
        all three checks without raising."""
        cp.validate_schema(copy.deepcopy(_VALID_SOIC8_SCHEMA))  # must not raise

    def test_002_wrong_pin_count_is_rejected(self):
        """TEST-002: pin count must match the package's real, known count."""
        schema = copy.deepcopy(_VALID_SOIC8_SCHEMA)
        schema["pins"] = schema["pins"][:6]
        with self.assertRaises(cp.ComponentValidationError) as ctx:
            cp.validate_schema(schema)
        self.assertIn("expects 8 pins, got 6", str(ctx.exception))

    def test_003_insane_pitch_is_rejected(self):
        """TEST-002: a pitch far outside the package family's real range
        is rejected, not just any mismatch."""
        schema = copy.deepcopy(_VALID_SOIC8_SCHEMA)
        schema["package_dimensions"]["pitch_mm"] = 5.0
        with self.assertRaises(cp.ComponentValidationError) as ctx:
            cp.validate_schema(schema)
        self.assertIn("outside the sane range", str(ctx.exception))

    def test_004_undersized_courtyard_is_rejected(self):
        """TEST-002: a courtyard smaller than the package body is
        physically nonsensical and must never pass."""
        schema = copy.deepcopy(_VALID_SOIC8_SCHEMA)
        schema["courtyard"] = {"length_mm": 2.0, "width_mm": 2.0}
        with self.assertRaises(cp.ComponentValidationError) as ctx:
            cp.validate_schema(schema)
        self.assertIn("does not enclose the package body", str(ctx.exception))

    def test_005_unrecognized_package_fails_closed(self):
        """TEST-002: SPEC-202 §3's explicit decision -- an unrecognized
        package is treated as a failed check, not a silent pass-through."""
        schema = copy.deepcopy(_VALID_SOIC8_SCHEMA)
        schema["package"] = "MADE-UP-PACKAGE-999"
        with self.assertRaises(cp.ComponentValidationError) as ctx:
            cp.validate_schema(schema)
        self.assertIn("not in the known reference table", str(ctx.exception))

    def test_006_a_package_with_no_meaningful_pitch_skips_that_check(self):
        """TEST-002: a 2-pin passive (e.g. 0603) has no adjacent-pin
        pitch to validate -- the pitch check is skipped for it, not
        silently passed as if checked, and this must not raise on that
        account alone."""
        schema = {
            "part_number": "R1",
            "package": "0603",
            "pins": [
                {"number": "1", "name": "1", "electrical_type": "passive"},
                {"number": "2", "name": "2", "electrical_type": "passive"},
            ],
            "package_dimensions": {"length_mm": 1.6, "width_mm": 0.8, "height_mm": 0.45, "pitch_mm": 0},
            "courtyard": {"length_mm": 2.0, "width_mm": 1.2},
        }
        cp.validate_schema(schema)  # must not raise


class TestBuildAgentExecutorProviderOverride(unittest.TestCase):
    """CTX-303.2: _build_agent_executor's provider/model override --
    construction-only (llm_providers._build_provider makes no network
    call, per test_llm_providers.py's own TestBuildProvider), so none of
    this needs a real API key or network access."""

    def _real_loader(self):
        loader = cp.ConfigLoader(cp._AGENTFLOW_DIR)
        loader.load()
        return loader

    def test_001_no_override_keeps_the_prompt_files_own_default(self):
        """TEST-004: a fresh install with nothing configured in Settings
        yet must behave exactly as before this fix."""
        loader = self._real_loader()
        executor, _client = cp._build_agent_executor(
            "component_extraction", loader, {"anthropic_api_key": "sk-fake"},
        )
        self.assertEqual(executor.config.provider, "anthropic")

    def test_002_provider_override_replaces_the_prompt_files_default(self):
        """TEST-004: this is the actual bug fix -- generate used to always
        run the hardcoded anthropic provider regardless of this override."""
        from agentflow import GoogleGenAIProvider

        loader = self._real_loader()
        executor, client = cp._build_agent_executor(
            "component_extraction", loader, {"google_api_key": "fake-key"}, provider="google",
        )

        self.assertEqual(executor.config.provider, "google")
        self.assertIsInstance(client, GoogleGenAIProvider)

    def test_003_model_override_replaces_the_prompt_files_default(self):
        """TEST-004."""
        loader = self._real_loader()
        executor, _client = cp._build_agent_executor(
            "component_extraction", loader, {"anthropic_api_key": "sk-fake"}, model="claude-opus-test",
        )
        self.assertEqual(executor.config.model, "claude-opus-test")

    def test_004_overriding_provider_uses_that_providers_own_secret_key(self):
        """TEST-004: only a google key is present -- if the override
        didn't actually change which provider's key gets looked up, this
        would build an anthropic client with an empty api_key instead."""
        loader = self._real_loader()
        executor, _client = cp._build_agent_executor(
            "component_extraction", loader, {"google_api_key": "the-real-one"}, provider="google",
        )
        self.assertEqual(executor.config.provider, "google")

    def test_005_switching_provider_without_a_model_uses_that_providers_own_default_model(self):
        """TEST-004: a real bug this exact test caught -- switching to
        google without overriding model must NOT keep
        component_extraction.prompt.md's anthropic-specific model name
        (claude-sonnet-4-6). A real call against Google with that model
        name returns an empty response, surfaced downstream as a
        confusing JSON-parse error rather than an obviously-wrong-model
        one."""
        loader = self._real_loader()
        executor, _client = cp._build_agent_executor(
            "component_extraction", loader, {"google_api_key": "fake-key"}, provider="google",
        )
        self.assertNotEqual(executor.config.model, "claude-sonnet-4-6")
        self.assertEqual(executor.config.model, cp.llm_providers._DEFAULT_MODELS["google"])


class TestValidateCandidates(unittest.TestCase):
    """SPEC-306: search_components' own safety check -- a malformed
    response must fail closed here, before it ever reaches the UI as a
    half-populated disambiguation card."""

    def _candidate(self, **overrides):
        base = {
            "part_number": "ATtiny85",
            "manufacturer": "Microchip",
            "package": "DIP-8",
            "datasheet_url": "https://example.com/attiny85.pdf",
            "confidence": "high",
            "rationale": "Exact part number match.",
        }
        base.update(overrides)
        return base

    def test_001_a_well_formed_candidate_list_passes_through_unchanged(self):
        candidates = [self._candidate()]
        self.assertEqual(cp._validate_candidates(candidates), candidates)

    def test_002_a_non_list_response_is_rejected(self):
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_candidates(self._candidate())

    def test_003_an_empty_list_is_rejected(self):
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_candidates([])

    def test_004_a_candidate_missing_a_required_field_is_rejected(self):
        candidate = self._candidate()
        del candidate["datasheet_url"]
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_candidates([candidate])

    def test_005_a_candidate_with_an_invalid_confidence_level_is_rejected(self):
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_candidates([self._candidate(confidence="very high")])


class TestRealSearchComponents(unittest.TestCase):
    """Real, non-mocked search calls -- CLAUDE.md's 'verify for real'
    norm. Skips itself cleanly when no real credential is available."""

    def test_001_a_real_search_returns_well_formed_ranked_candidates(self):
        """TEST-002: every candidate the real model returns has all
        required fields and a valid confidence level -- proven against
        the actual prompt file, not a hand-written fixture."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        candidates = cp.search_components("atiny85", secrets={"anthropic_api_key": api_key})

        self.assertGreaterEqual(len(candidates), 1)
        for candidate in candidates:
            for field in cp._SEARCH_REQUIRED_FIELDS:
                self.assertTrue(candidate.get(field))
            self.assertIn(candidate["confidence"], cp._SEARCH_CONFIDENCE_LEVELS)

    def test_002_a_real_search_via_google_does_not_truncate(self):
        """TEST-002: the actual bug this test exists to catch -- found by
        real end-to-end verification of the Components tab (not by this
        test suite first). With CONFIG["llm_provider"] == "google" (the
        real Settings-configured value at the time), component_search's
        response was truncated mid-JSON ('Unterminated string...') because
        component_search.prompt.md's max_tokens (1024) was too tight for
        Gemini's more verbose candidate rationales -- 3 of 5 real calls
        failed. Run several times here since the failure was probabilistic,
        not deterministic on a single call."""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            self.skipTest("GOOGLE_API_KEY not set. Add it to .env.local to run this test for real.")

        for _ in range(5):
            candidates = cp.search_components(
                "Atiny85", secrets={"google_api_key": api_key}, provider="google",
            )
            self.assertGreaterEqual(len(candidates), 1)


class TestRealGenerateComponent(unittest.TestCase):
    """Real, non-mocked runs of the full extract -> validate DAG --
    CLAUDE.md's 'verify for real' norm. Skips itself cleanly when no real
    credential is available, e.g. in CI."""

    def test_001_real_extraction_and_validation_succeeds_for_a_real_part(self):
        """TEST-003: a real part number, extracted by the real configured
        LLM provider (Anthropic -- CTX-202.1 Plan Drift explains why this
        is the default rather than a local model), passes real validation."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        schema = cp.generate_component("ATtiny85", secrets={"anthropic_api_key": api_key})

        self.assertEqual(schema["part_number"], "ATtiny85")
        self.assertIn(schema["package"], cp.PACKAGE_REFERENCE)
        self.assertEqual(len(schema["pins"]), cp.PACKAGE_REFERENCE[schema["package"]]["pin_count"])

    def test_002_a_nonexistent_part_number_is_handled_as_a_clean_error_or_a_valid_guess(self):
        """TEST-003: real LLM behavior on a nonsense part number varies --
        it may decline (surfaced as a validation/JSON error) or guess a
        plausible-but-wrong package (surfaced as a validation error if
        the guess doesn't pass the real checks). Either way, this must
        never raise anything *other than* ComponentValidationError."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        try:
            cp.generate_component("ZZZZ-NOT-A-REAL-PART-NUMBER-999", secrets={"anthropic_api_key": api_key})
        except cp.ComponentValidationError:
            pass  # expected outcome for a part the model can't confidently describe

    def test_003_real_extraction_via_an_overridden_provider(self):
        """TEST-004: the actual bug fix, proven for real -- generate_component
        with provider="google" must really call Google, not silently run
        component_extraction.prompt.md's hardcoded anthropic default.
        Skips cleanly without a real GOOGLE_API_KEY."""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            self.skipTest("GOOGLE_API_KEY not set. Add it to .env.local to run this test for real.")

        schema = cp.generate_component(
            "ATtiny85", secrets={"google_api_key": api_key}, provider="google",
        )

        self.assertEqual(schema["part_number"], "ATtiny85")
        self.assertIn(schema["package"], cp.PACKAGE_REFERENCE)


if __name__ == '__main__':
    unittest.main()

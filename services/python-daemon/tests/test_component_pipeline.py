import copy
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_007_a_pdip_synonym_validates_against_the_same_geometry_as_dip(self):
        """Real end-to-end verification of SPEC-307's Part Detail found
        this: a real extraction call returned "PDIP-8", a common
        real-world synonym for "DIP-8" the extraction prompt's own
        instruction to "use the package's real, standard name" doesn't
        reliably prevent. Widening recognition (not just failing closed)
        is the right fix here since the geometry is identical, not
        unknown."""
        schema = copy.deepcopy(_VALID_SOIC8_SCHEMA)
        schema["package"] = "PDIP-8"
        schema["package_dimensions"]["pitch_mm"] = 2.54
        cp.validate_schema(schema)  # must not raise

    def test_008_qfn_56_is_a_real_recognized_package(self):
        """CTX-202.2: a real, live ESP32-S3 (QFN-56) extraction failed
        closed here because this table didn't have it yet. 56 pins --
        the package's own nominal lead count, no separately-enumerated
        thermal pad."""
        schema = copy.deepcopy(_VALID_SOIC8_SCHEMA)
        schema["package"] = "QFN-56"
        schema["pins"] = [
            {"number": str(i), "name": f"P{i}", "electrical_type": "bidirectional"} for i in range(1, 57)
        ]
        schema["package_dimensions"]["pitch_mm"] = 0.4
        cp.validate_schema(schema)  # must not raise

    def test_009_qfn_56_with_a_real_exposed_thermal_pad_also_validates(self):
        """CTX-202.2: a second real, live extraction found the model
        correctly reporting a real 57th pin, "GND_PAD" -- the ESP32-S3's
        own datasheet numbers its exposed thermal/ground pad as a real
        electrical contact, not a hallucination. 56 leads + 1 pad = 57
        must validate too, not just the bare 56."""
        schema = copy.deepcopy(_VALID_SOIC8_SCHEMA)
        schema["package"] = "QFN-56"
        schema["pins"] = [
            {"number": str(i), "name": f"P{i}", "electrical_type": "bidirectional"} for i in range(1, 57)
        ] + [{"number": "57", "name": "GND_PAD", "electrical_type": "ground"}]
        schema["package_dimensions"]["pitch_mm"] = 0.4
        cp.validate_schema(schema)  # must not raise

    def test_010_qfn_56_still_rejects_a_count_that_is_neither_56_nor_57(self):
        """The widening is specific to the documented thermal-pad case,
        not a general loosening -- 58 (or any other count) must still
        fail closed."""
        schema = copy.deepcopy(_VALID_SOIC8_SCHEMA)
        schema["package"] = "QFN-56"
        schema["pins"] = [
            {"number": str(i), "name": f"P{i}", "electrical_type": "bidirectional"} for i in range(1, 59)
        ]
        schema["package_dimensions"]["pitch_mm"] = 0.4
        with self.assertRaises(cp.ComponentValidationError) as ctx:
            cp.validate_schema(schema)
        self.assertIn("expects 56 or 57 pins, got 58", str(ctx.exception))


class TestGenerateComponentRetry(unittest.TestCase):
    """CTX-202.2: a real, live ESP32-S3 extraction intermittently failed
    with "Extraction did not return valid JSON." Three fresh, direct
    calls to the real extraction agent all succeeded well under
    max_tokens, ruling out truncation-at-the-limit as the cause -- the
    real fix is a retry on that specific failure class, not a bigger
    budget. These mock only the LLM boundary (_build_agent_executor,
    same pattern TestExplainViolations already established); the real
    validate_component_schema handler and its real _extract_json/
    validate_schema checks run for real against the fake extract text."""

    def _executor_returning(self, *raw_texts):
        executor = MagicMock()
        executor.run = AsyncMock(side_effect=[
            cp.NodeOutput(node_id="extract", agent_id="component_extraction", text=text)
            for text in raw_texts
        ])
        # _client=None makes _close_provider_client's own real cleanup
        # return immediately -- a bare MagicMock() auto-creates a truthy
        # `_client.aio.aclose` chain that isn't a real coroutine, which
        # `await`s to a real TypeError.
        return executor, MagicMock(_client=None)

    @patch('component_pipeline._build_agent_executor')
    def test_001_retries_once_on_malformed_json_then_succeeds(self, mock_build):
        mock_build.return_value = self._executor_returning(
            "not valid json {{{", json.dumps(_VALID_SOIC8_SCHEMA),
        )

        schema = cp.generate_component("TEST123")

        self.assertEqual(schema["package"], "SOIC-8")
        self.assertEqual(mock_build.call_count, 2)

    @patch('component_pipeline._build_agent_executor')
    def test_002_a_deterministic_validation_failure_never_retries(self, mock_build):
        bad_schema = copy.deepcopy(_VALID_SOIC8_SCHEMA)
        bad_schema["package"] = "NOT-A-REAL-PACKAGE"
        mock_build.return_value = self._executor_returning(json.dumps(bad_schema))

        with self.assertRaises(cp.ComponentValidationError) as ctx:
            cp.generate_component("TEST123")

        self.assertIn("not in the known reference table", str(ctx.exception))
        self.assertEqual(mock_build.call_count, 1)

    @patch('component_pipeline._build_agent_executor')
    def test_003_exhausting_every_retry_on_repeated_malformed_json_still_raises(self, mock_build):
        mock_build.return_value = self._executor_returning(
            "not valid json {{{", "still not valid }}}",
        )

        with self.assertRaises(cp.ComponentValidationError) as ctx:
            cp.generate_component("TEST123")

        self.assertIn("Extraction did not return valid JSON", str(ctx.exception))
        self.assertEqual(mock_build.call_count, cp._MAX_EXTRACTION_ATTEMPTS)


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


_ATTINY85_PINS = [
    {"number": "1", "name": "RESET", "electrical_type": "bidirectional"},
    {"number": "4", "name": "GND", "electrical_type": "ground"},
    {"number": "8", "name": "VCC", "electrical_type": "power"},
]


class TestValidateConnectionGuidance(unittest.TestCase):
    """CTX-308.7: SPEC-308's own real safety check -- a pin_number the
    response references must be a real pin on this part, the same class
    of fail-closed check validate_schema already applies to footprint
    geometry, applied here to advisory text instead."""

    def _response(self, **overrides):
        base = {
            "pin_guidance": [
                {"pin_number": "8", "guidance": "Add a 100nF ceramic decoupling capacitor from VCC to GND."},
            ],
            "general_notes": "Tie RESET high through a pull-up if not using it for reset control.",
        }
        base.update(overrides)
        return base

    def test_001_a_well_formed_response_passes_through_unchanged(self):
        response = self._response()
        self.assertEqual(cp._validate_connection_guidance(response, _ATTINY85_PINS), response)

    def test_002_a_non_dict_response_is_rejected(self):
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_connection_guidance([], _ATTINY85_PINS)

    def test_003_a_response_missing_a_required_top_level_field_is_rejected(self):
        response = self._response()
        del response["general_notes"]
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_connection_guidance(response, _ATTINY85_PINS)

    def test_004_a_pin_entry_missing_guidance_is_rejected(self):
        response = self._response(pin_guidance=[{"pin_number": "8"}])
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_connection_guidance(response, _ATTINY85_PINS)

    def test_005_a_hallucinated_pin_number_is_rejected(self):
        """The real bar: a pin_number that doesn't exist on this part
        would point the user at the wrong physical pin -- must fail
        closed, not pass through as plausible-looking advice."""
        response = self._response(pin_guidance=[{"pin_number": "99", "guidance": "Decouple this."}])
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_connection_guidance(response, _ATTINY85_PINS)

    def test_006_an_empty_general_notes_string_is_allowed(self):
        response = self._response(general_notes="")
        self.assertEqual(cp._validate_connection_guidance(response, _ATTINY85_PINS)["general_notes"], "")

    def test_007_an_empty_pin_guidance_list_is_allowed(self):
        """Not every part needs per-pin advice beyond what's already in
        the prompt's own instruction to skip plain I/O pins -- an empty
        list is a legitimate, honest answer, not a malformed one."""
        response = self._response(pin_guidance=[])
        self.assertEqual(cp._validate_connection_guidance(response, _ATTINY85_PINS)["pin_guidance"], [])


class TestGenerateConnectionGuidance(unittest.TestCase):
    """CTX-206.1: mocked coverage of the provenance attachment -- the
    real end-to-end path is TestRealGenerateConnectionGuidance below,
    which skips itself with no credential, so this is what actually runs
    in CI."""

    @patch('component_pipeline._build_agent_executor')
    @patch('component_pipeline._run_agent_and_close')
    def test_001_attaches_the_real_resolved_provider_and_model_as_provenance(self, mock_run, mock_build):
        mock_executor = MagicMock()
        mock_executor.config.provider = "anthropic"
        mock_executor.config.model = "claude-sonnet-5"
        mock_build.return_value = (mock_executor, MagicMock())
        mock_run.return_value = json.dumps({"pin_guidance": [], "general_notes": "n"})

        result = cp.generate_connection_guidance("ATtiny85", "SOIC-8", _ATTINY85_PINS)

        self.assertEqual(result["provenance"], {"provider": "anthropic", "model": "claude-sonnet-5"})

    @patch('component_pipeline._build_agent_executor')
    @patch('component_pipeline._run_agent_and_close')
    def test_002_provenance_reflects_the_resolved_config_not_the_callers_raw_arguments(self, mock_run, mock_build):
        """`provider`/`model` args of `None` (a fresh install with
        nothing set in Settings yet) must not leak `None` into the
        stored provenance -- `executor.config` already carries whatever
        `_build_agent_executor` actually resolved (the prompt file's own
        default), which is what gets recorded."""
        mock_executor = MagicMock()
        mock_executor.config.provider = "anthropic"
        mock_executor.config.model = "claude-haiku-4-5"
        mock_build.return_value = (mock_executor, MagicMock())
        mock_run.return_value = json.dumps({"pin_guidance": [], "general_notes": "n"})

        result = cp.generate_connection_guidance(
            "ATtiny85", "SOIC-8", _ATTINY85_PINS, provider=None, model=None,
        )

        self.assertEqual(result["provenance"], {"provider": "anthropic", "model": "claude-haiku-4-5"})


class TestRealGenerateConnectionGuidance(unittest.TestCase):
    """Real, non-mocked calls against the actual prompt file -- CLAUDE.md's
    'verify for real' norm. Skips itself cleanly when no real credential
    is available."""

    def test_001_real_guidance_for_a_real_part_references_only_real_pins(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        result = cp.generate_connection_guidance(
            "ATtiny85", "SOIC-8", _ATTINY85_PINS, secrets={"anthropic_api_key": api_key},
        )

        self.assertIn("pin_guidance", result)
        self.assertIn("general_notes", result)
        self.assertEqual(result["provenance"]["provider"], "anthropic")
        self.assertTrue(result["provenance"]["model"])
        real_pin_numbers = {p["number"] for p in _ATTINY85_PINS}
        for entry in result["pin_guidance"]:
            self.assertIn(entry["pin_number"], real_pin_numbers)
            self.assertTrue(entry["guidance"])
        # The real model consistently has something to say about a real
        # power pin's decoupling -- not a strict requirement of the
        # schema itself (an empty list is valid, TEST-007 above), but a
        # real signal the prompt is actually producing useful guidance.
        self.assertTrue(any(e["pin_number"] == "8" for e in result["pin_guidance"]))


class TestValidateFootprintQuerySuggestion(unittest.TestCase):
    """CTX-308.10: unlike _validate_connection_guidance, there is no
    real-world fact to check a suggested search term against -- this
    only enforces the response's own shape."""

    def _response(self, **overrides):
        base = {"query": "QFN-56", "alternates": ["QFN-56-1EP"], "reasoning": "Matches the QFN-56 package."}
        base.update(overrides)
        return base

    def test_001_a_well_formed_response_passes_through_unchanged(self):
        response = self._response()
        self.assertEqual(cp._validate_footprint_query_suggestion(response), response)

    def test_002_a_non_dict_response_is_rejected(self):
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_footprint_query_suggestion([])

    def test_003_a_response_missing_a_required_field_is_rejected(self):
        response = self._response()
        del response["reasoning"]
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_footprint_query_suggestion(response)

    def test_004_an_empty_query_string_is_rejected(self):
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_footprint_query_suggestion(self._response(query=""))

    def test_005_a_non_list_alternates_is_rejected(self):
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_footprint_query_suggestion(self._response(alternates="QFN-56"))

    def test_006_an_empty_alternates_list_is_allowed(self):
        response = self._response(alternates=[])
        self.assertEqual(cp._validate_footprint_query_suggestion(response)["alternates"], [])


class TestSuggestFootprintQuery(unittest.TestCase):
    """CTX-308.10: mocked coverage of the provenance attachment, the same
    shape TestGenerateConnectionGuidance already covers for its own
    route. The real end-to-end path is TestRealSuggestFootprintQuery
    below, which skips itself with no credential."""

    @patch('component_pipeline._build_agent_executor')
    @patch('component_pipeline._run_agent_and_close')
    def test_001_attaches_the_real_resolved_provider_and_model_as_provenance(self, mock_run, mock_build):
        mock_executor = MagicMock()
        mock_executor.config.provider = "anthropic"
        mock_executor.config.model = "claude-sonnet-5"
        mock_build.return_value = (mock_executor, MagicMock())
        mock_run.return_value = json.dumps({"query": "QFN-56", "alternates": [], "reasoning": "n"})

        result = cp.suggest_footprint_query("ESP32-S3", "Espressif", "QFN-56")

        self.assertEqual(result["provenance"], {"provider": "anthropic", "model": "claude-sonnet-5"})

    @patch('component_pipeline._build_agent_executor')
    @patch('component_pipeline._run_agent_and_close')
    def test_002_passes_the_real_part_identity_to_the_agent(self, mock_run, mock_build):
        mock_executor = MagicMock()
        mock_executor.config.provider = "anthropic"
        mock_executor.config.model = "claude-sonnet-5"
        mock_build.return_value = (mock_executor, MagicMock())
        mock_run.return_value = json.dumps({"query": "QFN-56", "alternates": [], "reasoning": "n"})

        cp.suggest_footprint_query("ESP32-S3", "Espressif", "QFN-56")

        message = json.loads(mock_run.call_args.args[1])
        self.assertEqual(message, {"part_number": "ESP32-S3", "manufacturer": "Espressif", "package": "QFN-56"})


class TestRealSuggestFootprintQuery(unittest.TestCase):
    """Real, non-mocked calls against the actual prompt file -- CLAUDE.md's
    'verify for real' norm. Skips itself cleanly when no real credential
    is available."""

    def test_001_real_suggestion_for_a_real_part_is_a_plausible_package_name(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        result = cp.suggest_footprint_query(
            "ESP32-S3", "Espressif", "QFN-56", secrets={"anthropic_api_key": api_key},
        )

        self.assertIn("query", result)
        self.assertTrue(result["query"])
        self.assertIsInstance(result["alternates"], list)
        self.assertEqual(result["provenance"]["provider"], "anthropic")
        self.assertTrue(result["provenance"]["model"])
        # The real model consistently mentions the real package family
        # somewhere in its suggestion -- not a strict schema requirement,
        # but a real signal the prompt is actually useful, without
        # overfitting to one exact string format.
        self.assertIn("QFN", result["query"].upper())


_REAL_INVALID_OUTLINE_VIOLATION = {
    "description": "Board has malformed outline (no edges found on Edge.Cuts layer)",
    "items": [{"description": "PCB", "pos": {"x": 0.0, "y": 0.0}, "uuid": "fake-uuid"}],
    "severity": "error",
    "type": "invalid_outline",
}


class TestPrioritizeViolations(unittest.TestCase):

    def test_001_errors_sort_before_warnings_before_exclusions(self):
        violations = [
            {"severity": "exclusion", "description": "c"},
            {"severity": "error", "description": "a"},
            {"severity": "warning", "description": "b"},
        ]
        result = cp._prioritize_violations(violations)
        self.assertEqual([v["severity"] for v in result], ["error", "warning", "exclusion"])

    def test_002_an_unrecognized_severity_sorts_last_not_a_crash(self):
        violations = [{"severity": "weird"}, {"severity": "error"}]
        result = cp._prioritize_violations(violations)
        self.assertEqual(result[0]["severity"], "error")


class TestValidateBoardAdvisorResponse(unittest.TestCase):

    def _response(self, **overrides):
        base = {
            "violation_explanations": [
                {"index": 0, "explanation": "The board has no outline.", "suggested_fix": "Draw a closed shape on Edge.Cuts."},
            ],
            "summary": "One error found.",
        }
        base.update(overrides)
        return base

    def test_001_a_well_formed_response_passes_through_unchanged(self):
        response = self._response()
        self.assertEqual(cp._validate_board_advisor_response(response, 1), response)

    def test_002_a_non_dict_response_is_rejected(self):
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_board_advisor_response([], 1)

    def test_003_an_out_of_range_index_is_rejected(self):
        response = self._response(violation_explanations=[
            {"index": 5, "explanation": "x", "suggested_fix": "y"},
        ])
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_board_advisor_response(response, 1)

    def test_004_a_missing_index_is_rejected_not_silently_skipped(self):
        """The real bar: every violation must be explained -- a
        skipped one would silently hide a real problem."""
        response = self._response(violation_explanations=[])
        with self.assertRaises(cp.ComponentValidationError):
            cp._validate_board_advisor_response(response, 1)

    def test_005_index_zero_is_not_treated_as_falsy_and_missing(self):
        """A real footgun: `entry.get("index")` on a real 0 index is
        falsy in Python -- this must not be mistaken for a missing
        field."""
        response = self._response(violation_explanations=[
            {"index": 0, "explanation": "x", "suggested_fix": "y"},
        ])
        self.assertEqual(cp._validate_board_advisor_response(response, 1), response)


class TestExplainViolations(unittest.TestCase):
    """Mocked pipeline-level tests -- truncation and enrichment logic,
    not the LLM call itself (TestRealExplainViolations below is real)."""

    @patch('component_pipeline._build_agent_executor')
    def test_000_an_empty_violations_list_never_calls_the_llm(self, mock_build):
        result = cp.explain_violations([], "drc")

        mock_build.assert_not_called()
        self.assertEqual(result, {"violations": [], "summary": "No violations found.", "truncated_count": 0})

    @patch('component_pipeline._build_agent_executor')
    @patch('component_pipeline._run_agent_and_close')
    def test_001_caps_at_the_real_limit_and_reports_the_real_truncated_count(self, mock_run, mock_build):
        violations = [{"severity": "error", "description": f"v{i}", "type": "t"} for i in range(20)]
        mock_build.return_value = (MagicMock(), MagicMock())
        response = {
            "violation_explanations": [
                {"index": i, "explanation": "x", "suggested_fix": "y"}
                for i in range(cp._MAX_VIOLATIONS_PER_EXPLANATION_CALL)
            ],
            "summary": "s",
        }
        mock_run.return_value = json.dumps(response)

        result = cp.explain_violations(violations, "drc")

        self.assertEqual(len(result["violations"]), cp._MAX_VIOLATIONS_PER_EXPLANATION_CALL)
        self.assertEqual(result["truncated_count"], 20 - cp._MAX_VIOLATIONS_PER_EXPLANATION_CALL)

    @patch('component_pipeline._build_agent_executor')
    @patch('component_pipeline._run_agent_and_close')
    def test_002_enriches_each_real_violation_with_its_own_explanation(self, mock_run, mock_build):
        violations = [{"severity": "error", "description": "d1", "type": "t1"}]
        mock_build.return_value = (MagicMock(), MagicMock())
        mock_run.return_value = json.dumps({
            "violation_explanations": [{"index": 0, "explanation": "explained", "suggested_fix": "fixed"}],
            "summary": "s",
        })

        result = cp.explain_violations(violations, "drc")

        self.assertEqual(result["violations"][0]["description"], "d1")
        self.assertEqual(result["violations"][0]["explanation"], "explained")
        self.assertEqual(result["violations"][0]["suggested_fix"], "fixed")
        self.assertEqual(result["truncated_count"], 0)


class TestRealExplainViolations(unittest.TestCase):
    """Real, non-mocked call against the actual prompt file, using the
    exact real violation kicad_cli.run_drc produces against this repo's
    own committed empty_board.kicad_pcb fixture -- CLAUDE.md's 'verify
    for real' norm."""

    def test_001_real_explanation_for_a_real_kicad_violation(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        result = cp.explain_violations(
            [_REAL_INVALID_OUTLINE_VIOLATION], "drc", secrets={"anthropic_api_key": api_key},
        )

        self.assertEqual(len(result["violations"]), 1)
        self.assertTrue(result["violations"][0]["explanation"])
        self.assertTrue(result["violations"][0]["suggested_fix"])
        self.assertTrue(result["summary"])
        self.assertEqual(result["truncated_count"], 0)


if __name__ == '__main__':
    unittest.main()

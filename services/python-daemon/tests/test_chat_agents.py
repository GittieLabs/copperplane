import json
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentflow.types import NodeOutput

import chat_agents
import library_store as store


_VALID_PROVENANCE = {
    field: {"source": "datasheet_pdf", "model": None, "confidence": 1.0}
    for field in store.PART_PROVENANCE_REQUIRED_FIELDS
}


class ChatAgentsTestCase(unittest.TestCase):
    """CTX-206.4 (SPEC-206 §2.3): real file I/O against a real, isolated
    temp storage root, same as `LibraryStoreTestCase` in
    `test_library_store.py` -- these resolvers read real Part/Project/
    thread records, not mocks."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        store.configure(storage_root=self._tmpdir.name)

    def tearDown(self):
        store.configure(storage_root=None)
        self._tmpdir.cleanup()

    def _save_part(self, **overrides):
        part = {
            "part_id": "ATtiny85", "manufacturer": "Microchip", "package": "SOIC-8",
            "pins": [{"number": "8", "name": "VCC", "electrical_type": "power"}],
            "datasheet_url": "https://example.com/x.pdf", "package_dimensions": {}, "courtyard": {},
            "provenance": _VALID_PROVENANCE,
        }
        part.update(overrides)
        return store.save_part(part)


class TestResolveDatasheetPage(ChatAgentsTestCase):

    def test_001_resolves_when_the_cached_file_hash_matches(self):
        self._save_part()
        path = store.datasheet_cache_path("ATtiny85")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4 real bytes")
        real_hash = store.content_hash_of_file(path)

        ref = {"kind": "datasheet_page", "part_id": "ATtiny85", "page": 3, "content_hash": real_hash}

        self.assertTrue(chat_agents.resolve_source_ref(ref))

    def test_002_does_not_resolve_when_the_hash_is_stale(self):
        self._save_part()
        path = store.datasheet_cache_path("ATtiny85")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4 real bytes")

        ref = {
            "kind": "datasheet_page", "part_id": "ATtiny85", "page": 3,
            "content_hash": "not-the-real-hash",
        }

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_003_does_not_resolve_when_no_datasheet_is_cached_at_all(self):
        ref = {
            "kind": "datasheet_page", "part_id": "ATtiny85", "page": 1,
            "content_hash": "irrelevant",
        }

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_004_a_malformed_ref_missing_content_hash_does_not_resolve(self):
        ref = {"kind": "datasheet_page", "part_id": "ATtiny85", "page": 1}

        self.assertFalse(chat_agents.resolve_source_ref(ref))


class TestResolveGuidanceItem(ChatAgentsTestCase):

    def test_001_resolves_a_real_cited_quote(self):
        self._save_part(design_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "content_hash": "hash1", "document_revision": None,
            "categories": {"reset": [{"quote": "Tie RESET high.", "page": 3, "category": "reset"}]},
            "category_summaries": {},
        })

        ref = {
            "kind": "guidance_item", "part_id": "ATtiny85", "category": "reset",
            "quote": "Tie RESET high.", "content_hash": "hash1",
        }

        self.assertTrue(chat_agents.resolve_source_ref(ref))

    def test_002_does_not_resolve_a_stale_content_hash(self):
        self._save_part(design_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "content_hash": "hash1", "document_revision": None,
            "categories": {"reset": [{"quote": "Tie RESET high.", "page": 3, "category": "reset"}]},
            "category_summaries": {},
        })

        ref = {
            "kind": "guidance_item", "part_id": "ATtiny85", "category": "reset",
            "quote": "Tie RESET high.", "content_hash": "a-newer-hash",
        }

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_003_does_not_resolve_a_quote_that_was_never_actually_cited(self):
        self._save_part(design_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "content_hash": "hash1", "document_revision": None,
            "categories": {"reset": [{"quote": "Tie RESET high.", "page": 3, "category": "reset"}]},
            "category_summaries": {},
        })

        ref = {
            "kind": "guidance_item", "part_id": "ATtiny85", "category": "reset",
            "quote": "This quote was never generated.", "content_hash": "hash1",
        }

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_004_does_not_resolve_when_the_part_has_no_design_guidance_at_all(self):
        self._save_part()

        ref = {
            "kind": "guidance_item", "part_id": "ATtiny85", "category": "reset",
            "quote": "x", "content_hash": "hash1",
        }

        self.assertFalse(chat_agents.resolve_source_ref(ref))


class TestResolveConnectionGuidance(ChatAgentsTestCase):

    def test_001_resolves_a_real_referenced_pin(self):
        self._save_part(connection_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "pins_hash": "irrelevant",
            "pin_guidance": [{"pin_number": "8", "guidance": "Decouple with 100nF."}],
            "general_notes": "", "provenance": {"provider": "anthropic", "model": "claude-sonnet-5"},
        })

        ref = {"kind": "connection_guidance", "part_id": "ATtiny85", "pin_number": "8"}

        self.assertTrue(chat_agents.resolve_source_ref(ref))

    def test_002_does_not_resolve_an_unreferenced_pin(self):
        self._save_part(connection_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "pins_hash": "irrelevant",
            "pin_guidance": [{"pin_number": "8", "guidance": "Decouple with 100nF."}],
            "general_notes": "", "provenance": {"provider": "anthropic", "model": "claude-sonnet-5"},
        })

        ref = {"kind": "connection_guidance", "part_id": "ATtiny85", "pin_number": "1"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_003_does_not_resolve_when_the_part_has_no_connection_guidance_at_all(self):
        self._save_part()

        ref = {"kind": "connection_guidance", "part_id": "ATtiny85", "pin_number": "8"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))


class TestResolvePartField(ChatAgentsTestCase):

    def test_001_resolves_a_real_top_level_field(self):
        self._save_part()

        ref = {"kind": "part_field", "part_id": "ATtiny85", "field": "manufacturer"}

        self.assertTrue(chat_agents.resolve_source_ref(ref))

    def test_002_does_not_resolve_a_field_that_does_not_exist(self):
        self._save_part()

        ref = {"kind": "part_field", "part_id": "ATtiny85", "field": "not_a_real_field"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_003_does_not_resolve_when_the_part_itself_does_not_exist(self):
        ref = {"kind": "part_field", "part_id": "NoSuchPart", "field": "manufacturer"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))


class TestResolveChatTurn(ChatAgentsTestCase):

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})

    def test_001_resolves_a_real_turn_in_a_real_thread(self):
        path = store._project_thread_path("weather-pcb", "schematic")
        store._write_thread_turns(path, [{"turn_id": "t1", "role": "user", "content": "hi"}])

        ref = {"kind": "chat_turn", "scope": "project", "scope_id": "weather-pcb:schematic", "turn_id": "t1"}

        self.assertTrue(chat_agents.resolve_source_ref(ref))

    def test_002_does_not_resolve_a_turn_id_that_does_not_exist(self):
        path = store._project_thread_path("weather-pcb", "schematic")
        store._write_thread_turns(path, [{"turn_id": "t1", "role": "user", "content": "hi"}])

        ref = {"kind": "chat_turn", "scope": "project", "scope_id": "weather-pcb:schematic", "turn_id": "t2"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_003_does_not_resolve_a_malformed_scope_id(self):
        ref = {"kind": "chat_turn", "scope": "project", "scope_id": "weather-pcb", "turn_id": "t1"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))


class TestResolveProjectIntent(ChatAgentsTestCase):

    def test_001_resolves_when_the_project_has_a_real_intent(self):
        store.save_project({"name": "weather-pcb", "intent": "A weatherproof outdoor PCB."})

        ref = {"kind": "project_intent", "project_name": "weather-pcb"}

        self.assertTrue(chat_agents.resolve_source_ref(ref))

    def test_002_does_not_resolve_a_never_set_intent(self):
        store.save_project({"name": "weather-pcb"})

        ref = {"kind": "project_intent", "project_name": "weather-pcb"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_003_does_not_resolve_an_explicitly_cleared_empty_intent(self):
        store.save_project({"name": "weather-pcb", "intent": ""})

        ref = {"kind": "project_intent", "project_name": "weather-pcb"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_004_does_not_resolve_when_the_project_does_not_exist(self):
        ref = {"kind": "project_intent", "project_name": "no-such-project"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))


class TestDeferredKinds(ChatAgentsTestCase):
    """SPEC-206 §2.3 names these two kinds, but neither has real backing
    state yet -- see this module's own docstring for why. A
    well-formed ref of either kind never resolves, matching the
    contract for any other unresolvable reference."""

    def test_001_check_finding_never_resolves_yet(self):
        ref = {"kind": "check_finding", "project_name": "weather-pcb", "area": "schematic", "finding_id": "f1"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_002_note_never_resolves_yet(self):
        ref = {"kind": "note", "scope": "project", "scope_id": "weather-pcb:overview", "note_id": "n1"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))


class TestResolveSourceRefMalformedInput(ChatAgentsTestCase):

    def test_001_an_unknown_kind_does_not_resolve(self):
        self.assertFalse(chat_agents.resolve_source_ref({"kind": "not-a-real-kind"}))

    def test_002_a_non_dict_ref_does_not_resolve(self):
        self.assertFalse(chat_agents.resolve_source_ref(["not", "a", "dict"]))

    def test_003_a_ref_with_no_kind_at_all_does_not_resolve(self):
        self.assertFalse(chat_agents.resolve_source_ref({"part_id": "ATtiny85"}))


class TestValidateSourceRefs(ChatAgentsTestCase):

    def test_001_splits_real_and_dropped_refs_and_counts_the_dropped_ones(self):
        self._save_part()
        good_ref = {"kind": "part_field", "part_id": "ATtiny85", "field": "manufacturer"}
        bad_ref_1 = {"kind": "part_field", "part_id": "ATtiny85", "field": "not_real"}
        bad_ref_2 = {"kind": "not-a-real-kind"}

        resolved, dropped = chat_agents.validate_source_refs([good_ref, bad_ref_1, bad_ref_2])

        self.assertEqual(resolved, [good_ref])
        self.assertEqual(dropped, 2)

    def test_002_an_empty_list_resolves_to_empty_with_zero_dropped(self):
        resolved, dropped = chat_agents.validate_source_refs([])

        self.assertEqual(resolved, [])
        self.assertEqual(dropped, 0)


class TestExtractSelfReported(unittest.TestCase):
    """CTX-206.6 (SPEC-206 §2.3's "both, layered" design): parses the
    model's own trailing citation block. Never raises on malformed
    model output -- degrades to general_practice=True, the honest
    default when nothing can be confirmed as grounded."""

    def test_001_a_well_formed_block_is_parsed_and_stripped(self):
        text = (
            'The answer is 3.3V.\n\n'
            '<<<CITATIONS>>>\n'
            '{"sources": [{"kind": "part_field", "part_id": "ATtiny85", "field": "manufacturer"}], '
            '"general_practice": false}\n'
            '<<<END_CITATIONS>>>'
        )
        visible, sources, general_practice = chat_agents._extract_self_reported(text)

        self.assertEqual(visible, "The answer is 3.3V.")
        self.assertEqual(sources, [{"kind": "part_field", "part_id": "ATtiny85", "field": "manufacturer"}])
        self.assertFalse(general_practice)

    def test_002_no_block_at_all_defaults_to_general_practice_true(self):
        visible, sources, general_practice = chat_agents._extract_self_reported("Just an answer, no block.")

        self.assertEqual(visible, "Just an answer, no block.")
        self.assertEqual(sources, [])
        self.assertTrue(general_practice)

    def test_003_malformed_json_inside_the_block_degrades_safely(self):
        text = "An answer.\n<<<CITATIONS>>>not real json<<<END_CITATIONS>>>"

        visible, sources, general_practice = chat_agents._extract_self_reported(text)

        self.assertEqual(visible, "An answer.")
        self.assertEqual(sources, [])
        self.assertTrue(general_practice)

    def test_004_a_json_array_instead_of_an_object_degrades_safely(self):
        text = 'An answer.\n<<<CITATIONS>>>[1, 2, 3]<<<END_CITATIONS>>>'

        visible, sources, general_practice = chat_agents._extract_self_reported(text)

        self.assertEqual(sources, [])
        self.assertTrue(general_practice)

    def test_005_a_non_list_sources_value_degrades_to_an_empty_list(self):
        text = 'An answer.\n<<<CITATIONS>>>{"sources": "not a list", "general_practice": false}<<<END_CITATIONS>>>'

        visible, sources, general_practice = chat_agents._extract_self_reported(text)

        self.assertEqual(sources, [])
        self.assertFalse(general_practice)


class TestEnrichSourceRef(ChatAgentsTestCase):
    """CTX-206.6: fills in the one field the model cannot compute itself
    -- guidance_item's real content_hash."""

    def test_001_fills_in_the_real_content_hash_for_a_guidance_item(self):
        self._save_part(design_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "content_hash": "abc123", "document_revision": None,
            "categories": {"power": [{"quote": "Add a 100nF cap.", "page": 4, "category": "power"}]},
            "category_summaries": {},
        })
        ref = {"kind": "guidance_item", "part_id": "ATtiny85", "category": "power", "quote": "Add a 100nF cap."}

        enriched = chat_agents._enrich_source_ref(ref)

        self.assertEqual(enriched["content_hash"], "abc123")

    def test_002_other_kinds_pass_through_unchanged(self):
        ref = {"kind": "part_field", "part_id": "ATtiny85", "field": "manufacturer"}

        self.assertEqual(chat_agents._enrich_source_ref(ref), ref)

    def test_003_a_nonexistent_part_passes_through_unchanged_rather_than_raising(self):
        ref = {"kind": "guidance_item", "part_id": "does-not-exist", "category": "power", "quote": "x"}

        self.assertEqual(chat_agents._enrich_source_ref(ref), ref)

    def test_004_a_part_with_no_design_guidance_at_all_passes_through_unchanged(self):
        self._save_part()
        ref = {"kind": "guidance_item", "part_id": "ATtiny85", "category": "power", "quote": "x"}

        self.assertEqual(chat_agents._enrich_source_ref(ref), ref)


class TestMechanicalSourceRefs(unittest.TestCase):
    """CTX-206.6: the real, tool-trace-derived half of SPEC-206 §2.3's
    "both, layered" design -- never trusts the model's own account of
    what it read."""

    def test_001_derives_one_ref_per_real_page_read(self):
        events = [{
            "tool": "datasheet.read_pages", "is_error": False,
            "input": {"part_id": "ATtiny85", "pages": [4, 5]},
            "raw_result": {"content_hash": "abc123", "pages": [{"page": 4, "text": "..."}, {"page": 5, "text": "..."}]},
        }]

        refs = chat_agents._mechanical_source_refs(events)

        self.assertEqual(refs, [
            {"kind": "datasheet_page", "part_id": "ATtiny85", "page": 4, "content_hash": "abc123"},
            {"kind": "datasheet_page", "part_id": "ATtiny85", "page": 5, "content_hash": "abc123"},
        ])

    def test_002_ignores_a_different_tool(self):
        events = [{"tool": "library.load_part", "is_error": False, "input": {}, "raw_result": {}}]

        self.assertEqual(chat_agents._mechanical_source_refs(events), [])

    def test_003_ignores_an_errored_tool_call(self):
        events = [{
            "tool": "datasheet.read_pages", "is_error": True,
            "input": {"part_id": "ATtiny85"}, "raw_result": None,
        }]

        self.assertEqual(chat_agents._mechanical_source_refs(events), [])

    def test_004_ignores_a_result_missing_a_content_hash(self):
        events = [{
            "tool": "datasheet.read_pages", "is_error": False,
            "input": {"part_id": "ATtiny85"}, "raw_result": {"pages": [{"page": 4}]},
        }]

        self.assertEqual(chat_agents._mechanical_source_refs(events), [])


class TestAssembleContext(ChatAgentsTestCase):
    """CTX-206.6 (SPEC-206 §2.8's "transcript assembly"): real context
    per area, built from real Part/Project records -- no mocking of
    library_store itself."""

    def test_001_components_area_includes_the_real_part_and_project_intent(self):
        self._save_part()
        store.save_project({"name": "weather-pcb", "intent": "A weatherproof outdoor PCB."})

        context = json.loads(chat_agents._assemble_context("components", "part", "ATtiny85", "weather-pcb"))

        self.assertEqual(context["part"]["part_id"], "ATtiny85")
        self.assertEqual(context["project_intent"], "A weatherproof outdoor PCB.")

    def test_002_components_area_omits_project_intent_when_no_project_name_is_given(self):
        self._save_part()

        context = json.loads(chat_agents._assemble_context("components", "part", "ATtiny85", None))

        self.assertNotIn("project_intent", context)

    def test_003_overview_area_includes_intent_last_results_export_history_and_referenced_parts(self):
        self._save_part()
        store.save_project({
            "name": "weather-pcb", "intent": "A weatherproof outdoor PCB.",
            "last_results": {"enclosure": {"wall_thickness_mm": 2}},
            "export_history": [{"area": "enclosure", "dest_path": "/x", "exported_at": "2026-01-01"}],
            "parts": ["ATtiny85"],
        })

        context = json.loads(chat_agents._assemble_context("overview", "project", "weather-pcb:overview", None))

        self.assertEqual(context["project_intent"], "A weatherproof outdoor PCB.")
        self.assertEqual(context["last_results"], {"enclosure": {"wall_thickness_mm": 2}})
        self.assertEqual(len(context["export_history"]), 1)
        self.assertEqual(context["parts"], [{"part_id": "ATtiny85", "manufacturer": "Microchip", "package": "SOIC-8"}])

    def test_004_schematic_area_reports_not_checked_this_session_when_no_last_results_entry_exists(self):
        store.save_project({"name": "weather-pcb", "parts": []})

        context = json.loads(chat_agents._assemble_context("schematic", "project", "weather-pcb:schematic", None))

        self.assertIn("No ERC check result is available this session.", context["check_status"])

    def test_005_pcb_area_includes_full_part_guidance_not_just_identity(self):
        self._save_part(connection_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "pins_hash": "h", "general_notes": "n",
            "pin_guidance": [{"pin_number": "8", "guidance": "Decouple with 100nF."}],
            "provenance": {"provider": "anthropic", "model": "claude-sonnet-5"},
        })
        store.save_project({"name": "weather-pcb", "parts": ["ATtiny85"]})

        context = json.loads(chat_agents._assemble_context("pcb", "project", "weather-pcb:pcb", None))

        self.assertEqual(context["parts"][0]["connection_guidance"]["pin_guidance"][0]["pin_number"], "8")

    def test_006_enclosure_area_includes_generated_parameters_when_present(self):
        store.save_project({
            "name": "weather-pcb", "last_results": {"enclosure": {"wall_thickness_mm": 2, "standoff_height_mm": 5}},
        })

        context = json.loads(chat_agents._assemble_context("enclosure", "project", "weather-pcb:enclosure", None))

        self.assertEqual(context["enclosure_parameters"], {"wall_thickness_mm": 2, "standoff_height_mm": 5})

    def test_007_enclosure_area_reports_none_when_nothing_was_ever_generated(self):
        store.save_project({"name": "weather-pcb"})

        context = json.loads(chat_agents._assemble_context("enclosure", "project", "weather-pcb:enclosure", None))

        self.assertIsNone(context["enclosure_parameters"])


class TestSend(ChatAgentsTestCase):
    """CTX-206.6 (SPEC-206 §2.5): the real `chat.send` route body --
    real router/agent config loading, mocked LLM call only."""

    _NO_CITATIONS_TEXT = 'Hello.\n<<<CITATIONS>>>\n{"sources": [], "general_practice": true}\n<<<END_CITATIONS>>>'

    def _send(self, scope, scope_id, area, message, response_text=_NO_CITATIONS_TEXT, **kwargs):
        with patch('chat_agents.llm_providers._build_provider', return_value=MagicMock()), \
             patch('chat_agents.llm_providers._close_provider_client', new=AsyncMock()), \
             patch('chat_agents.AgentExecutor') as MockExecutor:
            MockExecutor.return_value.run = AsyncMock(
                return_value=NodeOutput(node_id="n", agent_id="a", text=response_text)
            )
            return chat_agents.send(scope, scope_id, area, message, secrets={"anthropic_api_key": "fake"}, **kwargs)

    def test_001_an_unknown_area_is_a_hard_error_raised_before_anything_is_appended(self):
        store.save_project({"name": "weather-pcb"})

        with self.assertRaises(chat_agents.UnknownChatAreaError):
            self._send("project", "weather-pcb:overview", "not-a-real-area", "hi")

        self.assertEqual(store.load_thread("project", "weather-pcb:overview"), [])

    def test_002_each_of_the_five_real_areas_routes_to_its_own_real_agent(self):
        store.save_project({"name": "weather-pcb", "parts": []})
        self._save_part()
        cases = [
            ("project", "weather-pcb:overview", "overview", "chat_overview"),
            ("part", "ATtiny85", "components", "chat_components"),
            ("project", "weather-pcb:schematic", "schematic", "chat_schematic"),
            ("project", "weather-pcb:pcb", "pcb", "chat_pcb"),
            ("project", "weather-pcb:enclosure", "enclosure", "chat_enclosure"),
        ]
        for scope, scope_id, area, expected_agent in cases:
            with self.subTest(area=area):
                turn = self._send(scope, scope_id, area, "hi")
                self.assertEqual(turn["agent"], expected_agent)

    def test_003_appends_the_user_turn_then_the_assistant_turn_in_order(self):
        store.save_project({"name": "weather-pcb"})

        self._send("project", "weather-pcb:overview", "overview", "What should I do next?")

        turns = store.load_thread("project", "weather-pcb:overview")
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0]["role"], "user")
        self.assertEqual(turns[0]["content"], "What should I do next?")
        self.assertEqual(turns[1]["role"], "assistant")
        self.assertEqual(turns[1]["content"], "Hello.")

    def test_004_the_assistant_turn_carries_real_provenance_and_a_fresh_turn_id(self):
        store.save_project({"name": "weather-pcb"})

        turn = self._send("project", "weather-pcb:overview", "overview", "hi")

        self.assertEqual(turn["provenance"]["provider"], "anthropic")
        self.assertTrue(turn["turn_id"])
        self.assertTrue(turn["timestamp"])

    def test_005_self_reported_and_mechanical_sources_are_both_validated_and_merged(self):
        self._save_part(design_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "content_hash": "abc123", "document_revision": None,
            "categories": {"power": [{"quote": "Add a 100nF cap.", "page": 4, "category": "power"}]},
            "category_summaries": {},
        })
        response_text = (
            'Add a 100nF cap.\n<<<CITATIONS>>>\n'
            '{"sources": [{"kind": "guidance_item", "part_id": "ATtiny85", "category": "power", '
            '"quote": "Add a 100nF cap."}], "general_practice": false}\n<<<END_CITATIONS>>>'
        )

        turn = self._send("part", "ATtiny85", "components", "how do I decouple this?", response_text=response_text)

        self.assertEqual(turn["sources"], [{
            "kind": "guidance_item", "part_id": "ATtiny85", "category": "power",
            "quote": "Add a 100nF cap.", "content_hash": "abc123",
        }])
        self.assertEqual(turn["sources_dropped"], 0)
        self.assertFalse(turn["general_practice"])

    def test_006_an_unresolvable_self_reported_source_is_dropped_and_counted(self):
        self._save_part()
        response_text = (
            'x\n<<<CITATIONS>>>\n'
            '{"sources": [{"kind": "part_field", "part_id": "ATtiny85", "field": "not_a_real_field"}], '
            '"general_practice": false}\n<<<END_CITATIONS>>>'
        )

        turn = self._send("part", "ATtiny85", "components", "hi", response_text=response_text)

        self.assertEqual(turn["sources"], [])
        self.assertEqual(turn["sources_dropped"], 1)

    def test_007_the_second_turn_in_a_conversation_sees_the_first_as_real_history_not_duplicated(self):
        store.save_project({"name": "weather-pcb"})

        with patch('chat_agents.llm_providers._build_provider', return_value=MagicMock()), \
             patch('chat_agents.llm_providers._close_provider_client', new=AsyncMock()), \
             patch('chat_agents.AgentExecutor') as MockExecutor:
            MockExecutor.return_value.run = AsyncMock(
                return_value=NodeOutput(node_id="n", agent_id="a", text=self._NO_CITATIONS_TEXT)
            )
            chat_agents.send("project", "weather-pcb:overview", "overview", "first message", secrets={})
            chat_agents.send("project", "weather-pcb:overview", "overview", "second message", secrets={})

            second_call_kwargs = MockExecutor.return_value.run.call_args_list[1].kwargs
            history = second_call_kwargs["history"]

        # Exactly the first turn's own user+assistant pair -- never the
        # second call's own new user message counted twice.
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].content, "first message")


if __name__ == '__main__':
    unittest.main()

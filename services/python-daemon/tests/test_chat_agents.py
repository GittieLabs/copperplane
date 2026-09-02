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
    """SPEC-206 §2.3 names this kind, but it has no real backing state
    yet -- see this module's own docstring for why. A well-formed ref
    never resolves, matching the contract for any other unresolvable
    reference. `note` used to be deferred the same way -- CTX-206.8
    gave it a real resolver, tested for real in TestResolveNote below."""

    def test_001_check_finding_never_resolves_yet(self):
        ref = {"kind": "check_finding", "project_name": "weather-pcb", "area": "schematic", "finding_id": "f1"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))


class TestResolveNote(ChatAgentsTestCase):
    """CTX-206.8 (SPEC-206 §2.7): a real note only ever lives on a Part
    or a Project."""

    def test_001_resolves_a_real_note_on_a_part(self):
        self._save_part(notes=[{"note_id": "n1", "text": "Decouple with 100nF.", "sources": [], "created_at": "t"}])
        ref = {"kind": "note", "scope": "part", "scope_id": "ATtiny85", "note_id": "n1"}

        self.assertTrue(chat_agents.resolve_source_ref(ref))

    def test_002_resolves_a_real_note_on_a_project(self):
        store.save_project({"name": "weather-pcb", "notes": [{"note_id": "n1", "text": "x"}]})
        ref = {"kind": "note", "scope": "project", "scope_id": "weather-pcb", "note_id": "n1"}

        self.assertTrue(chat_agents.resolve_source_ref(ref))

    def test_003_does_not_resolve_a_note_id_that_does_not_exist(self):
        self._save_part(notes=[{"note_id": "n1", "text": "x"}])
        ref = {"kind": "note", "scope": "part", "scope_id": "ATtiny85", "note_id": "not-real"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_004_does_not_resolve_when_the_part_has_no_notes_at_all(self):
        self._save_part()
        ref = {"kind": "note", "scope": "part", "scope_id": "ATtiny85", "note_id": "n1"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_005_does_not_resolve_an_unknown_scope(self):
        ref = {"kind": "note", "scope": "not-a-real-scope", "scope_id": "x", "note_id": "n1"}

        self.assertFalse(chat_agents.resolve_source_ref(ref))

    def test_006_does_not_resolve_when_the_named_part_does_not_exist(self):
        ref = {"kind": "note", "scope": "part", "scope_id": "does-not-exist", "note_id": "n1"}

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
    what it read.

    Fixtures use `NodeOutput.metadata["tool_calls"]`'s real shape
    (agentflow>=0.10.0): `result` is the tool's plain JSON string return
    value (matching `tool_registry._wrap_route`'s real
    `json.dumps(result)`), not a pre-parsed dict."""

    def test_001_derives_one_ref_per_real_page_read(self):
        tool_calls = [{
            "name": "datasheet.read_pages", "is_error": False,
            "input": {"part_id": "ATtiny85", "pages": [4, 5]},
            "result": json.dumps({"content_hash": "abc123", "pages": [{"page": 4, "text": "..."}, {"page": 5, "text": "..."}]}),
        }]

        refs = chat_agents._mechanical_source_refs(tool_calls)

        self.assertEqual(refs, [
            {"kind": "datasheet_page", "part_id": "ATtiny85", "page": 4, "content_hash": "abc123"},
            {"kind": "datasheet_page", "part_id": "ATtiny85", "page": 5, "content_hash": "abc123"},
        ])

    def test_002_ignores_a_different_tool(self):
        tool_calls = [{"name": "library.load_part", "is_error": False, "input": {}, "result": "{}"}]

        self.assertEqual(chat_agents._mechanical_source_refs(tool_calls), [])

    def test_003_ignores_an_errored_tool_call(self):
        tool_calls = [{
            "name": "datasheet.read_pages", "is_error": True,
            "input": {"part_id": "ATtiny85"}, "result": "Tool error: boom",
        }]

        self.assertEqual(chat_agents._mechanical_source_refs(tool_calls), [])

    def test_004_ignores_a_result_missing_a_content_hash(self):
        tool_calls = [{
            "name": "datasheet.read_pages", "is_error": False,
            "input": {"part_id": "ATtiny85"}, "result": json.dumps({"pages": [{"page": 4}]}),
        }]

        self.assertEqual(chat_agents._mechanical_source_refs(tool_calls), [])

    def test_005_ignores_a_result_that_is_not_valid_json(self):
        """The result string comes from a real tool call, but a defensive
        guard against a non-JSON or non-dict result (e.g. a plain-text
        error string that isn't the `Tool error: ...` shape) -- never
        raises, just drops it like any other unresolvable ref."""
        tool_calls = [{
            "name": "datasheet.read_pages", "is_error": False,
            "input": {"part_id": "ATtiny85"}, "result": "not json at all",
        }]

        self.assertEqual(chat_agents._mechanical_source_refs(tool_calls), [])

    def test_006_ignores_a_result_that_is_valid_json_but_not_an_object(self):
        tool_calls = [{
            "name": "datasheet.read_pages", "is_error": False,
            "input": {"part_id": "ATtiny85"}, "result": json.dumps([1, 2, 3]),
        }]

        self.assertEqual(chat_agents._mechanical_source_refs(tool_calls), [])


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

    def test_004_schematic_area_says_no_check_could_be_run_without_a_linked_project(self):
        """Was "not checked this session", back when the check block was read
        from stored results. The check now RUNS on request (`kicad-cli` reads
        a closed file), so the only reason to have no result is that there is
        no file to check -- and that must never read as a clean design."""
        store.save_project({"name": "weather-pcb", "parts": []})

        context = json.loads(chat_agents._assemble_context("schematic", "project", "weather-pcb:schematic", None))

        self.assertIn("no KiCad project linked", context["check_status"])
        self.assertIn("NOT a clean result", context["check_status"])

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

    def _send(self, scope, scope_id, area, message, response_text=_NO_CITATIONS_TEXT, metadata=None, **kwargs):
        with patch('chat_agents.llm_providers._build_provider', return_value=MagicMock()), \
             patch('chat_agents.llm_providers._close_provider_client', new=AsyncMock()), \
             patch('chat_agents.AgentExecutor') as MockExecutor:
            MockExecutor.return_value.run = AsyncMock(
                return_value=NodeOutput(node_id="n", agent_id="a", text=response_text, metadata=metadata or {})
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

    def test_007_a_real_datasheet_read_pages_tool_call_produces_a_mechanical_source_and_a_tool_calls_summary(self):
        """End-to-end through `send()`: `NodeOutput.metadata["tool_calls"]`
        (the real agentflow>=0.10.0 shape) flows into both the mechanical
        `datasheet_page` source and the turn's own `tool_calls` summary --
        no EventBus wiring involved, since AgentExecutor.run() surfaces
        this directly on its own return value now."""
        self._save_part()
        path = store.datasheet_cache_path("ATtiny85")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4 real bytes")
        real_hash = store.content_hash_of_file(path)
        tool_result = json.dumps({"content_hash": real_hash, "pages": [{"page": 4, "text": "..."}]})
        metadata = {"tool_calls": [{
            "name": "datasheet.read_pages", "input": {"part_id": "ATtiny85", "pages": [4]},
            "result": tool_result, "is_error": False,
        }]}

        turn = self._send("part", "ATtiny85", "components", "what does page 4 say?", metadata=metadata)

        self.assertEqual(turn["sources"], [
            {"kind": "datasheet_page", "part_id": "ATtiny85", "page": 4, "content_hash": real_hash},
        ])
        self.assertEqual(turn["tool_calls"], [{
            "name": "datasheet.read_pages", "input": {"part_id": "ATtiny85", "pages": [4]},
            "result_digest": tool_result,
        }])

    def test_008_the_second_turn_in_a_conversation_sees_the_first_as_real_history_not_duplicated(self):
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


class TestReview(ChatAgentsTestCase):
    """CTX-319.1 (SPEC-319 §2.1): the real `chat.review` route body --
    real router/agent config loading, mocked LLM call only, mirroring
    `TestSend`'s own convention exactly."""

    _NO_FINDINGS_TEXT = '<<<FINDINGS>>>\n[]\n<<<END_FINDINGS>>>'

    def _review(self, scope, scope_id, area, response_text=_NO_FINDINGS_TEXT, metadata=None, **kwargs):
        with patch('chat_agents.llm_providers._build_provider', return_value=MagicMock()), \
             patch('chat_agents.llm_providers._close_provider_client', new=AsyncMock()), \
             patch('chat_agents.AgentExecutor') as MockExecutor:
            MockExecutor.return_value.run = AsyncMock(
                return_value=NodeOutput(node_id="n", agent_id="a", text=response_text, metadata=metadata or {})
            )
            findings = chat_agents.review(scope, scope_id, area, secrets={"anthropic_api_key": "fake"}, **kwargs)
            return findings, MockExecutor

    def test_001_an_unknown_area_is_a_hard_error(self):
        with self.assertRaises(chat_agents.UnknownChatAreaError):
            self._review("project", "weather-pcb:overview", "not-a-real-area")

    def test_002_each_of_the_five_real_areas_routes_to_its_own_real_agent(self):
        store.save_project({"name": "weather-pcb", "parts": []})
        self._save_part()
        cases = [
            ("project", "weather-pcb:overview", "overview"),
            ("part", "ATtiny85", "components"),
            ("project", "weather-pcb:schematic", "schematic"),
            ("project", "weather-pcb:pcb", "pcb"),
            ("project", "weather-pcb:enclosure", "enclosure"),
        ]
        for scope, scope_id, area in cases:
            with self.subTest(area=area):
                findings, MockExecutor = self._review(scope, scope_id, area)
                self.assertEqual(findings, [])
                MockExecutor.assert_called_once()

    def test_003_an_empty_findings_block_is_a_normal_empty_list_not_an_error(self):
        store.save_project({"name": "weather-pcb"})

        findings, _ = self._review("project", "weather-pcb:overview", "overview")

        self.assertEqual(findings, [])

    def test_004_a_real_finding_is_parsed_with_area_filled_in_server_side(self):
        store.save_project({"name": "weather-pcb"})
        response_text = (
            '<<<FINDINGS>>>\n'
            '[{"severity": "warning", "title": "No project intent set", '
            '"detail": "Agents will answer generically until one is added.", '
            '"sources": [], "general_practice": true}]\n<<<END_FINDINGS>>>'
        )

        findings, _ = self._review("project", "weather-pcb:overview", "overview", response_text=response_text)

        self.assertEqual(findings, [{
            "severity": "warning",
            "title": "No project intent set",
            "detail": "Agents will answer generically until one is added.",
            "sources": [],
            "general_practice": True,
            "area": "overview",
        }])

    def test_005_a_malformed_finding_is_dropped_not_shown_broken(self):
        store.save_project({"name": "weather-pcb"})
        response_text = (
            '<<<FINDINGS>>>\n'
            '[{"severity": "not-a-real-severity", "title": "x", "detail": "y"}, '
            '{"severity": "info", "title": "", "detail": "y"}, '
            '{"severity": "info", "title": "x", "detail": ""}, '
            '{"title": "missing severity and detail"}]\n<<<END_FINDINGS>>>'
        )

        findings, _ = self._review("project", "weather-pcb:overview", "overview", response_text=response_text)

        self.assertEqual(findings, [])

    def test_006_self_reported_sources_are_validated_and_enriched_per_finding(self):
        self._save_part(design_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "content_hash": "abc123", "document_revision": None,
            "categories": {"power": [{"quote": "Add a 100nF cap.", "page": 4, "category": "power"}]},
            "category_summaries": {},
        })
        response_text = (
            '<<<FINDINGS>>>\n'
            '[{"severity": "suggestion", "title": "Add decoupling", "detail": "Add a 100nF cap near VCC.", '
            '"sources": [{"kind": "guidance_item", "part_id": "ATtiny85", "category": "power", '
            '"quote": "Add a 100nF cap."}], "general_practice": false}]\n<<<END_FINDINGS>>>'
        )

        findings, _ = self._review("part", "ATtiny85", "components", response_text=response_text)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["sources"], [{
            "kind": "guidance_item", "part_id": "ATtiny85", "category": "power",
            "quote": "Add a 100nF cap.", "content_hash": "abc123",
        }])
        self.assertFalse(findings[0]["general_practice"])

    def test_007_an_unresolvable_self_reported_source_is_dropped_from_the_finding(self):
        self._save_part()
        response_text = (
            '<<<FINDINGS>>>\n'
            '[{"severity": "info", "title": "x", "detail": "y", '
            '"sources": [{"kind": "part_field", "part_id": "ATtiny85", "field": "not_a_real_field"}], '
            '"general_practice": false}]\n<<<END_FINDINGS>>>'
        )

        findings, _ = self._review("part", "ATtiny85", "components", response_text=response_text)

        self.assertEqual(findings[0]["sources"], [])

    def test_008_a_real_datasheet_read_pages_tool_call_produces_a_mechanical_source_on_the_finding(self):
        self._save_part()
        path = store.datasheet_cache_path("ATtiny85")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4 real bytes")
        real_hash = store.content_hash_of_file(path)
        tool_result = json.dumps({"content_hash": real_hash, "pages": [{"page": 4, "text": "..."}]})
        metadata = {"tool_calls": [{
            "name": "datasheet.read_pages", "input": {"part_id": "ATtiny85", "pages": [4]},
            "result": tool_result, "is_error": False,
        }]}
        response_text = (
            '<<<FINDINGS>>>\n'
            '[{"severity": "info", "title": "x", "detail": "y", "sources": [], '
            '"general_practice": false}]\n<<<END_FINDINGS>>>'
        )

        findings, _ = self._review(
            "part", "ATtiny85", "components", response_text=response_text, metadata=metadata,
        )

        self.assertEqual(findings[0]["sources"], [
            {"kind": "datasheet_page", "part_id": "ATtiny85", "page": 4, "content_hash": real_hash},
        ])

    def test_009_never_appends_to_the_conversation_thread(self):
        store.save_project({"name": "weather-pcb"})

        self._review("project", "weather-pcb:overview", "overview")

        self.assertEqual(store.load_thread("project", "weather-pcb:overview"), [])

    def test_010_calls_with_no_history_even_when_the_thread_already_has_turns(self):
        store.save_project({"name": "weather-pcb"})
        store.append_thread_turn(
            "project", "weather-pcb:overview",
            {"turn_id": "t1", "role": "user", "content": "an earlier real question"},
        )

        _, MockExecutor = self._review("project", "weather-pcb:overview", "overview")

        self.assertEqual(MockExecutor.return_value.run.call_args.kwargs["history"], [])

    def test_011_the_gated_confirmation_required_tool_is_excluded_from_the_registry_it_receives(self):
        store.save_project({"name": "weather-pcb"})

        with patch('chat_agents.llm_providers._build_provider', return_value=MagicMock()), \
             patch('chat_agents.llm_providers._close_provider_client', new=AsyncMock()), \
             patch('chat_agents.AgentExecutor') as MockExecutor:
            MockExecutor.return_value.run = AsyncMock(
                return_value=NodeOutput(node_id="n", agent_id="a", text=self._NO_FINDINGS_TEXT)
            )
            chat_agents.review("project", "weather-pcb:overview", "overview", secrets={})

            passed_tools = MockExecutor.call_args.kwargs["tools"]
            tool_names = {t["name"] for t in passed_tools.list_tools()}
            self.assertNotIn("kicad.inject_component", tool_names)


class TestPromoteTurn(ChatAgentsTestCase):
    """CTX-206.8 (SPEC-206 §2.7): "the actual answer to answer
    consistency" -- moves a settled assistant turn out of a transcript
    and into a durable note."""

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})
        store.append_thread_turn(
            "project", "weather-pcb:overview",
            {"turn_id": "t1", "role": "user", "content": "How should I decouple this part?"},
        )
        store.append_thread_turn(
            "project", "weather-pcb:overview",
            {
                "turn_id": "t2", "role": "assistant", "content": "Add a 100nF ceramic capacitor near VCC.",
                "sources": [{"kind": "project_intent", "project_name": "weather-pcb"}],
                "sources_dropped": 0, "general_practice": False, "tool_calls": [],
                "provenance": {"provider": "anthropic", "model": "claude-sonnet-5"},
            },
        )

    def test_001_promotes_a_real_assistant_turn_onto_a_project(self):
        note = chat_agents.promote_turn("project", "weather-pcb:overview", "t2", "project", "weather-pcb")

        self.assertEqual(note["text"], "Add a 100nF ceramic capacitor near VCC.")
        self.assertEqual(note["sources"], [{"kind": "project_intent", "project_name": "weather-pcb"}])
        self.assertEqual(note["origin"], {"scope": "project", "scope_id": "weather-pcb:overview", "turn_id": "t2"})
        self.assertEqual(note["provenance"], {"provider": "anthropic", "model": "claude-sonnet-5"})
        reloaded = store.load_project("weather-pcb")
        self.assertEqual(reloaded["notes"], [note])

    def test_002_promotes_onto_a_part_instead_when_target_scope_is_part(self):
        self._save_part()

        note = chat_agents.promote_turn("project", "weather-pcb:overview", "t2", "part", "ATtiny85")

        reloaded = store.load_part("ATtiny85")
        self.assertEqual(reloaded["notes"], [note])

    def test_003_marks_the_source_turn_with_the_real_new_note_id(self):
        note = chat_agents.promote_turn("project", "weather-pcb:overview", "t2", "project", "weather-pcb")

        turns = store.load_thread("project", "weather-pcb:overview")
        promoted_turn = next(t for t in turns if t["turn_id"] == "t2")
        self.assertEqual(promoted_turn["promoted_note_id"], note["note_id"])

    def test_004_rejects_promoting_a_user_turn(self):
        with self.assertRaises(chat_agents.NotAssistantTurnError):
            chat_agents.promote_turn("project", "weather-pcb:overview", "t1", "project", "weather-pcb")

    def test_005_rejects_an_unknown_turn_id(self):
        with self.assertRaises(chat_agents.TurnNotFoundError):
            chat_agents.promote_turn("project", "weather-pcb:overview", "not-real", "project", "weather-pcb")

    def test_006_rejects_an_unknown_target_scope(self):
        with self.assertRaises(chat_agents.UnknownPromotionTargetError):
            chat_agents.promote_turn("project", "weather-pcb:overview", "t2", "not-a-real-scope", "weather-pcb")

    def test_007_the_promoted_note_resolves_as_a_real_source_ref(self):
        note = chat_agents.promote_turn("project", "weather-pcb:overview", "t2", "project", "weather-pcb")

        ref = {"kind": "note", "scope": "project", "scope_id": "weather-pcb", "note_id": note["note_id"]}
        self.assertTrue(chat_agents.resolve_source_ref(ref))

    def test_008_re_promoting_the_same_turn_to_a_second_target_is_allowed(self):
        self._save_part()

        chat_agents.promote_turn("project", "weather-pcb:overview", "t2", "project", "weather-pcb")
        chat_agents.promote_turn("project", "weather-pcb:overview", "t2", "part", "ATtiny85")

        self.assertEqual(len(store.load_project("weather-pcb")["notes"]), 1)
        self.assertEqual(len(store.load_part("ATtiny85")["notes"]), 1)


if __name__ == '__main__':
    unittest.main()


class TestLiveCheckStatusNote(unittest.TestCase):
    """The review agents' check block is computed NOW, not read from storage.

    Persisting results and warning about their age was the obvious repair and
    is the wrong one: the maintainer pointed out that a stored finding goes
    stale in ways this app cannot detect -- he can run DRC in KiCad, fix
    everything, and never tell us -- so re-running the review would "still
    just show cached and potentially stale results". `kicad-cli` reads a
    CLOSED file in about two seconds, so there is nothing worth caching."""

    _FILES = {"schematic_path": "/p/s.kicad_sch", "pcb_path": "/p/b.kicad_pcb"}

    def test_001_an_unlinked_project_is_not_reported_as_clean(self):
        note = chat_agents._check_status_note({"name": "P"}, "pcb")

        self.assertIn("no KiCad project linked", note)
        self.assertIn("NOT a clean result", note)

    def test_002_a_real_drc_run_reaches_the_agent(self):
        report = {
            "violations": [],
            "unconnected_items": [{"description": "Missing connection",
                                   "severity": "error", "type": "unconnected_items"}],
            "schematic_parity": [],
        }
        with patch.object(chat_agents.kicad_project, "resolve_project", return_value=self._FILES), \
             patch.object(chat_agents.kicad_cli, "run_drc", return_value=report):
            note = json.loads(
                chat_agents._check_status_note({"kicad_project_path": "/p/p.kicad_pro"}, "pcb")
            )

        self.assertTrue(note["ran_now"])
        self.assertEqual(note["unconnected_count"], 1)
        self.assertEqual(note["findings"][0]["description"], "Missing connection")

    def test_003_the_drc_run_asks_for_schematic_parity(self):
        with patch.object(chat_agents.kicad_project, "resolve_project", return_value=self._FILES), \
             patch.object(chat_agents.kicad_cli, "run_drc",
                          return_value={"violations": []}) as run_drc:
            chat_agents._check_status_note({"kicad_project_path": "/p/p.kicad_pro"}, "pcb")

        run_drc.assert_called_once_with("/p/b.kicad_pcb", schematic_parity=True)

    def test_004_erc_violations_are_flattened_across_sheets(self):
        erc = {"sheets": [
            {"path": "/", "violations": [{"description": "a", "severity": "error", "type": "x"}]},
            {"path": "/sub", "violations": [{"description": "b", "severity": "warning", "type": "y"}]},
        ]}
        with patch.object(chat_agents.kicad_project, "resolve_project", return_value=self._FILES), \
             patch.object(chat_agents.kicad_cli, "run_erc", return_value=erc):
            note = json.loads(
                chat_agents._check_status_note({"kicad_project_path": "/p/p.kicad_pro"}, "schematic")
            )

        self.assertEqual(note["violation_count"], 2)

    def test_005_a_failed_check_is_never_mistaken_for_a_clean_one(self):
        """'We could not check' and 'we checked and it is fine' must not look
        the same to the agent -- the whole complaint about the old behaviour."""
        with patch.object(chat_agents.kicad_project, "resolve_project",
                          side_effect=OSError("kicad-cli not found")):
            note = chat_agents._check_status_note({"kicad_project_path": "/p/p.kicad_pro"}, "pcb")

        self.assertIn("could not be run", note)
        self.assertIn("NOT a clean result", note)

    def test_006_a_clean_board_says_a_check_actually_ran(self):
        with patch.object(chat_agents.kicad_project, "resolve_project", return_value=self._FILES), \
             patch.object(chat_agents.kicad_cli, "run_drc", return_value={"violations": []}):
            note = json.loads(
                chat_agents._check_status_note({"kicad_project_path": "/p/p.kicad_pro"}, "pcb")
            )

        self.assertTrue(note["ran_now"])
        self.assertEqual(note["findings"], [])
        self.assertIn("checked_at", note)

    def test_007_the_note_says_it_read_the_file_not_the_editor(self):
        with patch.object(chat_agents.kicad_project, "resolve_project", return_value=self._FILES), \
             patch.object(chat_agents.kicad_cli, "run_drc", return_value={"violations": []}):
            note = json.loads(
                chat_agents._check_status_note({"kicad_project_path": "/p/p.kicad_pro"}, "pcb")
            )

        self.assertIn("unsaved changes", note["read_from"])

    def test_008_a_huge_finding_list_is_capped_but_the_counts_are_not(self):
        many = [{"description": f"v{i}", "severity": "error", "type": "unconnected_items"}
                for i in range(200)]
        with patch.object(chat_agents.kicad_project, "resolve_project", return_value=self._FILES), \
             patch.object(chat_agents.kicad_cli, "run_drc",
                          return_value={"violations": [], "unconnected_items": many}):
            note = json.loads(
                chat_agents._check_status_note({"kicad_project_path": "/p/p.kicad_pro"}, "pcb")
            )

        self.assertEqual(len(note["findings"]), 25)
        self.assertEqual(note["findings_omitted"], 175)
        self.assertEqual(note["unconnected_count"], 200)


class TestCheckFindingSourceRef(unittest.TestCase):
    """A citation of a finding the check itself just produced.

    `check_finding` resolved to `_resolve_deferred` (always False) from
    SPEC-206 until now -- correct while the check block was read from stored
    results nothing ever wrote, wrong the moment it started carrying a real
    DRC run. Every such citation was dropped, so `sources` came back empty
    and the UI fell through to a general-practice note beneath a finding
    that opened "DRC detected 2 missing connections"."""

    def test_001_a_citation_of_a_real_checked_file_resolves(self):
        with tempfile.NamedTemporaryFile(suffix=".kicad_pcb") as f:
            self.assertTrue(
                chat_agents.resolve_source_ref(
                    {"kind": "check_finding", "source_path": f.name}
                )
            )

    def test_002_a_citation_of_a_file_that_is_not_there_is_dropped(self):
        self.assertFalse(
            chat_agents.resolve_source_ref(
                {"kind": "check_finding", "source_path": "/nope/never.kicad_pcb"}
            )
        )

    def test_003_a_citation_with_no_path_is_dropped(self):
        self.assertFalse(chat_agents.resolve_source_ref({"kind": "check_finding"}))
        self.assertFalse(
            chat_agents.resolve_source_ref({"kind": "check_finding", "source_path": ""})
        )

    def test_004_it_travels_through_validate_source_refs(self):
        """The path a real response takes -- resolve_source_ref is only
        reached through here."""
        with tempfile.NamedTemporaryFile(suffix=".kicad_pcb") as f:
            resolved, dropped = chat_agents.validate_source_refs([
                {"kind": "check_finding", "source_path": f.name},
                {"kind": "check_finding", "source_path": "/nope/x.kicad_pcb"},
            ])

        self.assertEqual(len(resolved), 1)
        self.assertEqual(dropped, 1)


class TestFindingLocations(unittest.TestCase):
    """`items` used to be dropped from every finding as "KiCad's internal
    uuids, which mean nothing to a user". Only `uuid` is: the rest names the
    pad, the net, the component and the millimetre position -- the answer to
    "where is it". Reported as "we didn't even tell the user where to find the
    problems on the board."."""

    _REAL = {
        "description": "Missing connection between items",
        "severity": "error",
        "type": "unconnected_items",
        "items": [
            {"description": "PTH pad 2 [Net-(U2-THRES)] of U2",
             "pos": {"x": 99.695, "y": 68.23}, "uuid": "316be86b"},
            {"description": "Track [Net-(U2-THRES)] on F.Cu, length 1.5556 mm",
             "pos": {"x": 107.315, "y": 70.77}, "uuid": "8568ccf9"},
        ],
    }

    def test_001_locations_reach_the_agent_with_their_positions(self):
        out = chat_agents._finding_for_agent(self._REAL)

        self.assertEqual(len(out["locations"]), 2)
        self.assertEqual(out["locations"][0]["description"], "PTH pad 2 [Net-(U2-THRES)] of U2")
        self.assertEqual(out["locations"][0]["pos_mm"], {"x": 99.695, "y": 68.23})

    def test_002_the_uuid_is_not_carried(self):
        """The one part of an item that really is meaningless to a reader."""
        out = chat_agents._finding_for_agent(self._REAL)

        self.assertNotIn("uuid", out["locations"][0])

    def test_003_a_finding_with_no_items_still_works(self):
        out = chat_agents._finding_for_agent({"description": "x", "severity": "warning"})

        self.assertEqual(out["locations"], [])

    def test_004_an_item_with_no_description_is_skipped(self):
        out = chat_agents._finding_for_agent(
            {"description": "x", "items": [{"uuid": "only-a-uuid"}]}
        )

        self.assertEqual(out["locations"], [])

    def test_005_ignored_checks_reach_the_agent(self):
        """A board can look clean because a check is switched off."""
        report = {"violations": [], "ignored_checks": [
            {"key": "missing_courtyard", "description": "Footprint has no courtyard defined"},
        ]}
        with patch.object(chat_agents.kicad_project, "resolve_project",
                          return_value={"pcb_path": "/p/b.kicad_pcb", "schematic_path": None}), \
             patch.object(chat_agents.kicad_cli, "run_drc", return_value=report):
            note = json.loads(
                chat_agents._check_status_note({"kicad_project_path": "/p/p.kicad_pro"}, "pcb")
            )

        self.assertEqual(note["ignored_checks"][0]["key"], "missing_courtyard")


class TestAnUnreadableReviewIsNotACleanBoard(unittest.TestCase):
    """Reported: "Reviewed -- nothing worth flagging" on a board with two
    unconnected errors, right after a build where the same review had found
    them. The model had written prose and no FINDINGS block, `_extract_findings`
    returned [] for that exactly as it does for a genuinely clean board, and
    the UI could not tell the two apart."""

    def _review_returning(self, text):
        async def fake_dispatch(*a, **kw):
            return {"text": text, "tool_calls_raw": [], "model": "m", "provider": "p"}
        with patch.object(chat_agents, "_dispatch", side_effect=fake_dispatch), \
             patch.object(chat_agents.tool_registry, "build_tool_registry", return_value={}):
            return chat_agents.review("project", "P:pcb", "pcb", project_name="P")

    def test_001_the_checks_own_findings_survive_the_prose_failing(self):
        """"Try again" was the first answer here and it was wrong: the check
        is on demand and deterministic, it has already run, and only the
        model's formatting failed. Re-running would recompute findings this
        process is already holding."""
        with patch.object(chat_agents, "_findings_from_check_alone", return_value=[
            {"severity": "warning", "title": "Missing connection between items",
             "detail": "raw", "sources": [], "general_practice": False, "area": "pcb"},
        ]):
            findings = self._review_returning("prose, and no block at all")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["title"], "Missing connection between items")

    def test_002_it_raises_only_when_there_is_no_check_to_fall_back_on(self):
        """An unlinked project, or an area with no check: the one case where
        the area really has not been assessed."""
        with patch.object(chat_agents, "_findings_from_check_alone", return_value=None), \
             self.assertRaises(chat_agents.ReviewFormatError) as ctx:
            self._review_returning("prose only")

        self.assertIn("NOT a clean result", str(ctx.exception))
        # No longer tells the user to re-run: re-running would not help.
        self.assertNotIn("Try again", str(ctx.exception))

    def test_003_an_explicitly_empty_block_is_still_an_honest_clean_review(self):
        """The other half: a model that DID answer in the format and found
        nothing must not be turned into an error."""
        findings = self._review_returning("<<<FINDINGS>>>\n[]\n<<<END_FINDINGS>>>")

        self.assertEqual(findings, [])

    def test_004_a_malformed_block_is_still_read_as_present(self):
        """Present-but-unparseable drops to no findings rather than raising:
        the model did answer in the format, and the per-entry validation above
        already governs what survives."""
        findings = self._review_returning("<<<FINDINGS>>>\nnot json\n<<<END_FINDINGS>>>")

        self.assertEqual(findings, [])

    def test_005_real_findings_still_come_through(self):
        block = (
            '<<<FINDINGS>>>\n'
            '[{"severity": "warning", "title": "Unconnected items", '
            '"detail": "Two pads are not joined.", "sources": [], "general_practice": false}]\n'
            '<<<END_FINDINGS>>>'
        )
        findings = self._review_returning(block)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["title"], "Unconnected items")


class TestFindingsFromCheckAlone(unittest.TestCase):
    """The check's own findings, rendered as review findings with no model
    prose at all."""

    _NOTE = {
        "check": "DRC", "ran_now": True, "source_path": "/p/b.kicad_pcb",
        "findings": [{
            "description": "Missing connection between items",
            "severity": "error", "type": "unconnected_items",
            "locations": [
                {"description": "PTH pad 2 [Net-(U2-THRES)] of U2", "pos_mm": {"x": 1, "y": 2}},
            ],
        }],
    }

    def _run(self, note, project=None):
        with patch.object(chat_agents.library_store, "load_project",
                          return_value=project if project is not None else {"name": "P"}), \
             patch.object(chat_agents, "_check_status_note", return_value=json.dumps(note)):
            return chat_agents._findings_from_check_alone("pcb", "P:pcb", "P")

    def test_001_a_finding_carries_where_it_is(self):
        out = self._run(self._NOTE)

        self.assertIn("PTH pad 2 [Net-(U2-THRES)] of U2", out[0]["detail"])

    def test_002_it_says_the_explanation_is_missing_rather_than_pretending(self):
        out = self._run(self._NOTE)

        self.assertIn("explanation could not be generated", out[0]["detail"])

    def test_003_it_is_not_marked_general_practice(self):
        """It came straight from KiCad's check, which is the opposite of
        general engineering knowledge."""
        out = self._run(self._NOTE)

        self.assertFalse(out[0]["general_practice"])

    def test_004_it_cites_the_file_the_check_read(self):
        with patch("os.path.exists", return_value=True):
            out = self._run(self._NOTE)

        self.assertEqual(out[0]["sources"][0]["kind"], "check_finding")

    def test_005_a_clean_check_falls_back_to_an_honestly_empty_review(self):
        out = self._run({**self._NOTE, "findings": []})

        self.assertEqual(out, [])

    def test_006_a_check_that_could_not_run_is_not_a_fallback(self):
        """`_check_status_note` returns prose, not JSON, when it could not run
        -- that is the case where the board really has not been assessed."""
        with patch.object(chat_agents.library_store, "load_project", return_value={"name": "P"}), \
             patch.object(chat_agents, "_check_status_note",
                          return_value="No DRC check could be run: ..."):
            self.assertIsNone(chat_agents._findings_from_check_alone("pcb", "P:pcb", "P"))

    def test_007_an_area_with_no_check_has_nothing_to_fall_back_on(self):
        self.assertIsNone(
            chat_agents._findings_from_check_alone("enclosure", "P:enclosure", "P")
        )

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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


if __name__ == '__main__':
    unittest.main()

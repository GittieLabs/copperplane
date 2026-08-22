import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import chat_agents
import context_index as ci
import library_store as store


_VALID_PROVENANCE = {
    field: {"source": "datasheet_pdf", "model": None, "confidence": 1.0}
    for field in store.PART_PROVENANCE_REQUIRED_FIELDS
}


class ContextIndexTestCase(unittest.TestCase):
    """Real file I/O against a real, isolated temp storage root, and a
    real SQLite/FTS5 index file under it -- same convention as
    LibraryStoreTestCase/ChatAgentsTestCase, no mocking of SQLite
    itself. FTS5 is real on this dev machine (confirmed directly before
    writing this suite); CI's own real availability is exactly what
    `TestFts5Available` below checks for, not assumed."""

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


class TestFts5Available(unittest.TestCase):
    """No storage root needed -- this probes an in-memory database."""

    def test_001_returns_a_real_bool_not_an_exception(self):
        self.assertIn(ci.fts5_available(), (True, False))


class TestRebuildIndex(ContextIndexTestCase):

    def test_001_indexes_a_real_guidance_item_as_a_resolvable_source_ref(self):
        self._save_part(design_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "content_hash": "abc123", "document_revision": None,
            "categories": {"power": [{"quote": "Add a 100nF decoupling capacitor.", "page": 4, "category": "power"}]},
            "category_summaries": {},
        })

        result = ci.rebuild_index()

        self.assertGreater(result["chunk_count"], 0)
        chunks = ci.search("decoupling capacitor")
        guidance_chunks = [c for c in chunks if c.kind == "guidance_item"]
        self.assertEqual(len(guidance_chunks), 1)
        self.assertTrue(chat_agents.resolve_source_ref(guidance_chunks[0].source_ref))

    def test_002_a_category_summary_is_indexed_as_a_resolvable_part_field_not_a_fake_guidance_item(self):
        """A summary isn't a literal quote from `categories[category]`'s
        own items -- citing it as guidance_item would produce a
        SourceRef that could never resolve."""
        self._save_part(design_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "content_hash": "abc123", "document_revision": None,
            "categories": {"power": [{"quote": "Add a 100nF cap.", "page": 4, "category": "power"}]},
            "category_summaries": {"power": "Decouple every power pin with a small ceramic capacitor."},
        })

        ci.rebuild_index()

        chunks = ci.search("Decouple every power pin")
        summary_chunks = [c for c in chunks if "Decouple every power pin" in c.body]
        self.assertEqual(len(summary_chunks), 1)
        self.assertEqual(summary_chunks[0].source_ref, {
            "kind": "part_field", "part_id": "ATtiny85", "field": "design_guidance",
        })
        self.assertTrue(chat_agents.resolve_source_ref(summary_chunks[0].source_ref))

    def test_003_indexes_real_connection_guidance_per_pin(self):
        self._save_part(connection_guidance={
            "generated_at": "2026-01-01T00:00:00Z", "pins_hash": "h", "general_notes": "Tie unused pins high.",
            "pin_guidance": [{"pin_number": "8", "guidance": "Decouple with a 100nF ceramic capacitor."}],
            "provenance": {"provider": "anthropic", "model": "claude-sonnet-5"},
        })

        ci.rebuild_index()

        chunks = ci.search("Decouple with a 100nF ceramic capacitor")
        pin_chunks = [c for c in chunks if c.kind == "connection_guidance"]
        self.assertEqual(pin_chunks[0].source_ref, {
            "kind": "connection_guidance", "part_id": "ATtiny85", "pin_number": "8",
        })
        self.assertTrue(chat_agents.resolve_source_ref(pin_chunks[0].source_ref))

    def test_004_indexes_part_identity_fields_and_pin_names(self):
        self._save_part()

        ci.rebuild_index()

        manufacturer_chunks = [c for c in ci.search("Microchip") if c.body == "Microchip"]
        self.assertEqual(manufacturer_chunks[0].source_ref, {
            "kind": "part_field", "part_id": "ATtiny85", "field": "manufacturer",
        })
        pin_name_chunks = [c for c in ci.search("VCC") if c.body == "VCC"]
        self.assertEqual(pin_name_chunks[0].source_ref["field"], "pins")

    def test_005_indexes_real_project_intent(self):
        store.save_project({"name": "weather-pcb", "intent": "A weatherproof outdoor sensor board."})

        ci.rebuild_index()

        chunks = ci.search("weatherproof outdoor sensor")
        intent_chunks = [c for c in chunks if c.kind == "project_intent"]
        self.assertEqual(intent_chunks[0].source_ref, {"kind": "project_intent", "project_name": "weather-pcb"})
        self.assertTrue(chat_agents.resolve_source_ref(intent_chunks[0].source_ref))

    def test_006_a_part_or_project_with_nothing_generated_yet_indexes_cleanly(self):
        self._save_part()
        store.save_project({"name": "weather-pcb"})

        result = ci.rebuild_index()

        self.assertGreater(result["chunk_count"], 0)  # identity fields still index

    def test_007_reports_the_real_fts5_status(self):
        result = ci.rebuild_index()

        self.assertEqual(result["fts5"], ci.fts5_available())

    def test_008_a_deleted_index_file_is_a_supported_recovery_action(self):
        self._save_part()
        ci.rebuild_index()
        os.remove(ci._index_path())

        self.assertTrue(ci.needs_rebuild())
        ci.rebuild_index()
        self.assertTrue(os.path.isfile(ci._index_path()))


class TestNeedsRebuild(ContextIndexTestCase):

    def test_001_true_before_the_index_file_exists_at_all(self):
        self.assertTrue(ci.needs_rebuild())

    def test_002_false_immediately_after_a_real_rebuild_with_no_further_changes(self):
        self._save_part()
        ci.rebuild_index()

        self.assertFalse(ci.needs_rebuild())

    def test_003_true_after_a_real_file_change_newer_than_last_indexed(self):
        self._save_part()
        ci.rebuild_index()

        self._save_part(manufacturer="Atmel")  # a real, newer write under library/

        self.assertTrue(ci.needs_rebuild())

    def test_004_ensure_fresh_index_rebuilds_exactly_when_needed(self):
        self._save_part()
        self.assertTrue(ci.needs_rebuild())

        ci.ensure_fresh_index()

        self.assertFalse(ci.needs_rebuild())
        chunks = ci.search("Microchip")
        self.assertTrue(chunks)


class TestPromotedNoteIndexing(ContextIndexTestCase):
    """CTX-206.7's own note extractor was wired but inert (no real
    `notes` field existed anywhere yet). CTX-206.8 (chat.promote_turn)
    made it real -- this proves the two contexts actually connect, not
    just that each passes its own isolated tests."""

    def test_001_a_real_promoted_note_on_a_part_indexes_and_resolves(self):
        self._save_part()
        store.add_part_note("ATtiny85", {
            "note_id": "n1", "text": "Add a 100nF ceramic capacitor near VCC.",
            "sources": [], "created_at": "t", "origin": {}, "provenance": None,
        })

        ci.rebuild_index()

        chunks = ci.search("100nF ceramic capacitor")
        note_chunks = [c for c in chunks if c.kind == "note"]
        self.assertEqual(len(note_chunks), 1)
        self.assertEqual(note_chunks[0].source_ref, {
            "kind": "note", "scope": "part", "scope_id": "ATtiny85", "note_id": "n1",
        })
        self.assertTrue(chat_agents.resolve_source_ref(note_chunks[0].source_ref))

    def test_002_a_real_promoted_note_on_a_project_indexes_and_resolves(self):
        store.save_project({"name": "weather-pcb"})
        store.add_project_note("weather-pcb", {
            "note_id": "n1", "text": "This board must survive outdoor rain exposure.",
            "sources": [], "created_at": "t", "origin": {}, "provenance": None,
        })

        ci.rebuild_index()

        chunks = ci.search("outdoor rain exposure")
        note_chunks = [c for c in chunks if c.kind == "note"]
        self.assertEqual(note_chunks[0].source_ref, {
            "kind": "note", "scope": "project", "scope_id": "weather-pcb", "note_id": "n1",
        })
        self.assertTrue(chat_agents.resolve_source_ref(note_chunks[0].source_ref))


class TestSearchScoping(ContextIndexTestCase):

    def setUp(self):
        super().setUp()
        self._save_part()
        store.save_part({
            "part_id": "ESP32-S3", "manufacturer": "Espressif", "package": "QFN-56", "pins": [],
            "datasheet_url": "https://example.com/y.pdf", "package_dimensions": {}, "courtyard": {},
            "provenance": _VALID_PROVENANCE,
        })
        ci.rebuild_index()

    def test_001_an_unscoped_search_finds_matches_across_every_part(self):
        chunks = ci.search("Espressif")
        self.assertTrue(any(c.body == "Espressif" for c in chunks))

    def test_002_scoping_to_one_part_excludes_a_real_match_on_another(self):
        chunks = ci.search("Espressif", scopes=[("part", "ATtiny85")])
        self.assertEqual(chunks, [])

    def test_003_scoping_to_the_real_matching_part_still_finds_it(self):
        chunks = ci.search("Espressif", scopes=[("part", "ESP32-S3")])
        self.assertTrue(any(c.body == "Espressif" for c in chunks))


class TestLikeScanRetriever(ContextIndexTestCase):
    """The real fallback path (SPEC-206 §2.6's own explicit requirement)
    -- exercised directly, not just assumed to work because Fts5Retriever
    does."""

    def test_001_finds_a_real_substring_match(self):
        self._save_part()
        ci.rebuild_index()

        chunks = ci.LikeScanRetriever().search("Micro", scopes=[])

        self.assertTrue(any("Microchip" in c.body for c in chunks))

    def test_002_respects_scope_filtering_too(self):
        self._save_part()
        store.save_part({
            "part_id": "ESP32-S3", "manufacturer": "Espressif", "package": "QFN-56", "pins": [],
            "datasheet_url": "https://example.com/y.pdf", "package_dimensions": {}, "courtyard": {},
            "provenance": _VALID_PROVENANCE,
        })
        ci.rebuild_index()

        chunks = ci.LikeScanRetriever().search("Espressif", scopes=[("part", "ATtiny85")])

        self.assertEqual(chunks, [])


if __name__ == '__main__':
    unittest.main()

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import library_store as store


_VALID_PROVENANCE = {
    field: {"source": "datasheet_pdf", "model": None, "confidence": 1.0}
    for field in store.PART_PROVENANCE_REQUIRED_FIELDS
}


class LibraryStoreTestCase(unittest.TestCase):
    """Every test gets a real, isolated temp directory -- configure() is
    called directly, the same way _apply_env_config() calls it in
    production, per CLAUDE.md's 'verify against the real thing' norm:
    this is real file I/O against a real filesystem, not mocked."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        store.configure(storage_root=self._tmpdir.name)

    def tearDown(self):
        store.configure(storage_root=None)
        self._tmpdir.cleanup()


class TestStorageRootUnconfigured(unittest.TestCase):

    def test_001_reading_before_configure_raises_a_clean_error(self):
        store.configure(storage_root=None)
        with self.assertRaises(store.StorageRootUnconfiguredError):
            store.list_parts()


class TestPart(LibraryStoreTestCase):

    def test_001_save_and_load_round_trip(self):
        part = {
            "part_id": "ATtiny85",
            "manufacturer": "Microchip",
            "package": "SOIC-8",
            "pins": [],
            "datasheet_url": "https://example.com/ATtiny85.pdf",
            "footprint_id": None,
            "provenance": _VALID_PROVENANCE,
        }
        saved = store.save_part(part)
        self.assertEqual(saved["schema_version"], 1)

        loaded = store.load_part("ATtiny85")
        self.assertEqual(loaded["manufacturer"], "Microchip")
        self.assertIsNone(loaded["footprint_id"])

    def test_002_missing_part_id_is_rejected(self):
        with self.assertRaises(store.SchemaValidationError):
            store.save_part({"manufacturer": "Microchip", "provenance": _VALID_PROVENANCE})

    def test_003_missing_provenance_entirely_is_rejected(self):
        with self.assertRaises(store.SchemaValidationError) as ctx:
            store.save_part({"part_id": "X", "manufacturer": "Microchip"})
        self.assertIn("provenance", str(ctx.exception))

    def test_004_provenance_missing_a_required_field_is_rejected(self):
        """TEST: SPEC-300 §2.2's 'must reject', not merely document --
        every required field needs its own provenance entry, not just
        one blanket provenance blob for the whole record."""
        incomplete = dict(_VALID_PROVENANCE)
        del incomplete["package"]
        with self.assertRaises(store.SchemaValidationError) as ctx:
            store.save_part({
                "part_id": "X",
                "manufacturer": "Microchip",
                "package": "SOIC-8",
                "pins": [],
                "datasheet_url": "https://example.com/x.pdf",
                "provenance": incomplete,
            })
        self.assertIn("package", str(ctx.exception))

    def test_005_list_parts_returns_every_saved_part_id_sorted(self):
        for part_id in ("Zeta", "Alpha", "Mid"):
            store.save_part({
                "part_id": part_id,
                "manufacturer": "Test",
                "package": "SOIC-8",
                "pins": [],
                "datasheet_url": "https://example.com/x.pdf",
                "provenance": _VALID_PROVENANCE,
            })

        self.assertEqual(store.list_parts(), ["Alpha", "Mid", "Zeta"])

    def test_006_a_part_with_no_footprint_yet_is_still_valid(self):
        """TEST: SPEC-300 §2.1 -- a Part with pins and a datasheet is
        useful before any Footprint exists."""
        store.save_part({
            "part_id": "NoFootprintYet",
            "manufacturer": "Test",
            "package": "SOIC-8",
            "pins": [{"number": "1", "name": "VCC"}],
            "datasheet_url": "https://example.com/x.pdf",
            "footprint_id": None,
            "provenance": _VALID_PROVENANCE,
        })
        loaded = store.load_part("NoFootprintYet")
        self.assertIsNone(loaded["footprint_id"])


class TestSymbolAndFootprint(LibraryStoreTestCase):

    def test_001_save_and_load_symbol(self):
        store.save_symbol({"symbol_id": "ATtiny85-sym", "pins": []})
        loaded = store.load_symbol("ATtiny85-sym")
        self.assertEqual(loaded["symbol_id"], "ATtiny85-sym")

    def test_002_missing_symbol_id_is_rejected(self):
        with self.assertRaises(store.SchemaValidationError):
            store.save_symbol({"pins": []})

    def test_003_save_and_load_footprint(self):
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})
        loaded = store.load_footprint("SOIC-8")
        self.assertEqual(loaded["footprint_id"], "SOIC-8")

    def test_004_missing_footprint_id_is_rejected(self):
        with self.assertRaises(store.SchemaValidationError):
            store.save_footprint({"pads": []})

    def test_005_one_footprint_record_is_not_duplicated_per_part(self):
        """TEST: SPEC-300 §2.1's explicit cardinality call -- SOIC-8 is
        one Footprint record regardless of how many Parts reference it."""
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})
        store.save_part({
            "part_id": "PartA", "manufacturer": "X", "package": "SOIC-8", "pins": [],
            "datasheet_url": "https://example.com/a.pdf", "footprint_id": "SOIC-8",
            "provenance": _VALID_PROVENANCE,
        })
        store.save_part({
            "part_id": "PartB", "manufacturer": "X", "package": "SOIC-8", "pins": [],
            "datasheet_url": "https://example.com/b.pdf", "footprint_id": "SOIC-8",
            "provenance": _VALID_PROVENANCE,
        })

        footprints_dir = os.path.join(self._tmpdir.name, "library", "footprints")
        self.assertEqual(os.listdir(footprints_dir), ["SOIC-8.json"])
        self.assertEqual(store.load_part("PartA")["footprint_id"], "SOIC-8")
        self.assertEqual(store.load_part("PartB")["footprint_id"], "SOIC-8")


class TestProject(LibraryStoreTestCase):

    def test_001_save_and_load_round_trip(self):
        store.save_project({"name": "weather-pcb", "component_refs": []})
        loaded = store.load_project("weather-pcb")
        self.assertEqual(loaded["name"], "weather-pcb")
        self.assertEqual(loaded["schema_version"], 1)

    def test_002_missing_name_is_rejected(self):
        with self.assertRaises(store.SchemaValidationError):
            store.save_project({"component_refs": []})

    def test_003_list_projects_returns_only_real_projects_sorted(self):
        store.save_project({"name": "weather-pcb"})
        store.save_project({"name": "doorbell"})

        self.assertEqual(store.list_projects(), ["doorbell", "weather-pcb"])


class TestArtifact(LibraryStoreTestCase):

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})

    def test_001_save_and_load_a_non_enclosure_artifact(self):
        store.save_artifact("weather-pcb", {"artifact_id": "report-1", "kind": "advisor_report"})
        loaded = store.load_artifact("weather-pcb", "report-1")
        self.assertEqual(loaded["kind"], "advisor_report")

    def test_002_enclosure_artifact_without_board_revision_is_rejected(self):
        """TEST: the one real gap the SPEC-304 ID-collision resolution
        carried forward (ROADMAP.md §3.3) -- enforced, not just named."""
        with self.assertRaises(store.SchemaValidationError) as ctx:
            store.save_artifact("weather-pcb", {"artifact_id": "enc-1", "kind": "enclosure"})
        self.assertIn("board_revision", str(ctx.exception))

    def test_003_enclosure_artifact_with_board_revision_succeeds(self):
        store.save_artifact(
            "weather-pcb",
            {"artifact_id": "enc-1", "kind": "enclosure", "board_revision": "a1b2c3d"},
        )
        loaded = store.load_artifact("weather-pcb", "enc-1")
        self.assertEqual(loaded["board_revision"], "a1b2c3d")

    def test_004_list_artifacts_returns_every_saved_artifact_id_sorted(self):
        store.save_artifact("weather-pcb", {"artifact_id": "b", "kind": "advisor_report"})
        store.save_artifact("weather-pcb", {"artifact_id": "a", "kind": "advisor_report"})

        self.assertEqual(store.list_artifacts("weather-pcb"), ["a", "b"])


class TestConversation(LibraryStoreTestCase):

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})

    def test_001_load_conversation_is_empty_before_any_turn_is_appended(self):
        self.assertEqual(store.load_conversation("weather-pcb"), [])

    def test_002_append_and_load_round_trip_in_order(self):
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "hello"})
        store.append_conversation_turn("weather-pcb", {"role": "assistant", "content": "hi"})

        turns = store.load_conversation("weather-pcb")
        self.assertEqual([t["role"] for t in turns], ["user", "assistant"])

    def test_003_conversation_is_append_only_not_rewritten(self):
        """TEST: SPEC-300 §2.1 -- a JSONL file, not one record rewritten
        on every turn. Confirmed by checking the file grows one line at a
        time rather than being replaced."""
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "one"})
        path = store._conversation_path("weather-pcb")
        with open(path) as f:
            after_first = f.read()

        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "two"})
        with open(path) as f:
            after_second = f.read()

        self.assertTrue(after_second.startswith(after_first))


if __name__ == '__main__':
    unittest.main()

import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
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


class TestFrozenIdentityStrings(unittest.TestCase):
    """SPEC-405 §2.1/§3.4: the durable guard against that spec's own
    central hazard -- a global find-and-replace during the Copperplane
    rename silently orphaning every already-linked project (which stores
    its state under `_PROJECT_STATE_SUBDIR`, possibly inside the user's
    own git repo) and every previously-generated `.kicad_mod` footprint
    (stamped with `_KICAD_MOD_GENERATOR`). Both stay exactly these
    strings, deliberately, forever."""

    def test_001_project_state_subdir_is_frozen(self):
        self.assertEqual(store._PROJECT_STATE_SUBDIR, ".hardware-agent-studio")

    def test_002_kicad_mod_generator_is_frozen(self):
        self.assertEqual(store._KICAD_MOD_GENERATOR, "hardware-agent-studio")


class TestStorageRootUnconfigured(unittest.TestCase):

    def test_001_reading_before_configure_raises_a_clean_error(self):
        store.configure(storage_root=None)
        with self.assertRaises(store.StorageRootUnconfiguredError):
            store.list_parts()


class TestCurrentStorageRoot(unittest.TestCase):
    """SPEC-110: unlike _root(), current_storage_root() never raises --
    daemon.get_capabilities calls it to report the real path (or None)
    without needing to catch StorageRootUnconfiguredError itself."""

    def test_001_returns_none_before_configure(self):
        store.configure(storage_root=None)
        self.assertIsNone(store.current_storage_root())

    def test_002_returns_the_real_configured_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store.configure(storage_root=tmpdir)
            try:
                self.assertEqual(store.current_storage_root(), tmpdir)
            finally:
                store.configure(storage_root=None)


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

    def test_006_list_footprints_returns_every_saved_id_sorted(self):
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})
        store.save_footprint({"footprint_id": "DIP-8", "pads": []})

        self.assertEqual(store.list_footprints(), ["DIP-8", "SOIC-8"])

    def test_007_search_footprints_matches_on_footprint_name(self):
        store.save_footprint({
            "footprint_id": "MyPCBLibs__MP1584EN_5V_Module",
            "library": "MyPCBLibs", "footprint_name": "MP1584EN_5V_Module",
        })
        store.save_footprint({"footprint_id": "DIP-8", "pads": []})

        results = store.search_footprints("MP1584")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["footprint_id"], "MyPCBLibs__MP1584EN_5V_Module")

    def test_008_search_footprints_falls_back_to_footprint_id_when_name_is_missing(self):
        """TEST-002: a real, already-possible shape -- this file's own
        test_003/test_005 above save footprints with no footprint_name
        at all. Search must still find them, by footprint_id."""
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})

        results = store.search_footprints("SOIC")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["footprint_id"], "SOIC-8")

    def test_009_search_footprints_no_match_returns_an_empty_list(self):
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})

        self.assertEqual(store.search_footprints("definitely_not_present"), [])


class TestLibraryTagging(LibraryStoreTestCase):
    """CTX-315.1: SPEC-315's real library_ids/registry/tagging layer."""

    def _save_part(self, part_id, **overrides):
        return store.save_part({
            "part_id": part_id, "manufacturer": "X", "package": "SOIC-8", "pins": [],
            "datasheet_url": "https://example.com/x.pdf", "provenance": _VALID_PROVENANCE,
            **overrides,
        })

    def test_001_saving_with_no_library_ids_persists_default_only(self):
        saved = self._save_part("P1")
        self.assertEqual(saved["library_ids"], ["default"])

    def test_002_saving_with_a_real_custom_set_force_includes_default(self):
        store.create_library("ESP32 Boards")
        saved = self._save_part("P1", library_ids=["esp32-boards"])
        self.assertEqual(saved["library_ids"], ["default", "esp32-boards"])

    def test_003_loading_a_real_pre_migration_record_backfills_default(self):
        """A real record saved before CTX-315.1 shipped has no
        `library_ids` key at all -- hand-write one directly to disk
        (bypassing save_part) to prove the real read-time backfill,
        not just that save_part always adds the field."""
        part = {
            "part_id": "PreMigration", "manufacturer": "X", "package": "SOIC-8", "pins": [],
            "datasheet_url": "https://example.com/x.pdf", "provenance": _VALID_PROVENANCE,
            "schema_version": 1,
        }
        path = os.path.join(self._tmpdir.name, "library", "parts", "PreMigration.part.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(part, f)

        loaded = store.load_part("PreMigration")
        self.assertEqual(loaded["library_ids"], ["default"])

    def test_004_re_saving_a_tagged_part_preserves_its_real_custom_tags(self):
        """The real, important precedence bug this slice found while
        wiring it in: every existing caller of save_part (attaching a
        footprint, re-saving a confirmed candidate) re-saves an
        already-loaded record without passing library_ids explicitly --
        that must never silently reset a user's real custom tags."""
        store.create_library("ESP32 Boards")
        self._save_part("P1", library_ids=["esp32-boards"])

        reloaded = store.load_part("P1")
        resaved = store.save_part(reloaded)

        self.assertEqual(resaved["library_ids"], ["default", "esp32-boards"])

    def test_005_create_library_derives_a_real_collision_checked_id(self):
        first = store.create_library("ESP32 Boards")
        second = store.create_library("ESP32 Boards")

        self.assertEqual(first["id"], "esp32-boards")
        self.assertNotEqual(first["id"], second["id"])

    def test_006_create_library_rejects_an_empty_name(self):
        with self.assertRaises(store.SchemaValidationError):
            store.create_library("   ")

    def test_007_list_libraries_reports_default_with_real_counts_across_everything(self):
        self._save_part("P1")
        self._save_part("P2")
        store.save_footprint({"footprint_id": "SOIC-8", "pads": []})

        libraries = store.list_libraries()

        default = next(lib for lib in libraries if lib["id"] == "default")
        self.assertEqual(default["part_count"], 2)
        self.assertEqual(default["footprint_count"], 1)

    def test_008_list_libraries_reports_a_real_custom_librarys_own_counts(self):
        store.create_library("ESP32 Boards")
        self._save_part("P1", library_ids=["esp32-boards"])
        self._save_part("P2")

        libraries = store.list_libraries()

        custom = next(lib for lib in libraries if lib["id"] == "esp32-boards")
        self.assertEqual(custom["part_count"], 1)

    def test_009_list_parts_with_a_library_id_filter_returns_only_real_tagged_members(self):
        store.create_library("ESP32 Boards")
        self._save_part("Tagged", library_ids=["esp32-boards"])
        self._save_part("Untagged")

        self.assertEqual(store.list_parts("esp32-boards"), ["Tagged"])
        self.assertEqual(sorted(store.list_parts("default")), ["Tagged", "Untagged"])

    def test_010_list_symbols_mirrors_list_footprints_real_pattern(self):
        store.save_symbol({"symbol_id": "Zeta", "pins": []})
        store.save_symbol({"symbol_id": "Alpha", "pins": []})

        self.assertEqual(store.list_symbols(), ["Alpha", "Zeta"])

    def test_011_tag_object_replaces_a_real_parts_own_custom_membership(self):
        store.create_library("ESP32 Boards")
        store.create_library("Client X")
        self._save_part("P1", library_ids=["esp32-boards"])

        tagged = store.tag_object("part", "P1", ["client-x"])

        self.assertEqual(tagged["library_ids"], ["client-x", "default"])

    def test_012_tag_object_rejects_an_unknown_library_id(self):
        self._save_part("P1")
        with self.assertRaises(store.SchemaValidationError) as ctx:
            store.tag_object("part", "P1", ["not-a-real-library"])
        self.assertIn("not-a-real-library", str(ctx.exception))

    def test_013_tag_object_works_for_symbols_and_footprints_independently(self):
        """A Footprint's own library membership is tracked independently
        of whichever Part references it -- SPEC-315 §2's own real
        design call, since a Footprint is already shared across many
        Parts (test_005 above)."""
        store.create_library("ESP32 Boards")
        store.save_symbol({"symbol_id": "Sym1", "pins": []})
        store.save_footprint({"footprint_id": "Fp1", "pads": []})

        tagged_symbol = store.tag_object("symbol", "Sym1", ["esp32-boards"])
        tagged_footprint = store.tag_object("footprint", "Fp1", ["esp32-boards"])

        self.assertEqual(tagged_symbol["library_ids"], ["default", "esp32-boards"])
        self.assertEqual(tagged_footprint["library_ids"], ["default", "esp32-boards"])

    def test_014_tag_object_rejects_an_unknown_kind(self):
        self._save_part("P1")
        with self.assertRaises(store.SchemaValidationError):
            store.tag_object("not_a_real_kind", "P1", [])


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

    def test_004_renaming_the_folder_on_disk_does_not_leave_a_stale_name(self):
        """CTX-110.1/task #53: the folder name is the real identity (per
        list_projects()); project.json's own `name` field must never be
        allowed to silently disagree with it after a user renames the
        folder outside the app."""
        store.save_project({"name": "weather-pcb", "component_refs": []})
        old_dir = store._project_dir("weather-pcb")
        new_dir = os.path.join(os.path.dirname(old_dir), "weather-station")
        os.rename(old_dir, new_dir)

        self.assertEqual(store.list_projects(), ["weather-station"])
        loaded = store.load_project("weather-station")
        self.assertEqual(loaded["name"], "weather-station")
        self.assertEqual(loaded["component_refs"], [])


class TestProjectIntent(LibraryStoreTestCase):
    """CTX-206.1 (SPEC-206 §2.1): the project-level counterpart to
    Part.connection_guidance's backfill-and-persist shape, applied to a
    plain optional free-text field instead of a generated record."""

    def test_001_load_project_backfills_intent_as_none_not_an_empty_string(self):
        store.save_project({"name": "weather-pcb"})

        loaded = store.load_project("weather-pcb")

        self.assertIsNone(loaded["intent"])

    def test_002_save_project_accepts_a_real_intent_string(self):
        store.save_project({"name": "weather-pcb", "intent": "A weatherproof outdoor PCB."})

        loaded = store.load_project("weather-pcb")

        self.assertEqual(loaded["intent"], "A weatherproof outdoor PCB.")

    def test_003_save_project_rejects_a_non_string_non_null_intent(self):
        with self.assertRaises(store.SchemaValidationError):
            store.save_project({"name": "weather-pcb", "intent": 42})

    def test_004_an_empty_string_intent_stays_distinguishable_from_never_set(self):
        # SPEC-206 §2.1: "never asked" and "asked, answered nothing" (the
        # user deliberately cleared it) are different states.
        store.save_project({"name": "weather-pcb", "intent": ""})

        loaded = store.load_project("weather-pcb")

        self.assertEqual(loaded["intent"], "")
        self.assertIsNotNone(loaded["intent"])

    def test_005_set_project_intent_persists_onto_the_real_current_record(self):
        store.save_project({"name": "weather-pcb", "component_refs": ["ATtiny85"]})

        updated = store.set_project_intent("weather-pcb", "A macropad from scratch.")

        self.assertEqual(updated["intent"], "A macropad from scratch.")
        # Preserves the record's other real fields, matching
        # save_part_design_guidance's own load-fresh-then-save shape.
        self.assertEqual(updated["component_refs"], ["ATtiny85"])
        reloaded = store.load_project("weather-pcb")
        self.assertEqual(reloaded["intent"], "A macropad from scratch.")


class TestProjectPartReferences(LibraryStoreTestCase):
    """CTX-304.3 (SPEC-304 §2): a Project holds real references to
    Library Parts (many-to-many, Part-level only) -- the same
    backfill-and-persist shape as TestProjectIntent above, applied to a
    list instead of a free-text field."""

    def test_001_load_project_backfills_parts_as_an_empty_list_not_none(self):
        store.save_project({"name": "weather-pcb"})

        loaded = store.load_project("weather-pcb")

        self.assertEqual(loaded["parts"], [])

    def test_002_add_project_part_reference_appends_and_persists(self):
        store.save_project({"name": "weather-pcb"})

        updated = store.add_project_part_reference("weather-pcb", "ATtiny85")

        self.assertEqual(updated["parts"], ["ATtiny85"])
        reloaded = store.load_project("weather-pcb")
        self.assertEqual(reloaded["parts"], ["ATtiny85"])

    def test_003_adding_the_same_part_twice_is_idempotent(self):
        store.save_project({"name": "weather-pcb"})

        store.add_project_part_reference("weather-pcb", "ATtiny85")
        updated = store.add_project_part_reference("weather-pcb", "ATtiny85")

        self.assertEqual(updated["parts"], ["ATtiny85"])

    def test_004_a_second_distinct_part_is_appended_alongside_the_first(self):
        store.save_project({"name": "weather-pcb"})

        store.add_project_part_reference("weather-pcb", "ATtiny85")
        updated = store.add_project_part_reference("weather-pcb", "ESP32-S3")

        self.assertEqual(updated["parts"], ["ATtiny85", "ESP32-S3"])

    def test_005_preserves_the_record_s_other_real_fields(self):
        store.save_project({"name": "weather-pcb", "intent": "A weatherproof outdoor PCB."})

        updated = store.add_project_part_reference("weather-pcb", "ATtiny85")

        self.assertEqual(updated["intent"], "A weatherproof outdoor PCB.")


class TestProjectFootprintOverrides(LibraryStoreTestCase):
    """CTX-308.9 (SPEC-308): real user feedback -- there's no guarantee
    the same footprint fits a Part in every project. A Project can
    override which already-saved Footprint a Part resolves to for that
    project only, falling back to the Part's own global `footprint_id`
    when no override is set. This never creates a second Footprint
    record (still one global library object, SPEC-300 §2.1's own
    cardinality) -- only a per-project foreign-key override."""

    def test_001_load_project_backfills_footprint_overrides_as_an_empty_dict(self):
        store.save_project({"name": "weather-pcb"})

        loaded = store.load_project("weather-pcb")

        self.assertEqual(loaded["footprint_overrides"], {})

    def test_002_set_footprint_override_persists_and_reloads(self):
        store.save_project({"name": "weather-pcb"})

        updated = store.set_project_footprint_override("weather-pcb", "ATtiny85", "SOIC-8")

        self.assertEqual(updated["footprint_overrides"], {"ATtiny85": "SOIC-8"})
        reloaded = store.load_project("weather-pcb")
        self.assertEqual(reloaded["footprint_overrides"], {"ATtiny85": "SOIC-8"})

    def test_003_setting_a_second_part_s_override_leaves_the_first_untouched(self):
        store.save_project({"name": "weather-pcb"})

        store.set_project_footprint_override("weather-pcb", "ATtiny85", "SOIC-8")
        updated = store.set_project_footprint_override("weather-pcb", "ESP32-S3", "QFN-56")

        self.assertEqual(updated["footprint_overrides"], {"ATtiny85": "SOIC-8", "ESP32-S3": "QFN-56"})

    def test_004_re_setting_the_same_part_s_override_replaces_it(self):
        store.save_project({"name": "weather-pcb"})

        store.set_project_footprint_override("weather-pcb", "ATtiny85", "SOIC-8")
        updated = store.set_project_footprint_override("weather-pcb", "ATtiny85", "DIP-8")

        self.assertEqual(updated["footprint_overrides"], {"ATtiny85": "DIP-8"})

    def test_005_footprint_id_none_clears_an_existing_override(self):
        store.save_project({"name": "weather-pcb"})
        store.set_project_footprint_override("weather-pcb", "ATtiny85", "SOIC-8")

        updated = store.set_project_footprint_override("weather-pcb", "ATtiny85", None)

        self.assertEqual(updated["footprint_overrides"], {})

    def test_006_clearing_an_override_that_was_never_set_is_a_harmless_no_op(self):
        store.save_project({"name": "weather-pcb"})

        updated = store.set_project_footprint_override("weather-pcb", "ATtiny85", None)

        self.assertEqual(updated["footprint_overrides"], {})

    def test_007_preserves_the_record_s_other_real_fields(self):
        store.save_project({"name": "weather-pcb", "intent": "A weatherproof outdoor PCB."})

        updated = store.set_project_footprint_override("weather-pcb", "ATtiny85", "SOIC-8")

        self.assertEqual(updated["intent"], "A weatherproof outdoor PCB.")


class TestProjectDirectoryLink(LibraryStoreTestCase):
    """CTX-312.1: SPEC-304 §2.1 already described a Project as holding "a
    link to a KiCad project directory on disk" -- these tests cover the
    real directory-aware routing that finally builds it, and the
    guarantee that an unlinked project's behavior is untouched."""

    def setUp(self):
        super().setUp()
        self._real_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._real_dir.cleanup()
        super().tearDown()

    def test_001_a_directory_linked_project_writes_its_real_manifest_there(self):
        store.save_project({
            "name": "weather-pcb", "directory": self._real_dir.name, "wall_thickness_mm": 2,
        })

        state_path = os.path.join(
            self._real_dir.name, store._PROJECT_STATE_SUBDIR, "project.json",
        )
        self.assertTrue(os.path.isfile(state_path))

    def test_002_a_directory_linked_project_round_trips_through_the_real_directory(self):
        store.save_project({
            "name": "weather-pcb", "directory": self._real_dir.name, "wall_thickness_mm": 2,
        })

        loaded = store.load_project("weather-pcb")

        self.assertEqual(loaded["wall_thickness_mm"], 2)
        self.assertEqual(loaded["directory"], self._real_dir.name)

    def test_003_an_unlinked_project_still_behaves_exactly_as_before_ctx_312_1(self):
        store.save_project({"name": "weather-pcb", "component_refs": []})

        loaded = store.load_project("weather-pcb")

        # CTX-206.1/CTX-304.3/CTX-308.9/CTX-206.8: `intent`, `parts`,
        # `footprint_overrides`, and `notes` are now real, backfilled
        # state -- part of "exactly as before" now that all four fields
        # exist at all.
        self.assertEqual(
            loaded,
            {
                "name": "weather-pcb",
                "schema_version": 1,
                "component_refs": [],
                "intent": None,
                "parts": [],
                "footprint_overrides": {},
                "notes": None,
            },
        )
        self.assertNotIn("directory", loaded)

    def test_004_a_moved_or_deleted_linked_directory_raises_a_clean_error_not_a_bare_one(self):
        store.save_project({"name": "weather-pcb", "directory": self._real_dir.name})
        self._real_dir.cleanup()

        with self.assertRaises(store.ProjectDirectoryMissingError) as ctx:
            store.load_project("weather-pcb")
        self.assertIn("weather-pcb", str(ctx.exception))
        self.assertIn(self._real_dir.name, str(ctx.exception))

    def test_005_project_directory_returns_the_real_link_once_set(self):
        store.save_project({"name": "weather-pcb", "directory": self._real_dir.name})

        self.assertEqual(store.project_directory("weather-pcb"), self._real_dir.name)

    def test_006_project_directory_falls_back_to_storage_root_when_unlinked(self):
        store.save_project({"name": "weather-pcb"})

        self.assertEqual(store.project_directory("weather-pcb"), store._project_dir("weather-pcb"))

    def test_007_list_projects_still_finds_a_directory_linked_project(self):
        store.save_project({"name": "weather-pcb", "directory": self._real_dir.name})

        self.assertEqual(store.list_projects(), ["weather-pcb"])

    def test_008_set_project_intent_on_a_linked_project_lands_in_the_real_manifest_not_the_pointer(self):
        # CTX-206.1: `intent` must travel with the portable folder, the
        # same as every other real field -- never stranded in the
        # storage-root pointer, which save_project's own linked branch
        # deliberately keeps to exactly {name, directory, schema_version}.
        store.save_project({"name": "weather-pcb", "directory": self._real_dir.name})

        store.set_project_intent("weather-pcb", "A macropad from scratch.")

        state_path = os.path.join(self._real_dir.name, store._PROJECT_STATE_SUBDIR, "project.json")
        with open(state_path) as f:
            manifest = json.load(f)
        self.assertEqual(manifest["intent"], "A macropad from scratch.")
        reloaded = store.load_project("weather-pcb")
        self.assertEqual(reloaded["intent"], "A macropad from scratch.")


class TestOpenProjectFromDirectory(LibraryStoreTestCase):
    """CTX-312.3: the real reverse of TestProjectDirectoryLink above --
    given a real folder (as if copied from another machine), restores it
    as a known project on this one. The actual payoff of CTX-312.1's own
    portability work, and the real backend for the native menu's own
    "Open Project…" action."""

    def setUp(self):
        super().setUp()
        self._real_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._real_dir.cleanup()
        super().tearDown()

    def test_001_a_real_linked_folder_is_restored_as_a_known_project(self):
        # Simulates a folder that already carries real project state --
        # e.g. handed over from another machine -- written directly, not
        # via this test's own storage-root-configured save_project (that
        # would already register the pointer, defeating the point of
        # this test).
        state_dir = os.path.join(self._real_dir.name, store._PROJECT_STATE_SUBDIR)
        os.makedirs(state_dir)
        with open(os.path.join(state_dir, "project.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "weather-pcb", "wall_thickness_mm": 2}, f)

        result = store.open_project_from_directory(self._real_dir.name)

        self.assertEqual(result["name"], "weather-pcb")
        self.assertEqual(result["wall_thickness_mm"], 2)
        self.assertEqual(result["directory"], self._real_dir.name)

    def test_002_restoring_a_project_makes_it_discoverable_via_list_projects(self):
        state_dir = os.path.join(self._real_dir.name, store._PROJECT_STATE_SUBDIR)
        os.makedirs(state_dir)
        with open(os.path.join(state_dir, "project.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "weather-pcb"}, f)

        store.open_project_from_directory(self._real_dir.name)

        self.assertEqual(store.list_projects(), ["weather-pcb"])

    def test_003_a_folder_with_no_real_state_file_raises_a_clean_error(self):
        with self.assertRaises(store.ProjectNotLinkedError) as ctx:
            store.open_project_from_directory(self._real_dir.name)
        self.assertIn(self._real_dir.name, str(ctx.exception))

    def test_004_never_silently_creates_a_new_project_from_the_folder_name(self):
        """The real, deliberate design decision named in this function's
        own docstring: no state file means a clean error, not a guessed
        new project -- avoids a real name-collision risk against an
        existing, unrelated storage_root/projects/<basename>/."""
        with self.assertRaises(store.ProjectNotLinkedError):
            store.open_project_from_directory(self._real_dir.name)

        self.assertEqual(store.list_projects(), [])


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


class TestChatThreads(LibraryStoreTestCase):
    """CTX-206.3 (SPEC-206 §2.2): thread storage -- scope resolution,
    real path construction, real round trips. `append_turn`/`chat.send`
    (SPEC-206 §2.5) are a later, separate slice needing the agent layer;
    tests here write via the private `_write_thread_turns` helper
    directly, the same way `TestConversation` above reaches into
    `_conversation_path`."""

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})

    def test_001_load_thread_is_empty_before_any_turn_exists(self):
        self.assertEqual(store.load_thread("project", "weather-pcb:overview"), [])

    def test_002_load_thread_rejects_an_unknown_project_scoped_area(self):
        with self.assertRaises(store.SchemaValidationError):
            store.load_thread("project", "weather-pcb:not-a-real-area")

    def test_003_load_thread_rejects_a_malformed_scope_id_with_no_area(self):
        with self.assertRaises(store.SchemaValidationError):
            store.load_thread("project", "weather-pcb")

    def test_004_load_thread_rejects_an_unknown_scope(self):
        with self.assertRaises(store.SchemaValidationError):
            store.load_thread("not-a-real-scope", "weather-pcb:overview")

    def test_005_a_real_turn_written_via_the_real_path_helper_round_trips(self):
        path = store._project_thread_path("weather-pcb", "schematic")
        store._write_thread_turns(path, [
            {"turn_id": "t1", "role": "user", "content": "what's pin 8 for?"},
        ])

        turns = store.load_thread("project", "weather-pcb:schematic")

        self.assertEqual(turns[0]["content"], "what's pin 8 for?")

    def test_006_a_part_scoped_thread_lives_under_the_real_global_library_path(self):
        path = store._part_thread_path("ATtiny85")
        store._write_thread_turns(path, [{"turn_id": "t1", "role": "user", "content": "hi"}])

        turns = store.load_thread("part", "ATtiny85")

        self.assertEqual(len(turns), 1)
        self.assertTrue(path.endswith(os.path.join("library", "chats", "parts", "ATtiny85.jsonl")))


class TestAppendThreadTurn(LibraryStoreTestCase):
    """CTX-206.6 (SPEC-206 §2.5): `chat.send` calls this twice per turn
    (user, then assistant) -- a real, single-line append, not a
    read-all-rewrite-all like `_write_thread_turns`."""

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})

    def test_001_appends_and_persists_a_real_turn(self):
        store.append_thread_turn("project", "weather-pcb:overview", {"turn_id": "t1", "role": "user", "content": "hi"})

        turns = store.load_thread("project", "weather-pcb:overview")

        self.assertEqual(turns, [{"turn_id": "t1", "role": "user", "content": "hi"}])

    def test_002_a_second_append_lands_after_the_first_not_over_it(self):
        store.append_thread_turn("project", "weather-pcb:overview", {"turn_id": "t1", "role": "user", "content": "hi"})
        store.append_thread_turn("project", "weather-pcb:overview", {"turn_id": "t2", "role": "assistant", "content": "hello"})

        turns = store.load_thread("project", "weather-pcb:overview")

        self.assertEqual([t["turn_id"] for t in turns], ["t1", "t2"])

    def test_003_works_for_a_part_scoped_thread_too(self):
        store.append_thread_turn("part", "ATtiny85", {"turn_id": "t1", "role": "user", "content": "hi"})

        turns = store.load_thread("part", "ATtiny85")

        self.assertEqual(len(turns), 1)

    def test_004_rejects_an_unknown_scope_the_same_way_load_thread_does(self):
        with self.assertRaises(store.SchemaValidationError):
            store.append_thread_turn("not-a-real-scope", "weather-pcb:overview", {"turn_id": "t1"})


class TestUpdateThreadTurn(LibraryStoreTestCase):
    """CTX-206.8 (SPEC-206 §2.7): `chat.promote_turn`'s own real caller
    -- marks a turn's `promoted_note_id` once its note exists."""

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})
        store.append_thread_turn("project", "weather-pcb:overview", {"turn_id": "t1", "role": "user", "content": "hi"})
        store.append_thread_turn(
            "project", "weather-pcb:overview", {"turn_id": "t2", "role": "assistant", "content": "hello"},
        )

    def test_001_updates_only_the_real_matching_turn(self):
        updated = store.update_thread_turn("project", "weather-pcb:overview", "t2", {"promoted_note_id": "n1"})

        self.assertEqual(updated["promoted_note_id"], "n1")
        turns = store.load_thread("project", "weather-pcb:overview")
        self.assertEqual(turns[0].get("promoted_note_id"), None)
        self.assertEqual(turns[1]["promoted_note_id"], "n1")

    def test_002_preserves_the_turn_s_other_real_fields(self):
        store.update_thread_turn("project", "weather-pcb:overview", "t2", {"promoted_note_id": "n1"})

        turns = store.load_thread("project", "weather-pcb:overview")
        self.assertEqual(turns[1]["content"], "hello")

    def test_003_raises_a_clean_error_for_an_unknown_turn_id(self):
        with self.assertRaises(store.SchemaValidationError):
            store.update_thread_turn("project", "weather-pcb:overview", "not-real", {"promoted_note_id": "n1"})


class TestAddPartNote(LibraryStoreTestCase):
    """CTX-206.8 (SPEC-206 §2.7): always additive -- a Part's notes list
    never shrinks."""

    def setUp(self):
        super().setUp()
        store.save_part({
            "part_id": "ATtiny85", "manufacturer": "Microchip", "package": "SOIC-8", "pins": [],
            "datasheet_url": "https://example.com/x.pdf", "package_dimensions": {}, "courtyard": {},
            "provenance": {f: {"source": "test"} for f in store.PART_PROVENANCE_REQUIRED_FIELDS},
        })

    def test_001_load_part_backfills_notes_to_none_not_an_empty_list(self):
        loaded = store.load_part("ATtiny85")

        self.assertIsNone(loaded["notes"])

    def test_002_adds_and_persists_a_real_note(self):
        note = {"note_id": "n1", "text": "Decouple with 100nF.", "sources": [], "created_at": "t"}

        updated = store.add_part_note("ATtiny85", note)

        self.assertEqual(updated["notes"], [note])
        reloaded = store.load_part("ATtiny85")
        self.assertEqual(reloaded["notes"], [note])

    def test_003_a_second_note_is_appended_alongside_the_first(self):
        store.add_part_note("ATtiny85", {"note_id": "n1", "text": "x"})
        updated = store.add_part_note("ATtiny85", {"note_id": "n2", "text": "y"})

        self.assertEqual([n["note_id"] for n in updated["notes"]], ["n1", "n2"])


class TestAddProjectNote(LibraryStoreTestCase):

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})

    def test_001_load_project_backfills_notes_to_none_not_an_empty_list(self):
        loaded = store.load_project("weather-pcb")

        self.assertIsNone(loaded["notes"])

    def test_002_adds_and_persists_a_real_note(self):
        note = {"note_id": "n1", "text": "This project targets outdoor use.", "sources": [], "created_at": "t"}

        updated = store.add_project_note("weather-pcb", note)

        self.assertEqual(updated["notes"], [note])
        reloaded = store.load_project("weather-pcb")
        self.assertEqual(reloaded["notes"], [note])


class TestChatThreadDirectoryLinkFix(LibraryStoreTestCase):
    """SPEC-206 §2.2's own named real bug: `_conversation_path` never
    followed `CTX-312.1`'s directory link, so a linked project's history
    was stripped when handed to another machine. This is the fix,
    verified directly against a real linked directory."""

    def setUp(self):
        super().setUp()
        self._real_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._real_dir.cleanup()
        super().tearDown()

    def test_001_a_linked_projects_thread_lives_inside_its_own_real_directory(self):
        store.save_project({"name": "weather-pcb", "directory": self._real_dir.name})

        path = store._project_thread_path("weather-pcb", "overview")

        self.assertTrue(path.startswith(self._real_dir.name))
        self.assertIn(store._PROJECT_STATE_SUBDIR, path)

    def test_002_a_turn_written_to_a_linked_project_thread_travels_with_the_folder(self):
        store.save_project({"name": "weather-pcb", "directory": self._real_dir.name})
        path = store._project_thread_path("weather-pcb", "overview")
        store._write_thread_turns(path, [{"turn_id": "t1", "role": "user", "content": "hi"}])

        turns = store.load_thread("project", "weather-pcb:overview")

        self.assertEqual(len(turns), 1)
        self.assertTrue(os.path.isfile(
            os.path.join(self._real_dir.name, store._PROJECT_STATE_SUBDIR, "chats", "overview.jsonl")
        ))


class TestChatThreadMigration(LibraryStoreTestCase):
    """SPEC-206 §2.2: a project's legacy `conversation.jsonl` (pre-
    CTX-206.3) is upconverted on first read of its `overview` thread,
    and left in place, never deleted."""

    def setUp(self):
        super().setUp()
        store.save_project({"name": "weather-pcb"})

    def test_001_migrates_a_real_legacy_conversation_on_first_overview_read(self):
        store.append_conversation_turn(
            "weather-pcb", {"role": "user", "content": "hello", "timestamp": "2026-01-01T00:00:00Z"},
        )
        store.append_conversation_turn("weather-pcb", {"role": "assistant", "content": "hi there"})

        turns = store.load_thread("project", "weather-pcb:overview")

        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0]["content"], "hello")
        self.assertEqual(turns[0]["timestamp"], "2026-01-01T00:00:00Z")
        self.assertIsNone(turns[1]["timestamp"])
        self.assertTrue(turns[0]["turn_id"])

    def test_002_migration_marks_general_practice_true_on_assistant_turns_only(self):
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "hello"})
        store.append_conversation_turn("weather-pcb", {"role": "assistant", "content": "hi"})

        turns = store.load_thread("project", "weather-pcb:overview")

        self.assertFalse(turns[0]["general_practice"])
        self.assertTrue(turns[1]["general_practice"])

    def test_003_migrated_from_lands_only_on_the_first_record(self):
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "one"})
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "two"})

        turns = store.load_thread("project", "weather-pcb:overview")

        self.assertIn("migrated_from", turns[0])
        self.assertNotIn("migrated_from", turns[1])
        self.assertEqual(turns[0]["migrated_from"], store._conversation_path("weather-pcb"))

    def test_004_the_legacy_file_is_left_in_place_not_deleted(self):
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "hello"})

        store.load_thread("project", "weather-pcb:overview")

        self.assertTrue(os.path.isfile(store._conversation_path("weather-pcb")))

    def test_005_migration_only_runs_once_a_second_read_uses_the_real_new_file(self):
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "hello"})
        first = store.load_thread("project", "weather-pcb:overview")

        # A legacy turn appended after migration must NOT retroactively
        # reappear -- the new file is now the real source of truth.
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "too late"})
        second = store.load_thread("project", "weather-pcb:overview")

        self.assertEqual(first, second)

    def test_006_a_project_with_no_legacy_conversation_migrates_nothing(self):
        turns = store.load_thread("project", "weather-pcb:overview")

        self.assertEqual(turns, [])
        self.assertFalse(os.path.isfile(store._project_thread_path("weather-pcb", "overview")))

    def test_007_list_threads_reports_an_unmigrated_legacy_overview_thread(self):
        store.append_conversation_turn("weather-pcb", {"role": "user", "content": "hello"})

        self.assertEqual(store.list_threads("weather-pcb"), ["overview"])

    def test_008_list_threads_reports_real_new_format_threads_too(self):
        path = store._project_thread_path("weather-pcb", "schematic")
        store._write_thread_turns(path, [{"turn_id": "t1", "role": "user", "content": "hi"}])

        self.assertEqual(store.list_threads("weather-pcb"), ["schematic"])

    def test_009_list_threads_is_empty_for_a_project_with_no_chat_history(self):
        self.assertEqual(store.list_threads("weather-pcb"), [])


class _OneShotServer:
    """A real, local HTTP server for cache_datasheet's tests -- a genuine
    socket round trip and a genuine urllib fetch, per CLAUDE.md's 'verify
    against the real thing' norm, without depending on outside internet
    access for a repo test."""

    def __init__(self, status: int, body: bytes, content_type: str = "application/pdf"):
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}/datasheet.pdf"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()


class _StallingServer:
    """Accepts the connection and sends headers, then blocks forever
    before writing any body -- reproduces the real bug found by real
    network testing: a timeout that happens during `response.read()`
    (the connection succeeded; the body never arrives) raises a bare
    TimeoutError, not urllib.error.URLError, so a handler that only
    catches URLError lets it escape uncaught."""

    def __init__(self):
        release = threading.Event()
        self._release = release

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.end_headers()
                self.wfile.flush()
                release.wait(timeout=10)

            def log_message(self, *args):
                pass

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}/datasheet.pdf"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self._release.set()
        self._server.shutdown()
        self._server.server_close()


class TestCacheDatasheet(LibraryStoreTestCase):

    def test_001_a_successful_fetch_writes_the_real_bytes_and_returns_the_real_path(self):
        server = _OneShotServer(200, b"%PDF-1.4 fake datasheet bytes")
        try:
            path = store.cache_datasheet("ATtiny85", server.url)
        finally:
            server.stop()

        self.assertTrue(path.endswith(os.path.join("library", "datasheets", "ATtiny85.pdf")))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"%PDF-1.4 fake datasheet bytes")

    def test_002_a_non_200_response_raises_and_writes_nothing(self):
        server = _OneShotServer(404, b"not found")
        try:
            with self.assertRaises(store.DatasheetFetchError):
                store.cache_datasheet("ATtiny85", server.url)
        finally:
            server.stop()

        self.assertFalse(os.path.exists(os.path.join(store._datasheets_dir(), "ATtiny85.pdf")))

    def test_002b_an_html_error_page_served_with_200_is_refused(self):
        """CTX-306.8, found for real on 2026-09-01. keyelco.com answers a
        missing PDF with its own HTML page and HTTP 200, so `3003.pdf` and
        `1060.pdf` cached BYTE-IDENTICAL HTML -- same sha256 -- and every
        downstream consumer would have been reading a web page. Worse than
        the 403s and 404s beside it, which at least fail loudly."""
        server = _OneShotServer(200, b'<!DOCTYPE html><html><body>Not found</body></html>')
        try:
            with self.assertRaises(store.DatasheetFetchError) as ctx:
                store.cache_datasheet("3003", server.url)
        finally:
            server.stop()

        self.assertIn("not a PDF", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(store._datasheets_dir(), "3003.pdf")))

    def test_002c_an_empty_body_served_as_application_pdf_is_refused(self):
        """The header cannot be trusted either: a real 404 observed the same
        day (industrial.panasonic.com) returned Content-Type: application/pdf
        with Content-Length: 0. A content-type check passes exactly the case
        it is meant to catch, which is why this validates magic bytes."""
        server = _OneShotServer(200, b"", content_type="application/pdf")
        try:
            with self.assertRaises(store.DatasheetFetchError):
                store.cache_datasheet("CR2032", server.url)
        finally:
            server.stop()

        self.assertFalse(os.path.exists(os.path.join(store._datasheets_dir(), "CR2032.pdf")))

    def test_003_an_unreachable_host_raises_a_clean_error(self):
        with self.assertRaises(store.DatasheetFetchError):
            store.cache_datasheet("ATtiny85", "http://127.0.0.1:1/nope.pdf")

    def test_004_a_part_number_with_a_path_separator_is_rejected_before_any_fetch(self):
        with self.assertRaises(store.DatasheetFetchError):
            store.cache_datasheet("../../etc/passwd", "http://127.0.0.1:1/nope.pdf")

    def test_005_a_real_https_fetch_passes_real_tls_certificate_verification(self):
        """Real end-to-end verification of the Components tab found this:
        this Python build's own default SSL context fails closed with
        CERTIFICATE_VERIFY_FAILED on every real HTTPS host, because its
        baked-in default cert path is a path from the build's own CI
        runner, not a real path on any actual machine. The _OneShotServer
        tests above are plain HTTP and can never catch this -- only a
        real HTTPS fetch exercises certificate verification at all. Skips
        cleanly on a genuine network-level failure (no internet access),
        but a certificate error is a real regression, not something to
        skip past."""
        try:
            path = store.cache_datasheet("test-tls-part", "https://www.python.org/robots.txt")
        except store.DatasheetFetchError as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                raise
            self.skipTest(f"No real network access for this test: {e}")

        with open(path, "rb") as f:
            self.assertTrue(f.read())

    def test_006_a_stalled_read_after_a_successful_connection_raises_a_clean_error(self):
        """The real bug this test exists to catch: found running a real
        search+cache loop against real search-agent output where one
        candidate's URL connected fine but stalled reading the body.
        Before this fix, that raised a bare TimeoutError that escaped
        cache_datasheet entirely -- crashing the route instead of
        surfacing a clean DatasheetFetchError."""
        original_timeout = store._DATASHEET_FETCH_TIMEOUT_S
        store._DATASHEET_FETCH_TIMEOUT_S = 0.3
        server = _StallingServer()
        try:
            with self.assertRaises(store.DatasheetFetchError):
                store.cache_datasheet("ATtiny85", server.url)
        finally:
            store._DATASHEET_FETCH_TIMEOUT_S = original_timeout
            server.stop()


def _find_kicad_cli():
    """Same shutil.which-first, real-known-path-fallback convention
    freecad_bridge.py already uses for freecadcmd. Test-only -- locating
    kicad-cli robustly for *production* use is SPEC-309's own named open
    question, not this context's job to solve."""
    on_path = shutil.which("kicad-cli")
    if on_path:
        return on_path
    macos_path = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
    if os.path.exists(macos_path):
        return macos_path
    return None


_ATTINY85_PINS = [
    {"number": "1", "name": "RESET", "electrical_type": "bidirectional"},
    {"number": "2", "name": "PB3", "electrical_type": "input"},
    {"number": "3", "name": "PB4", "electrical_type": "output"},
    {"number": "4", "name": "GND", "electrical_type": "ground"},
    {"number": "5", "name": "PB0", "electrical_type": "bidirectional"},
    {"number": "6", "name": "PB1", "electrical_type": "bidirectional"},
    {"number": "7", "name": "PB2", "electrical_type": "bidirectional"},
    {"number": "8", "name": "VCC", "electrical_type": "power"},
]


class TestLayoutPins(unittest.TestCase):

    def test_001_splits_pins_evenly_left_and_right(self):
        layout = store._layout_pins(_ATTINY85_PINS)
        left = [p for p in layout["pins"] if p["angle"] == 0]
        right = [p for p in layout["pins"] if p["angle"] == 180]
        self.assertEqual(len(left), 4)
        self.assertEqual(len(right), 4)

    def test_002_left_pins_are_negative_x_right_pins_are_positive_x(self):
        """Matches real KiCad convention confirmed by reading actual
        .kicad_sym files: angle 0 on the left (negative x), angle 180 on
        the right (positive x)."""
        layout = store._layout_pins(_ATTINY85_PINS)
        for pin in layout["pins"]:
            if pin["angle"] == 0:
                self.assertLess(pin["x"], 0)
            else:
                self.assertGreater(pin["x"], 0)

    def test_003_pins_on_one_side_are_stacked_on_the_real_2_54mm_grid(self):
        layout = store._layout_pins(_ATTINY85_PINS)
        left_ys = sorted(p["y"] for p in layout["pins"] if p["angle"] == 0)
        gaps = [round(b - a, 4) for a, b in zip(left_ys, left_ys[1:])]
        self.assertTrue(all(gap == store._KICAD_PIN_PITCH_MM for gap in gaps))

    def test_004_an_odd_pin_count_puts_the_extra_pin_on_the_left(self):
        layout = store._layout_pins(_ATTINY85_PINS[:5])
        left = [p for p in layout["pins"] if p["angle"] == 0]
        right = [p for p in layout["pins"] if p["angle"] == 180]
        self.assertEqual(len(left), 3)
        self.assertEqual(len(right), 2)


class TestExportSymbolKicadSym(LibraryStoreTestCase):

    def test_001_writes_a_real_file_to_the_symbols_directory(self):
        store.save_symbol({"symbol_id": "SOIC-8_8pin", "reference_prefix": "U", "pins": _ATTINY85_PINS})
        path = store.export_symbol_kicad_sym("SOIC-8_8pin")
        self.assertTrue(path.endswith(os.path.join("library", "symbols", "SOIC-8_8pin.kicad_sym")))
        with open(path) as f:
            text = f.read()
        self.assertIn('(kicad_symbol_lib', text)
        self.assertIn('"SOIC-8_8pin"', text)

    def test_002_a_real_kicad_cli_parses_and_renders_the_exported_file(self):
        """The real bar SPEC-307 §2 itself names: a file KiCad's own
        parser accepts and can render, not just plausible-looking text.
        Skips cleanly if kicad-cli isn't found on this machine, same
        convention every other real-tool test in this repo uses."""
        kicad_cli = _find_kicad_cli()
        if not kicad_cli:
            self.skipTest("kicad-cli not found on this machine.")

        store.save_symbol({"symbol_id": "SOIC-8_8pin", "reference_prefix": "U", "pins": _ATTINY85_PINS})
        path = store.export_symbol_kicad_sym("SOIC-8_8pin")

        with tempfile.TemporaryDirectory() as svg_dir:
            result = subprocess.run(
                [kicad_cli, "sym", "export", "svg", "-o", svg_dir, path],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            svgs = [f for f in os.listdir(svg_dir) if f.endswith(".svg")]
            self.assertEqual(len(svgs), 1)

    def test_003_escapes_a_pin_name_containing_a_double_quote(self):
        """A malformed .kicad_sym from an unescaped quote is a real,
        not hypothetical, risk -- pin names come from an LLM extraction
        (SPEC-202), which never guarantees clean input."""
        pins = [{"number": "1", "name": 'weird"name', "electrical_type": "passive"}]
        store.save_symbol({"symbol_id": "weird_1pin", "reference_prefix": "U", "pins": pins})
        path = store.export_symbol_kicad_sym("weird_1pin")
        with open(path) as f:
            text = f.read()
        self.assertIn('weird\\"name', text)

    def test_004_a_raw_kicad_sym_backed_record_writes_verbatim_not_the_hand_built_path(self):
        """CTX-314.2: a symbol imported from a real community library
        carries its own real raw_kicad_sym text -- this must be written
        as-is, never re-derived through _build_kicad_sym_text (which
        would silently discard a real multi-symbol vendor file down to
        this app's own single-symbol generated shape). No pins field at
        all on this record -- the raw-content branch must not need one."""
        raw_text = '(kicad_symbol_lib\n\t(version 20251024)\n\t(symbol "Real_Vendor_Symbol"\n\t)\n)\n'
        store.save_symbol({"symbol_id": "vendor__lib__Real_Vendor_Symbol", "raw_kicad_sym": raw_text})
        path = store.export_symbol_kicad_sym("vendor__lib__Real_Vendor_Symbol")
        with open(path) as f:
            self.assertEqual(f.read(), raw_text)

    def test_005_a_real_kicad_cli_parses_and_renders_a_raw_backed_symbol(self):
        """Same real bar test_002 already holds itself to, applied to
        the new raw-content branch -- reuses _build_kicad_sym_text's
        own real, valid output as the 'raw' fixture, since it's already
        proven-parseable real KiCad S-expression text."""
        kicad_cli = _find_kicad_cli()
        if not kicad_cli:
            self.skipTest("kicad-cli not found on this machine.")

        raw_text = store._build_kicad_sym_text(
            {"symbol_id": "Raw_SOIC-8", "reference_prefix": "U", "pins": _ATTINY85_PINS}
        )
        store.save_symbol({"symbol_id": "Raw_SOIC-8", "raw_kicad_sym": raw_text})
        path = store.export_symbol_kicad_sym("Raw_SOIC-8")

        with tempfile.TemporaryDirectory() as svg_dir:
            result = subprocess.run(
                [kicad_cli, "sym", "export", "svg", "-o", svg_dir, path],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)


_SOIC8_PADS = [
    {"number": str(i), "x_mm": -2.0 if i <= 4 else 2.0, "y_mm": (i - 2.5) * 1.27 if i <= 4 else (6.5 - i) * 1.27,
     "width_mm": 1.5, "height_mm": 0.6, "pad_type": "smd", "drill_mm": None}
    for i in range(1, 9)
]
_SOIC8_COURTYARD = {"length_mm": 5.4, "width_mm": 4.4}


class TestExportFootprintKicadMod(LibraryStoreTestCase):
    """CTX-308.6: SPEC-308 §1's "export it to a real .pretty library" --
    only meaningful for a footprint with real pad geometry, which today
    only a CTX-308.5-generated footprint has."""

    def test_001_writes_a_real_file_to_a_real_pretty_directory(self):
        """KiCad's own convention: a footprint library is a directory
        named *.pretty/, unlike a symbol library's single .kicad_sym
        file -- confirmed by reading real footprint libraries on this
        machine before writing this, not assumed."""
        store.save_footprint({
            "footprint_id": "generated__ATtiny85", "pads": _SOIC8_PADS, "courtyard": _SOIC8_COURTYARD,
        })
        path = store.export_footprint_kicad_mod("generated__ATtiny85")
        self.assertTrue(
            path.endswith(os.path.join("library", "footprints.pretty", "generated__ATtiny85.kicad_mod"))
        )
        with open(path) as f:
            text = f.read()
        self.assertIn('(footprint "generated__ATtiny85"', text)
        self.assertEqual(text.count('(pad '), 8)

    def test_002_a_real_kicad_cli_parses_and_renders_the_exported_file(self):
        """The real bar this repo holds itself to: a file KiCad's own
        parser accepts and can render, not just plausible-looking text.
        kicad-cli fp export svg (unlike sym export svg) takes the
        containing .pretty directory plus --footprint, not the file
        path directly -- confirmed by actually running it before writing
        this assertion, not assumed from the --help text alone. Skips
        cleanly if kicad-cli isn't found, same convention as symbol
        export's own test."""
        kicad_cli = _find_kicad_cli()
        if not kicad_cli:
            self.skipTest("kicad-cli not found on this machine.")

        store.save_footprint({
            "footprint_id": "generated__ATtiny85", "pads": _SOIC8_PADS, "courtyard": _SOIC8_COURTYARD,
        })
        path = store.export_footprint_kicad_mod("generated__ATtiny85")
        pretty_dir = os.path.dirname(path)

        with tempfile.TemporaryDirectory() as svg_dir:
            result = subprocess.run(
                [kicad_cli, "fp", "export", "svg", "-o", svg_dir, "--footprint", "generated__ATtiny85", pretty_dir],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            svgs = [f for f in os.listdir(svg_dir) if f.endswith(".svg")]
            self.assertEqual(len(svgs), 1)

    def test_003_a_thru_hole_pad_round_trips_through_real_kicad_cli_too(self):
        """Real, not hypothetical: DIP packages (kicad_write.
        THROUGH_HOLE_PACKAGES) produce pth pads with a real drill --
        the smd-only test above doesn't exercise that branch."""
        kicad_cli = _find_kicad_cli()
        if not kicad_cli:
            self.skipTest("kicad-cli not found on this machine.")

        pads = [
            {"number": "1", "x_mm": -1.27, "y_mm": -3.81, "width_mm": 1.6, "height_mm": 1.6,
             "pad_type": "pth", "drill_mm": 0.8},
        ]
        store.save_footprint({
            "footprint_id": "generated__DIPTest", "pads": pads, "courtyard": {"length_mm": 10.0, "width_mm": 8.0},
        })
        path = store.export_footprint_kicad_mod("generated__DIPTest")
        pretty_dir = os.path.dirname(path)

        with open(path) as f:
            text = f.read()
        self.assertIn("thru_hole", text)
        self.assertIn("(drill 0.8)", text)

        with tempfile.TemporaryDirectory() as svg_dir:
            result = subprocess.run(
                [kicad_cli, "fp", "export", "svg", "-o", svg_dir, "--footprint", "generated__DIPTest", pretty_dir],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_004b_an_all_smd_footprint_is_tagged_attr_smd(self):
        store.save_footprint({
            "footprint_id": "generated__ATtiny85", "pads": _SOIC8_PADS, "courtyard": _SOIC8_COURTYARD,
        })
        path = store.export_footprint_kicad_mod("generated__ATtiny85")

        with open(path) as f:
            text = f.read()
        self.assertIn("(attr smd)", text)

    def test_004c_an_all_through_hole_footprint_is_tagged_attr_through_hole_not_smd(self):
        # A real bug found by live user testing: this line was
        # previously hardcoded to `(attr smd)` regardless of the
        # footprint's own real pads, so an exported through-hole (DIP)
        # footprint claimed to be surface-mount in KiCad.
        pads = [
            {"number": "1", "x_mm": -1.27, "y_mm": -3.81, "width_mm": 1.6, "height_mm": 1.6,
             "pad_type": "pth", "drill_mm": 0.8},
        ]
        store.save_footprint({
            "footprint_id": "generated__DIPTest", "pads": pads, "courtyard": {"length_mm": 10.0, "width_mm": 8.0},
        })
        path = store.export_footprint_kicad_mod("generated__DIPTest")

        with open(path) as f:
            text = f.read()
        self.assertIn("(attr through_hole)", text)
        self.assertNotIn("(attr smd)", text)

    def test_004_a_footprint_with_no_pad_geometry_fails_closed_not_a_meaningless_file(self):
        """A footprint attached via CTX-308.2's own find flow
        ({footprint_id, library, footprint_name}, no pads at all) has
        nothing real to export -- it's already a real .kicad_mod
        sitting in the user's own KiCad library. Must raise, not write
        an empty/meaningless file."""
        store.save_footprint({"footprint_id": "MyPCBLibs__MP1584EN_5V_Module", "library": "MyPCBLibs",
                               "footprint_name": "MP1584EN_5V_Module"})
        with self.assertRaises(store.SchemaValidationError):
            store.export_footprint_kicad_mod("MyPCBLibs__MP1584EN_5V_Module")

    def test_005_a_raw_kicad_mod_backed_record_writes_verbatim_skipping_the_pads_check(self):
        """CTX-314.2: a footprint imported from a real community library
        carries its own real raw_kicad_mod text and no pads/courtyard
        fields at all -- must skip the fail-closed check above entirely
        (real geometry already lives in the raw text) and write it
        verbatim, never re-derived through _build_kicad_mod_text."""
        raw_text = '(footprint "Real_Vendor_Footprint"\n\t(version 20221018)\n\t(layer "F.Cu")\n)\n'
        store.save_footprint({"footprint_id": "vendor__lib__Real_Vendor_Footprint", "raw_kicad_mod": raw_text})
        path = store.export_footprint_kicad_mod("vendor__lib__Real_Vendor_Footprint")
        with open(path) as f:
            self.assertEqual(f.read(), raw_text)

    def test_006_a_real_kicad_cli_parses_and_renders_a_raw_backed_footprint(self):
        """Same real bar test_002 already holds itself to, applied to
        the new raw-content branch -- reuses _build_kicad_mod_text's own
        real, valid output as the 'raw' fixture."""
        kicad_cli = _find_kicad_cli()
        if not kicad_cli:
            self.skipTest("kicad-cli not found on this machine.")

        raw_text = store._build_kicad_mod_text(
            {"footprint_id": "Raw_ATtiny85", "pads": _SOIC8_PADS, "courtyard": _SOIC8_COURTYARD}
        )
        store.save_footprint({"footprint_id": "Raw_ATtiny85", "raw_kicad_mod": raw_text})
        path = store.export_footprint_kicad_mod("Raw_ATtiny85")
        pretty_dir = os.path.dirname(path)

        with tempfile.TemporaryDirectory() as svg_dir:
            result = subprocess.run(
                [kicad_cli, "fp", "export", "svg", "-o", svg_dir, "--footprint", "Raw_ATtiny85", pretty_dir],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

    # Deliberately no "footprint_id containing a double quote" test here,
    # unlike TestExportSymbolKicadSym.test_003: footprint_id doubles as
    # this file's own on-disk filename (unlike a symbol's pin *name*,
    # which is just text inside the file) -- a literal `"` is invalid on
    # Windows, the same class of bug CTX-308.4 already found and fixed
    # for `:`. footprint_id is already required to be filesystem-safe by
    # that established convention, so this isn't a realistic input to
    # defend against here. _sexpr_str's own escaping is already covered
    # by the symbol export test above (same shared helper).


_VALID_DESIGN_GUIDANCE = {
    "generated_at": "2026-08-20T00:00:00+00:00",
    "content_hash": "deadbeef",
    "document_revision": None,
    "categories": {"reset": [{"quote": "real quote", "page": 5, "category": "reset"}], "layout": []},
}


class TestContentHashOfFile(unittest.TestCase):

    def test_001_hashes_real_file_bytes(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"real content")
            path = f.name
        try:
            expected = hashlib.sha256(b"real content").hexdigest()
            self.assertEqual(store.content_hash_of_file(path), expected)
        finally:
            os.remove(path)

    def test_002_different_real_content_hashes_differently(self):
        with tempfile.NamedTemporaryFile(delete=False) as f1, tempfile.NamedTemporaryFile(delete=False) as f2:
            f1.write(b"content one")
            f2.write(b"content two")
            path1, path2 = f1.name, f2.name
        try:
            self.assertNotEqual(store.content_hash_of_file(path1), store.content_hash_of_file(path2))
        finally:
            os.remove(path1)
            os.remove(path2)


class TestEnsureDatasheetCached(LibraryStoreTestCase):

    def test_001_an_already_cached_real_file_is_returned_without_a_new_fetch(self):
        server = _OneShotServer(200, b"%PDF-1.4 first fetch")
        try:
            first_path = store.cache_datasheet("ATtiny85", server.url)
        finally:
            server.stop()

        # A server that would fail any real fetch -- proves the second
        # call never actually reaches the network, only the filesystem.
        path = store.ensure_datasheet_cached("ATtiny85", "http://127.0.0.1:1/unreachable.pdf")

        self.assertEqual(path, first_path)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"%PDF-1.4 first fetch")

    def test_002_a_real_cache_miss_fetches_and_caches_for_real(self):
        server = _OneShotServer(200, b"%PDF-1.4 real fetch")
        try:
            path = store.ensure_datasheet_cached("ATtiny85", server.url)
        finally:
            server.stop()

        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"%PDF-1.4 real fetch")

    def test_003_a_real_unsafe_part_number_is_rejected_before_any_fetch(self):
        with self.assertRaises(store.DatasheetFetchError):
            store.ensure_datasheet_cached("../../etc/passwd", "http://127.0.0.1:1/nope.pdf")


class TestDesignGuidanceStorage(LibraryStoreTestCase):

    def _valid_part(self, **overrides):
        provenance = {field: {"source": "datasheet_pdf"} for field in store.PART_PROVENANCE_REQUIRED_FIELDS}
        part = {
            "part_id": "ATtiny85", "manufacturer": "Microchip", "package": "SOIC-8", "pins": [],
            "datasheet_url": "https://example.com/x.pdf", "package_dimensions": {}, "courtyard": {},
            "provenance": provenance,
        }
        part.update(overrides)
        return part

    def test_001_load_part_backfills_design_guidance_as_none_not_an_empty_dict(self):
        store.save_part(self._valid_part())

        loaded = store.load_part("ATtiny85")

        self.assertIsNone(loaded["design_guidance"])

    def test_001b_save_part_itself_returns_a_real_backfilled_design_guidance_key(self):
        # CTX-205.4: a real inconsistency found while typing this field on
        # the frontend -- library.save_confirmed_part's own real response
        # is save_part's return value directly, never routed through
        # load_part first, so save_part must backfill this key itself too.
        record = store.save_part(self._valid_part())

        self.assertIn("design_guidance", record)
        self.assertIsNone(record["design_guidance"])

    def test_002_save_part_accepts_a_real_valid_design_guidance(self):
        store.save_part(self._valid_part(design_guidance=_VALID_DESIGN_GUIDANCE))

        loaded = store.load_part("ATtiny85")

        self.assertEqual(loaded["design_guidance"]["categories"]["reset"][0]["quote"], "real quote")

    def test_003_save_part_rejects_design_guidance_missing_the_real_categories_key(self):
        with self.assertRaises(store.SchemaValidationError):
            store.save_part(self._valid_part(design_guidance={"generated_at": "x"}))

    def test_004_save_part_rejects_a_real_item_missing_a_required_citation_field(self):
        malformed = {**_VALID_DESIGN_GUIDANCE, "categories": {"reset": [{"quote": "x"}]}}
        with self.assertRaises(store.SchemaValidationError):
            store.save_part(self._valid_part(design_guidance=malformed))

    def test_005_save_part_design_guidance_persists_onto_the_real_current_record(self):
        store.save_part(self._valid_part())

        updated = store.save_part_design_guidance(
            "ATtiny85", "real-content-hash", {"reset": [{"quote": "x", "page": 1, "category": "reset"}]},
        )

        self.assertEqual(updated["design_guidance"]["content_hash"], "real-content-hash")
        self.assertIsNone(updated["design_guidance"]["document_revision"])
        reloaded = store.load_part("ATtiny85")
        self.assertEqual(reloaded["design_guidance"]["categories"]["reset"][0]["page"], 1)

    def test_006_save_part_design_guidance_preserves_the_real_records_other_fields(self):
        store.save_part(self._valid_part())

        updated = store.save_part_design_guidance("ATtiny85", "hash", {"reset": []})

        self.assertEqual(updated["manufacturer"], "Microchip")

    def test_007_save_part_design_guidance_persists_real_category_summaries(self):
        # CTX-205.7: SPEC-205 §2.1.1's real plain-language layer.
        store.save_part(self._valid_part())

        updated = store.save_part_design_guidance(
            "ATtiny85", "hash", {"reset": [{"quote": "x", "page": 1, "category": "reset"}]},
            {"reset": "A real plain-language summary."},
        )

        self.assertEqual(updated["design_guidance"]["category_summaries"]["reset"], "A real plain-language summary.")

    def test_008_save_part_design_guidance_defaults_category_summaries_to_an_empty_dict(self):
        store.save_part(self._valid_part())

        updated = store.save_part_design_guidance("ATtiny85", "hash", {"reset": []})

        self.assertEqual(updated["design_guidance"]["category_summaries"], {})

    def test_009_load_part_backfills_category_summaries_for_a_pre_ctx_205_7_record(self):
        # A real record generated before CTX-205.7 shipped has no
        # `category_summaries` key at all -- backfilled to `{}` on read,
        # never re-triggering generation or raising.
        pre_ctx_205_7 = {**_VALID_DESIGN_GUIDANCE}
        store.save_part(self._valid_part(design_guidance=pre_ctx_205_7))

        loaded = store.load_part("ATtiny85")

        self.assertEqual(loaded["design_guidance"]["category_summaries"], {})

    def test_010_save_part_rejects_a_real_non_string_non_null_summary(self):
        malformed = {**_VALID_DESIGN_GUIDANCE, "category_summaries": {"reset": 42}}
        with self.assertRaises(store.SchemaValidationError):
            store.save_part(self._valid_part(design_guidance=malformed))

    def test_011_save_part_accepts_a_real_null_summary_for_a_category_with_no_items(self):
        valid = {**_VALID_DESIGN_GUIDANCE, "category_summaries": {"reset": "text", "layout": None}}
        store.save_part(self._valid_part(design_guidance=valid))

        loaded = store.load_part("ATtiny85")

        self.assertIsNone(loaded["design_guidance"]["category_summaries"]["layout"])


_VALID_CONNECTION_GUIDANCE = {
    "generated_at": "2026-08-21T00:00:00+00:00",
    "pins_hash": "irrelevant-for-the-shape-check",
    "pin_guidance": [{"pin_number": "8", "guidance": "Add a 100nF decoupling capacitor."}],
    "general_notes": "Tie unused pins to a known state.",
    "provenance": {"provider": "anthropic", "model": "claude-sonnet-5"},
}


class TestConnectionGuidanceStorage(LibraryStoreTestCase):
    """CTX-206.1 (SPEC-206 §2.4): persisting `kicad.generate_connection_guidance`'s
    result onto the Part record, the prerequisite SPEC-318's Components
    agent needs. Mirrors TestDesignGuidanceStorage's own shape --
    real backfill-to-None, real shape validation, real persist-and-reload."""

    def _valid_part(self, **overrides):
        provenance = {field: {"source": "datasheet_pdf"} for field in store.PART_PROVENANCE_REQUIRED_FIELDS}
        part = {
            "part_id": "ATtiny85", "manufacturer": "Microchip", "package": "SOIC-8", "pins": _ATTINY85_PINS,
            "datasheet_url": "https://example.com/x.pdf", "package_dimensions": {}, "courtyard": {},
            "provenance": provenance,
        }
        part.update(overrides)
        return part

    def test_001_load_part_backfills_connection_guidance_as_none_not_an_empty_dict(self):
        store.save_part(self._valid_part())

        loaded = store.load_part("ATtiny85")

        self.assertIsNone(loaded["connection_guidance"])

    def test_001b_save_part_itself_returns_a_real_backfilled_connection_guidance_key(self):
        record = store.save_part(self._valid_part())

        self.assertIn("connection_guidance", record)
        self.assertIsNone(record["connection_guidance"])

    def test_002_save_part_accepts_a_real_valid_connection_guidance(self):
        store.save_part(self._valid_part(connection_guidance=_VALID_CONNECTION_GUIDANCE))

        loaded = store.load_part("ATtiny85")

        self.assertEqual(loaded["connection_guidance"]["general_notes"], "Tie unused pins to a known state.")

    def test_003_save_part_rejects_connection_guidance_missing_a_required_field(self):
        malformed = {k: v for k, v in _VALID_CONNECTION_GUIDANCE.items() if k != "pins_hash"}
        with self.assertRaises(store.SchemaValidationError):
            store.save_part(self._valid_part(connection_guidance=malformed))

    def test_004_save_part_rejects_a_pin_guidance_entry_missing_guidance(self):
        malformed = {**_VALID_CONNECTION_GUIDANCE, "pin_guidance": [{"pin_number": "8"}]}
        with self.assertRaises(store.SchemaValidationError):
            store.save_part(self._valid_part(connection_guidance=malformed))

    def test_004b_save_part_rejects_a_non_dict_provenance(self):
        malformed = {**_VALID_CONNECTION_GUIDANCE, "provenance": "anthropic"}
        with self.assertRaises(store.SchemaValidationError):
            store.save_part(self._valid_part(connection_guidance=malformed))

    def test_005_save_part_connection_guidance_persists_onto_the_real_current_record(self):
        store.save_part(self._valid_part())

        updated = store.save_part_connection_guidance(
            "ATtiny85",
            pin_guidance=[{"pin_number": "8", "guidance": "Decouple with 100nF."}],
            general_notes="notes",
            provenance={"provider": "anthropic", "model": "claude-sonnet-5"},
        )

        self.assertEqual(updated["connection_guidance"]["general_notes"], "notes")
        reloaded = store.load_part("ATtiny85")
        self.assertEqual(reloaded["connection_guidance"]["pin_guidance"][0]["pin_number"], "8")

    def test_006_save_part_connection_guidance_preserves_the_real_records_other_fields(self):
        store.save_part(self._valid_part())

        updated = store.save_part_connection_guidance(
            "ATtiny85", pin_guidance=[], general_notes="", provenance={"provider": "p", "model": "m"},
        )

        self.assertEqual(updated["manufacturer"], "Microchip")

    def test_007_save_part_connection_guidance_computes_pins_hash_from_the_real_current_pins(self):
        store.save_part(self._valid_part())

        updated = store.save_part_connection_guidance(
            "ATtiny85", pin_guidance=[], general_notes="", provenance={"provider": "p", "model": "m"},
        )

        self.assertEqual(updated["connection_guidance"]["pins_hash"], store.compute_pins_hash(_ATTINY85_PINS))

    def test_008_compute_pins_hash_is_deterministic_and_content_sensitive(self):
        same_again = list(_ATTINY85_PINS)
        different = _ATTINY85_PINS + [{"number": "1", "name": "RESET", "electrical_type": "bidirectional"}]

        self.assertEqual(store.compute_pins_hash(_ATTINY85_PINS), store.compute_pins_hash(same_again))
        self.assertNotEqual(store.compute_pins_hash(_ATTINY85_PINS), store.compute_pins_hash(different))


if __name__ == '__main__':
    unittest.main()


class TestProjectCheckResults(LibraryStoreTestCase):
    """`Project.last_results[area]`, written per area.

    Built for SPEC-319 §2.1, to feed the review agents stored ERC/DRC
    findings. That is no longer what grounds them: `_check_status_note` now
    RUNS the check on request, because `kicad-cli` reads a closed file and a
    stored finding can go stale in ways this app cannot detect (the user can
    fix everything in KiCad and never tell us).

    This record is kept for a genuinely different job -- `OverviewDashboard`
    reads `last_results` to show per-area status -- so it is still written,
    just no longer load-bearing for an agent's grounding."""

    def _result(self, n=3):
        return {
            "checked_at": "2026-09-02T00:00:00Z",
            "source_path": "/p/b.kicad_pcb",
            "violation_count": 0,
            "unconnected_count": n,
            "findings": [
                {"severity": "error", "type": "unconnected_items",
                 "description": f"Missing connection {i}"} for i in range(n)
            ],
        }

    def test_001_a_check_result_is_readable_after_a_restart(self):
        store.save_project({"name": "P"})
        store.set_project_check_result("P", "pcb", self._result())

        stored = store.load_project("P")["last_results"]["pcb"]
        self.assertEqual(stored["unconnected_count"], 3)
        self.assertEqual(len(stored["findings"]), 3)

    def test_002_areas_do_not_overwrite_each_other(self):
        store.save_project({"name": "P"})
        store.set_project_check_result("P", "pcb", self._result())
        store.set_project_check_result("P", "schematic", {"violation_count": 0, "findings": []})

        last = store.load_project("P")["last_results"]
        self.assertIn("pcb", last)
        self.assertIn("schematic", last)
        self.assertEqual(last["pcb"]["unconnected_count"], 3)

    def test_003_an_existing_enclosure_result_survives(self):
        """The one area that already wrote here must not be clobbered."""
        store.save_project({"name": "P", "last_results": {"enclosure": {"glb_path": "/x.glb"}}})
        store.set_project_check_result("P", "pcb", self._result())

        last = store.load_project("P")["last_results"]
        self.assertEqual(last["enclosure"]["glb_path"], "/x.glb")

    def test_004_a_huge_finding_list_is_capped_and_says_so(self):
        """This record is read straight into an LLM context window. A real
        board can produce hundreds of findings."""
        store.save_project({"name": "P"})
        store.set_project_check_result("P", "pcb", self._result(n=200))

        stored = store.load_project("P")["last_results"]["pcb"]
        self.assertEqual(len(stored["findings"]), 25)
        self.assertEqual(stored["findings_omitted"], 175)
        # The COUNT stays exact even though the detail is capped -- an agent
        # told "3 of 200" must not conclude the board has 25 problems.
        self.assertEqual(stored["unconnected_count"], 200)

    def test_005_an_unknown_area_is_refused(self):
        store.save_project({"name": "P"})
        with self.assertRaises(store.SchemaValidationError):
            store.set_project_check_result("P", "firmware", self._result())

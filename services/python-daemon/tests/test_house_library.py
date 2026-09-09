"""Tests for the global board-house library -- SPEC-342, CTX-342.1.

The library is global (shared across projects) while the *choice* is per
project, and a project also records the numbers it was actually checked
against, because a profile is a historical record rather than a live pointer.

These call the real store. `CTX-340.2` shipped a persistence route that raised
on every call while 890 tests agreed it worked, because every one of them
mocked it -- a mock asserts the caller's intent, and the intent was correct.
"""

import os
import tempfile
import unittest

import capability_profile
import library_store


def _house(house_id="house-a", name="House A", recorded_on="2026-09-09", **values):
    fields = {"min_track_width": 0.15, "min_drill": 0.35, "min_annular_ring": 0.15}
    fields.update(values)
    profile = capability_profile.starter_profile(
        name, "https://example.invalid/capabilities", recorded_on, **fields
    )
    profile["house_id"] = house_id
    return profile


class HouseLibraryTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        library_store.configure(storage_root=self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(library_store.configure, storage_root=None)

    # TEST-001
    def test_001_a_house_round_trips_and_appears_in_the_list(self):
        library_store.save_house(_house())
        self.assertEqual(library_store.list_houses(), ["house-a"])
        loaded = library_store.load_house("house-a")
        self.assertEqual(loaded["house_name"], "House A")
        self.assertEqual(loaded["min_drill"], 0.35)

    def test_the_library_is_global_rather_than_per_project(self):
        # The whole point of SPEC-342 section 2.1: one house, many projects.
        library_store.save_house(_house())
        library_store.save_project({"name": "alpha"})
        library_store.save_project({"name": "beta"})
        self.assertEqual(library_store.list_houses(), ["house-a"])

    # TEST-002
    def test_002_a_house_that_fails_validation_is_refused_at_save_time(self):
        broken = _house()
        del broken["provenance"]["min_drill"]
        with self.assertRaises(library_store.SchemaValidationError):
            library_store.save_house(broken)
        self.assertEqual(library_store.list_houses(), [], "and nothing half-written is left")

    def test_a_house_without_an_id_is_refused(self):
        nameless = _house()
        del nameless["house_id"]
        with self.assertRaises(library_store.SchemaValidationError):
            library_store.save_house(nameless)

    def test_a_house_id_cannot_escape_the_library_directory(self):
        with self.assertRaises(library_store.SchemaValidationError):
            library_store.save_house(_house(house_id="../../etc/passwd"))

    # TEST-003
    def test_003_deleting_a_house_reports_the_projects_that_referenced_it(self):
        library_store.save_house(_house())
        chosen = _house()
        library_store.save_project({"name": "alpha"})
        library_store.set_project_fabrication_profile("alpha", chosen)
        library_store.save_project({"name": "beta"})

        result = library_store.delete_house("house-a")

        self.assertEqual(result["still_referenced_by"], ["alpha"])
        self.assertEqual(library_store.list_houses(), [])

    # TEST-004
    def test_004_a_project_keeps_the_numbers_it_was_checked_against(self):
        """Not a bare reference. SPEC-342 section 2.1: a profile is a historical
        record, so a project must still be able to say what its findings were
        produced against after the library moves on."""
        library_store.save_house(_house())
        library_store.save_project({"name": "alpha"})
        library_store.set_project_fabrication_profile("alpha", _house())

        library_store.delete_house("house-a")

        kept = library_store.load_project("alpha")["fabrication_profile"]
        self.assertEqual(kept["min_drill"], 0.35, "the numbers survive the house being removed")

    # TEST-005
    def test_005_editing_a_house_does_not_rewrite_what_a_project_checked(self):
        library_store.save_house(_house())
        library_store.save_project({"name": "alpha"})
        library_store.set_project_fabrication_profile("alpha", _house())

        # The shared house is revised later, as SPEC-342 section 3 warns it will be.
        library_store.save_house(_house(min_drill=0.2))

        self.assertEqual(library_store.load_house("house-a")["min_drill"], 0.2)
        self.assertEqual(
            library_store.load_project("alpha")["fabrication_profile"]["min_drill"], 0.35,
            "the project's findings were produced against the old number and still say so",
        )

    def test_a_missing_house_is_an_error_rather_than_an_empty_record(self):
        with self.assertRaises(FileNotFoundError):
            library_store.load_house("never-existed")
        with self.assertRaises(FileNotFoundError):
            library_store.delete_house("never-existed")


class CloneTests(unittest.TestCase):
    """SPEC-342 section 2.2: the operation that makes the library usable."""

    # TEST-006
    def test_006_a_clone_resets_confirmation_on_every_field_it_did_not_change(self):
        base = _house()
        base["provenance"]["min_drill"]["confirmed_by_user"] = True
        base["provenance"]["min_track_width"]["confirmed_by_user"] = True

        cloned = capability_profile.clone(
            base, "House B", "house-b", "2026-09-09", overrides={"min_drill": 0.25}
        )

        # Inheriting a confirmation would claim a human checked this number
        # against a page they never read -- SPEC-114 section 2.6's whole point.
        self.assertFalse(cloned["provenance"]["min_drill"]["confirmed_by_user"])
        self.assertFalse(cloned["provenance"]["min_track_width"]["confirmed_by_user"])

    # TEST-007
    def test_007_a_clone_takes_its_own_recorded_on_date(self):
        base = _house(recorded_on="2020-01-01")
        cloned = capability_profile.clone(base, "House B", "house-b", "2026-09-09")
        for field in ("min_drill", "min_track_width"):
            self.assertEqual(cloned["provenance"][field]["recorded_on"], "2026-09-09")

    def test_a_clone_keeps_the_source_of_a_number_it_did_not_change(self):
        base = _house()
        cloned = capability_profile.clone(
            base, "House B", "house-b", "2026-09-09", overrides={"min_drill": 0.25}
        )
        self.assertEqual(
            cloned["provenance"]["min_track_width"]["source_url"],
            "https://example.invalid/capabilities",
            "an unchanged figure can still say where it came from",
        )
        self.assertEqual(
            cloned["provenance"]["min_drill"]["source_url"], "",
            "a number the user typed has no external source until they give it one",
        )

    def test_a_clone_carries_the_overridden_values(self):
        cloned = capability_profile.clone(
            _house(), "House B", "house-b", "2026-09-09", overrides={"min_drill": 0.25}
        )
        self.assertEqual(cloned["min_drill"], 0.25)
        self.assertEqual(cloned["min_track_width"], 0.15, "and everything else unchanged")
        self.assertEqual(cloned["house_name"], "House B")
        self.assertEqual(cloned["house_id"], "house-b")

    def test_an_unknown_override_field_is_refused(self):
        with self.assertRaises(capability_profile.ProfileValidationError):
            capability_profile.clone(
                _house(), "B", "b", "2026-09-09", overrides={"min_unicorn_width": 1.0}
            )

    def test_a_clone_is_a_valid_house_that_the_store_accepts(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        library_store.configure(storage_root=tmp.name)
        self.addCleanup(library_store.configure, storage_root=None)

        cloned = capability_profile.clone(_house(), "House B", "house-b", "2026-09-09")
        library_store.save_house(cloned)
        self.assertIn("house-b", library_store.list_houses())


if __name__ == "__main__":
    unittest.main()

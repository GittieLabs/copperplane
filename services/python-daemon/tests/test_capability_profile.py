"""Tests for the CapabilityProfile record and the fabrication review built on it.

`SPEC-114` section 2.6: every field is optional, an absent field produces no rule
rather than a guess, and each value carries its source URL, the date it was
recorded, and whether the user confirmed it. Mask dam and mask expansion are
recorded and displayed but can never be enforced through the sidecar.

CTX-114.1 Phases 2 to 5. The pure-record tests need no KiCad; the review tests
run against real `kicad-cli` and skip cleanly without it.
"""

import json
import os
import shutil
import tempfile
import unittest

import capability_profile
import fabrication_review
import kicad_cli
import kicad_dru

EXAMPLE_PROJECT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "examples", "Copperplane_Blink_LEDs"
))
EXAMPLE_PCB = os.path.join(EXAMPLE_PROJECT, "Copperplane_Blink_LEDs.kicad_pcb")


def _kicad_cli_available() -> bool:
    try:
        kicad_cli.find_kicad_cli()
        return True
    except Exception:
        return False


def _profile(**overrides):
    values = {
        "min_track_width": 0.127,
        "min_clearance": 0.127,
        "min_annular_ring": 0.13,
        "min_drill": 0.3,
        "min_hole_to_hole": 0.5,
        "min_silk_clearance": 0.15,
        "min_text_height": 1.0,
        "min_text_thickness": 0.15,
        "min_edge_clearance": 0.2,
    }
    values.update(overrides)
    return capability_profile.starter_profile(
        "Example Board House",
        "https://example.invalid/capabilities",
        "2026-09-08",
        **values
    )


class ProfileSchemaTests(unittest.TestCase):

    def test_a_profile_must_name_the_house_it_describes(self):
        with self.assertRaises(capability_profile.ProfileValidationError):
            capability_profile.validate({"min_track_width": 0.127, "provenance": {}})

    def test_a_value_without_provenance_is_refused(self):
        profile = _profile()
        del profile["provenance"]["min_track_width"]
        with self.assertRaises(capability_profile.ProfileValidationError):
            capability_profile.validate(profile)

    def test_provenance_must_carry_source_date_and_confirmation(self):
        profile = _profile()
        del profile["provenance"]["min_drill"]["recorded_on"]
        with self.assertRaises(capability_profile.ProfileValidationError):
            capability_profile.validate(profile)

    def test_a_non_positive_measurement_is_refused(self):
        with self.assertRaises(capability_profile.ProfileValidationError):
            _profile(min_track_width=0)

    def test_an_unknown_field_is_refused_rather_than_silently_kept(self):
        with self.assertRaises(capability_profile.ProfileValidationError):
            capability_profile.starter_profile(
                "H", "https://example.invalid", "2026-09-08", min_unicorn_width=1.0
            )

    def test_bundled_numbers_start_unconfirmed(self):
        profile = _profile()
        self.assertIn("min_drill", capability_profile.unconfirmed_fields(profile))
        self.assertFalse(
            capability_profile.field_provenance(profile, "min_drill")["confirmed_by_user"]
        )

    def test_staleness_is_reported_not_repaired(self):
        profile = _profile()
        self.assertFalse(capability_profile.is_stale(profile, today="2026-10-01"))
        self.assertTrue(capability_profile.is_stale(profile, today="2028-01-01"))
        # The record itself is untouched: it says what was actually checked.
        self.assertEqual(
            capability_profile.field_provenance(profile, "min_drill")["recorded_on"],
            "2026-09-08",
        )


class RuleGenerationTests(unittest.TestCase):

    # TEST-012
    def test_012_an_absent_field_produces_no_rule_rather_than_a_guess(self):
        full = capability_profile.to_rules(_profile())
        self.assertTrue(any(r[0] == "min-drill" for r in full))

        partial = _profile()
        partial["min_drill"] = None
        rules = capability_profile.to_rules(partial)
        self.assertFalse(
            any(r[0] == "min-drill" for r in rules),
            "an unpublished number must never become a rule the board is judged against",
        )

    # TEST-013
    def test_013_mask_fields_are_recorded_and_shown_but_never_emitted(self):
        profile = _profile()
        profile["min_mask_dam"] = 0.1
        profile["provenance"]["min_mask_dam"] = {
            "source_url": "https://example.invalid/capabilities",
            "recorded_on": "2026-09-08",
            "confirmed_by_user": False,
        }
        capability_profile.validate(profile)

        rules = capability_profile.to_rules(profile)
        self.assertFalse(any("mask" in r[1] for r in rules),
                         "no DRC constraint class exists for mask dam")
        self.assertIn("min_mask_dam", capability_profile.recorded_but_unenforceable(profile))
        notes = capability_profile.describe_unenforceable(profile)
        self.assertTrue(any("was not applied to your board" in n for n in notes),
                        "the gap has to be stated, not dropped quietly")

    def test_generated_rules_are_warnings_so_kicad_findings_stay_errors(self):
        for rule in capability_profile.to_rules(_profile()):
            self.assertEqual(rule[3], "warning")

    def test_every_generated_constraint_class_is_one_that_was_measured(self):
        for _, constraint, _, _ in capability_profile.to_rules(_profile()):
            self.assertIn(constraint, kicad_dru.CONFIRMED_CONSTRAINTS)

    def test_no_two_rules_share_a_constraint_class(self):
        """Measured in Phase 1: for one class the last rule wins.

        Two rules on the same class in one generated file would mean the first
        is silently discarded, so the generator must never emit such a pair."""
        classes = [c for _, c, _, _ in capability_profile.to_rules(_profile())]
        self.assertEqual(len(classes), len(set(classes)))


class OutcomeClassificationTests(unittest.TestCase):

    def test_the_silently_wrong_class_ranks_above_the_cosmetic_one(self):
        findings = [
            {"type": "silk_overlap"},
            {"type": "annular_width"},
            {"type": "drill_out_of_range"},
        ]
        ordered = [f["type"] for f in fabrication_review.rank_findings(findings)]
        self.assertEqual(
            ordered, ["annular_width", "drill_out_of_range", "silk_overlap"]
        )

    def test_an_unrecognised_finding_is_shown_not_buried(self):
        self.assertEqual(
            fabrication_review.classify({"type": "something_new_in_kicad_11"}),
            fabrication_review.WOULD_BE_REJECTED,
        )


class ProfilePersistenceTests(unittest.TestCase):
    """CTX-340.1 Phase 1: a profile belongs to one project.

    The failure this guards against is quiet and expensive: a profile leaking
    between projects means a user checks board B against board A's board house
    and is told, confidently, that it is fine."""

    def setUp(self):
        import library_store
        self.store = library_store
        self._tmp = tempfile.TemporaryDirectory()
        library_store.configure(storage_root=self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(library_store.configure, storage_root=None)

    # TEST-001
    def test_001_a_profile_round_trips_on_the_project_record(self):
        self.store.save_project({"name": "alpha"})
        profile = _profile()
        self.store.set_project_fabrication_profile("alpha", profile)

        reloaded = self.store.load_project("alpha")
        self.assertEqual(reloaded["fabrication_profile"]["house_name"], profile["house_name"])
        self.assertEqual(reloaded["fabrication_profile"]["min_drill"], 0.3)
        self.assertIn("provenance", reloaded["fabrication_profile"])

    # TEST-002
    def test_002_a_profile_does_not_leak_between_projects(self):
        self.store.save_project({"name": "alpha"})
        self.store.save_project({"name": "beta"})
        self.store.set_project_fabrication_profile("alpha", _profile())

        self.assertIsNone(
            self.store.load_project("beta")["fabrication_profile"],
            "the same design may go to two houses; a choice must not follow the user",
        )

    # TEST-003
    def test_003_an_invalid_profile_is_refused_at_store_time(self):
        self.store.save_project({"name": "alpha"})
        broken = _profile()
        del broken["provenance"]["min_drill"]

        with self.assertRaises(self.store.SchemaValidationError):
            self.store.set_project_fabrication_profile("alpha", broken)

        self.assertIsNone(
            self.store.load_project("alpha")["fabrication_profile"],
            "a refused profile must not be half-written",
        )

    # TEST-004
    def test_004_a_linked_project_carries_its_profile_in_the_folder_manifest(self):
        linked = os.path.join(self._tmp.name, "elsewhere")
        os.makedirs(linked, exist_ok=True)
        self.store.save_project({"name": "gamma", "directory": linked})
        self.store.set_project_fabrication_profile("gamma", _profile())

        manifest = os.path.join(linked, ".hardware-agent-studio", "project.json")
        self.assertTrue(os.path.exists(manifest), "a linked project stores its manifest in-folder")
        with open(manifest, encoding="utf-8") as handle:
            stored = json.load(handle)
        self.assertEqual(
            stored["fabrication_profile"]["house_name"], "Example Board House",
            "the profile has to travel with the folder, like intent does",
        )

    def test_a_project_saved_before_this_field_existed_reads_as_never_chosen(self):
        self.store.save_project({"name": "old"})
        record = self.store.load_project("old")
        self.assertIsNone(record["fabrication_profile"],
                          "None means never chosen, which is the honest empty state")

    def test_clearing_the_choice_is_distinct_from_an_empty_profile(self):
        self.store.save_project({"name": "alpha"})
        self.store.set_project_fabrication_profile("alpha", _profile())
        self.store.set_project_fabrication_profile("alpha", None)
        self.assertIsNone(self.store.load_project("alpha")["fabrication_profile"])


@unittest.skipUnless(_kicad_cli_available(), "kicad-cli is not installed on this machine")
@unittest.skipUnless(os.path.exists(EXAMPLE_PCB), "the example project is not present")
class FabricationReviewTests(unittest.TestCase):
    """Phase 5's proof surface, against the real board."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = os.path.join(self._tmp.name, "Copperplane_Blink_LEDs")
        shutil.copytree(EXAMPLE_PROJECT, self.project)
        self.pcb = os.path.join(self.project, "Copperplane_Blink_LEDs.kicad_pcb")
        self.addCleanup(self._tmp.cleanup)

    def test_a_looser_house_limit_cannot_hide_a_real_violation(self):
        """The defect this whole context exists for.

        A sidecar rule REPLACES the board's own constraint rather than adding to
        it. Measured on this board: a sidecar `annular_width` of 0.05mm against
        a board setup requiring 0.1mm took four genuine errors to ZERO. The
        shipped generic profile was looser than KiCad's defaults on two fields,
        so the app could silently switch off a check the user already had --
        exactly what SPEC-114 section 3 forbids."""
        reckless = _profile(min_annular_ring=0.05)
        result = fabrication_review.review(self.pcb, reckless)

        annular = [v for v in result["findings"] if v["type"] == "annular_width"]
        self.assertEqual(
            len(annular), 4,
            "the board's own 0.1mm annular rule must still fire; a looser house "
            "limit may never replace a stricter setting the user already has",
        )
        stricter = {e["field"] for e in result["not_checked"]["your_setting_is_stricter"]}
        self.assertIn("min_annular_ring", stricter, "and the app must say it did this")

    def test_a_stricter_house_limit_still_applies(self):
        """The control. Without this, the test above passes for a build that
        simply never writes any rule at all."""
        result = fabrication_review.review(self.pcb, _profile())
        self.assertGreater(result["after_count"], result["before_count"])
        self.assertGreater(result["rule_hits"]["min-annular-ring"], 0)

    def test_an_equal_limit_writes_no_rule(self):
        """Equal is not stricter. A duplicate rule buys nothing and is one more
        way to get the replacement semantics wrong."""
        rules = capability_profile.to_rules(
            _profile(min_drill=0.3), board_rules={"min_through_hole_diameter": 0.3}
        )
        self.assertFalse(any(r[0] == "min-drill" for r in rules))

    # TEST-014
    def test_014_generation_touches_only_the_sidecar(self):
        pro = os.path.join(self.project, "Copperplane_Blink_LEDs.kicad_pro")
        with open(pro, encoding="utf-8") as handle:
            before = handle.read()
        with open(self.pcb, encoding="utf-8") as handle:
            board_before = handle.read()

        fabrication_review.review(self.pcb, _profile())

        with open(pro, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), before, "the project file is never written")
        with open(self.pcb, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), board_before, "the board is never written")
        self.assertTrue(os.path.exists(kicad_dru.sidecar_path_for(self.pcb)))

    # TEST-016
    def test_016_before_and_after_reproduces_the_measured_headline(self):
        result = fabrication_review.review(self.pcb, _profile())
        self.assertEqual(result["verification_state"], kicad_dru.APPLIED)
        self.assertEqual(result["before_count"], 4,
                         "the 'before' side must be KiCad's own defaults")
        self.assertGreater(result["after_count"], result["before_count"])
        self.assertLess(result["after_count"], 100, "must not drown a first board")

        summary = fabrication_review.summarize(result)
        self.assertIn("4", summary)
        for forbidden in ("good to order", "ready to order", "safe to order"):
            self.assertNotIn(forbidden, summary.lower())

    def test_the_before_side_is_not_polluted_by_a_leftover_sidecar(self):
        """A stale generated sidecar would make 'before' into a second 'after'.

        Without this the proof surface compares the profile against itself and
        always shows no difference, which would read as a clean board."""
        fabrication_review.review(self.pcb, _profile())
        self.assertTrue(os.path.exists(kicad_dru.sidecar_path_for(self.pcb)))
        second = fabrication_review.review(self.pcb, _profile())
        self.assertEqual(second["before_count"], 4)

    # TEST-015
    def test_015_ignored_checks_are_reported_not_presented_as_clean(self):
        result = fabrication_review.review(self.pcb, _profile())
        self.assertGreater(
            len(result["not_checked"]["ignored_by_project"]), 0,
            "this board ships with checks ignored by default; the review must say so",
        )

    def test_a_rule_gated_off_by_the_project_is_named(self):
        import json
        pro = os.path.join(self.project, "Copperplane_Blink_LEDs.kicad_pro")
        with open(pro, encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("board", {}).setdefault("design_settings", {}) \
            .setdefault("rule_severities", {})["annular_width"] = "ignore"
        with open(pro, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

        result = fabrication_review.review(self.pcb, _profile())
        gated = [g["field"] for g in result["not_checked"]["profile_rules_gated_off"]]
        self.assertIn("min_annular_ring", gated,
                      "Limit 1: the app cannot re-enable it, so it has to say it was off")

    def _ignore_check(self, key):
        import json
        pro = os.path.join(self.project, "Copperplane_Blink_LEDs.kicad_pro")
        with open(pro, encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("board", {}).setdefault("design_settings", {}) \
            .setdefault("rule_severities", {})[key] = "ignore"
        with open(pro, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def test_gating_is_detected_when_the_check_key_differs_from_the_constraint(self):
        """The case the annular_width test cannot catch.

        A constraint class and the check it is gated under are often not the
        same name: `hole_size` reports under `drill_out_of_range`. Matching the
        constraint name against the severity table silently missed four of ten
        fields, and passed its test because that test happened to pick one of
        the six where the two names coincide."""
        self._ignore_check("drill_out_of_range")
        result = fabrication_review.review(self.pcb, _profile())
        gated = {g["field"]: g for g in result["not_checked"]["profile_rules_gated_off"]}
        self.assertIn("min_drill", gated)
        self.assertEqual(gated["min_drill"]["ignored_keys"], ["drill_out_of_range"])
        self.assertTrue(gated["min_drill"]["fully_gated"])

    def test_a_partly_gated_rule_is_not_reported_as_fully_off(self):
        """`silk_clearance` reports under two keys; ignoring one is not all."""
        self._ignore_check("silk_overlap")
        result = fabrication_review.review(self.pcb, _profile())
        gated = {g["field"]: g for g in result["not_checked"]["profile_rules_gated_off"]}
        self.assertIn("min_silk_clearance", gated)
        self.assertFalse(gated["min_silk_clearance"]["fully_gated"],
                         "silk_over_copper still reports, so the rule is not fully off")

    def test_every_enforceable_constraint_has_a_known_severity_key(self):
        """No field may fall back to guessing its own name as the key."""
        for field, (constraint, _, _) in capability_profile.ENFORCEABLE_FIELDS.items():
            self.assertIn(
                constraint, fabrication_review._SEVERITY_KEYS_BY_CONSTRAINT,
                f"{field} has no measured severity key mapping",
            )

    def test_a_discarded_sidecar_surfaces_rather_than_producing_a_review(self):
        original = kicad_dru.render_sidecar

        def sabotage(rules, include_canary=True):
            return original(rules, include_canary) + (
                '(rule "sabotage"\n'
                "  (constraint not_a_real_constraint (min 1mm))\n"
                "  (severity warning))\n"
            )

        kicad_dru.render_sidecar = sabotage
        self.addCleanup(setattr, kicad_dru, "render_sidecar", original)
        with self.assertRaises(kicad_dru.SidecarDiscarded):
            fabrication_review.review(self.pcb, _profile())

    def test_the_headline_findings_land_on_d1(self):
        result = fabrication_review.review(self.pcb, _profile())
        components = set()
        for violation in result["findings"]:
            for item in violation.get("items", []):
                if "D1" in item.get("description", ""):
                    components.add("D1")
        self.assertIn("D1", components,
                      "the same component SPEC-113's structural pack is built around")


if __name__ == "__main__":
    unittest.main()

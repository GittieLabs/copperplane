"""Tests for `.kicad_dru` sidecar generation and its mandatory verification run.

`SPEC-114` section 2.2, Limit 2: a malformed sidecar is discarded entirely and
silently -- no stderr, unchanged exit code, normal-looking report. A generated
file therefore may never be assumed to have taken effect. These tests are the
regression fence around that, and around Limit 1 (a rule cannot resurrect a
check the project set to `ignore`).

These run against a real `kicad-cli` on a real copy of the example project, and
skip cleanly when either is absent. Mocking the DRC subprocess would make the
Limit 1 and Limit 2 tests unfalsifiable, because the behaviour being pinned is
KiCad's own silence -- a mock would simply return whatever we told it to.

Several tests here assert that a *hazard still exists*. If a future KiCad starts
reporting malformed sidecars properly, they will fail. That is the intent: the
mitigation built on top of the hazard should be revisited the day it is fixed,
not left standing unexamined.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

import kicad_cli
import kicad_dru

EXAMPLE_PROJECT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "examples", "Copperplane_Blink_LEDs"
))
EXAMPLE_PCB = os.path.join(EXAMPLE_PROJECT, "Copperplane_Blink_LEDs.kicad_pcb")

# The measured baseline, SPEC-114 section 2.1: this board with no sidecar.
BASELINE_VIOLATIONS = 4
BASELINE_TYPE = "annular_width"


def _kicad_cli_available() -> bool:
    try:
        kicad_cli.find_kicad_cli()
        return True
    except Exception:
        return False


REASON_NO_CLI = "kicad-cli is not installed on this machine"
REASON_NO_EXAMPLE = "the example project is not present"


class FixturePathGuard(unittest.TestCase):
    """Never skips, on purpose.

    The first run of this module reported `OK (skipped=17)` because
    `EXAMPLE_PROJECT` was resolved one directory short of the repo root. Every
    test skipped, the suite went green, and nothing whatsoever had been checked
    -- a check that cannot fail, which `CLAUDE.md` names as the trap it is.
    `examples/` is committed to this repo, so its absence is always a path bug
    here and never a missing optional dependency. This test is the tripwire."""

    def test_the_example_project_path_actually_resolves(self):
        self.assertTrue(
            os.path.exists(EXAMPLE_PCB),
            f"the committed example board should always be found, got {EXAMPLE_PCB}",
        )


@unittest.skipUnless(_kicad_cli_available(), REASON_NO_CLI)
@unittest.skipUnless(os.path.exists(EXAMPLE_PCB), REASON_NO_EXAMPLE)
class DruSidecarTests(unittest.TestCase):
    """Every test works on its own throwaway copy of the project.

    The example board in the repo is never modified -- the same discipline the
    original measurements in SPEC-114 section 2.1 were taken under."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = os.path.join(self._tmp.name, "Copperplane_Blink_LEDs")
        shutil.copytree(EXAMPLE_PROJECT, self.project)
        self.pcb = os.path.join(self.project, "Copperplane_Blink_LEDs.kicad_pcb")
        self.dru = kicad_dru.sidecar_path_for(self.pcb)
        self.addCleanup(self._tmp.cleanup)

    def _write_raw(self, text):
        with open(self.dru, "w", encoding="utf-8") as handle:
            handle.write(text)

    def _drc(self):
        return kicad_cli.run_drc(self.pcb)

    # TEST-001
    def test_001_baseline_board_reproduces_the_measured_four_violations(self):
        report = self._drc()
        violations = report["violations"]
        self.assertEqual(len(violations), BASELINE_VIOLATIONS)
        self.assertEqual({v["type"] for v in violations}, {BASELINE_TYPE})

    # TEST-002
    def test_002_a_valid_sidecar_rule_fires_and_names_itself(self):
        self._write_raw(
            '(version 1)\n'
            '(rule "min-track-width")\n'.replace(
                '(rule "min-track-width")',
                '(rule "min-track-width"\n'
                "  (constraint track_width (min 0.5mm))\n"
                "  (severity warning))",
            )
        )
        hits = kicad_dru.rule_hits(self._drc())
        self.assertGreater(hits["min-track-width"], 0,
                           "a valid track_width rule should fire on this board")

    # TEST-003
    def test_003_a_sidecar_under_the_wrong_filename_changes_nothing(self):
        wrong = os.path.join(self.project, "not_the_project_name.kicad_dru")
        with open(wrong, "w", encoding="utf-8") as handle:
            handle.write(
                '(version 1)\n'
                '(rule "min-track-width"\n'
                "  (constraint track_width (min 0.5mm))\n"
                "  (severity warning))\n"
            )
        report = self._drc()
        self.assertEqual(len(report["violations"]), BASELINE_VIOLATIONS,
                         "only <project>.kicad_dru is honoured")
        self.assertEqual(kicad_dru.rule_hits(report), {})

    # TEST-004
    def test_004_one_misspelled_constraint_discards_every_other_rule(self):
        good = (
            '(rule "min-track-width"\n'
            "  (constraint track_width (min 0.5mm))\n"
            "  (severity warning))\n"
        )
        self._write_raw("(version 1)\n" + good)
        alone = kicad_dru.rule_hits(self._drc())["min-track-width"]
        self.assertGreater(alone, 0, "control: the good rule fires on its own")

        self._write_raw(
            "(version 1)\n" + good +
            '(rule "bogus"\n'
            "  (constraint trackwidth_typo (min 0.5mm))\n"
            "  (severity warning))\n"
        )
        report = self._drc()
        self.assertEqual(kicad_dru.rule_hits(report)["min-track-width"], 0,
                         "Limit 2: the good rule is discarded along with the bad one")
        self.assertEqual(len(report["violations"]), BASELINE_VIOLATIONS)

    # TEST-005
    def test_005_the_silent_discard_exits_zero_with_nothing_on_stderr(self):
        self._write_raw(
            "(version 1)\n"
            '(rule "bogus"\n'
            "  (constraint trackwidth_typo (min 0.5mm))\n"
            "  (severity warning))\n"
        )
        # Deliberately bypasses kicad_cli.run_drc: the exit code and stderr are
        # precisely what this test exists to observe, and the wrapper hides both.
        with tempfile.TemporaryDirectory() as out:
            report_path = os.path.join(out, "report.json")
            result = subprocess.run(
                [kicad_cli.find_kicad_cli(), "pcb", "drc", "--format", "json",
                 "--severity-all", "-o", report_path, self.pcb],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(result.returncode, 0, "the discard does not change the exit code")
            self.assertEqual(result.stderr.strip(), "", "the discard says nothing on stderr")
            with open(report_path, encoding="utf-8") as handle:
                report = json.load(handle)
        self.assertEqual(len(report["violations"]), BASELINE_VIOLATIONS,
                         "and the report looks perfectly normal")

    # TEST-006
    def test_006_unclosed_paren_and_bad_unit_discard_identically(self):
        for label, bad in (
            ("unclosed paren",
             '(rule "bad"\n  (constraint track_width (min 0.5mm)\n  (severity warning))\n'),
            ("unparseable unit",
             '(rule "bad"\n  (constraint track_width (min 0.2furlongs))\n  (severity warning))\n'),
        ):
            with self.subTest(malformation=label):
                self._write_raw(
                    "(version 1)\n"
                    '(rule "min-track-width"\n'
                    "  (constraint track_width (min 0.5mm))\n"
                    "  (severity warning))\n" + bad
                )
                report = self._drc()
                self.assertEqual(kicad_dru.rule_hits(report)["min-track-width"], 0)
                self.assertEqual(len(report["violations"]), BASELINE_VIOLATIONS)

    def _set_ignored(self, check_name):
        pro_path = os.path.join(self.project, "Copperplane_Blink_LEDs.kicad_pro")
        with open(pro_path, encoding="utf-8") as handle:
            pro = json.load(handle)
        pro.setdefault("board", {}).setdefault("design_settings", {}) \
           .setdefault("rule_severities", {})[check_name] = "ignore"
        with open(pro_path, "w", encoding="utf-8") as handle:
            json.dump(pro, handle, indent=2)

    # TEST-007
    def test_007_a_rule_cannot_resurrect_a_check_the_project_ignores(self):
        self._write_raw(
            "(version 1)\n"
            '(rule "min-track-width"\n'
            "  (constraint track_width (min 0.5mm))\n"
            "  (severity warning))\n"
        )
        self.assertGreater(kicad_dru.rule_hits(self._drc())["min-track-width"], 0,
                           "control: fires before the check is ignored")
        self._set_ignored("track_width")
        self.assertEqual(kicad_dru.rule_hits(self._drc())["min-track-width"], 0,
                         "Limit 1: the project severity table gates the sidecar")

    # TEST-008
    def test_008_an_explicit_severity_does_not_override_the_ignore_gate(self):
        self._set_ignored("track_width")
        self._write_raw(
            "(version 1)\n"
            '(rule "min-track-width"\n'
            "  (constraint track_width (min 0.5mm))\n"
            "  (severity error))\n"
        )
        self.assertEqual(kicad_dru.rule_hits(self._drc())["min-track-width"], 0,
                         "an explicit severity inside the rule does not lift the gate")

    # TEST-009
    def test_009_generated_rules_are_warnings_while_kicad_findings_stay_errors(self):
        result = kicad_dru.write_and_verify(
            self.pcb, [("min-track-width", "track_width", "min 0.5mm", "warning")]
        )
        severities = {}
        for violation in result["report"]["violations"]:
            severities.setdefault(violation["severity"], set()).add(violation["type"])
        self.assertIn("warning", severities)
        self.assertIn("track_width", severities["warning"])
        self.assertIn("error", severities)
        self.assertIn(BASELINE_TYPE, severities["error"],
                      "KiCad's own annular_width findings stay errors")

    # TEST-010
    def test_010_a_write_whose_rules_did_not_fire_raises_rather_than_passing(self):
        original = kicad_dru.render_sidecar

        def sabotage(rules, include_canary=True):
            # A typo introduced *after* validation, standing in for any future
            # bug in the writer. The point is that verification catches it even
            # when generation believes it succeeded.
            return original(rules, include_canary) + (
                '(rule "sabotage"\n'
                "  (constraint not_a_real_constraint (min 1mm))\n"
                "  (severity warning))\n"
            )

        kicad_dru.render_sidecar = sabotage
        self.addCleanup(setattr, kicad_dru, "render_sidecar", original)
        with self.assertRaises(kicad_dru.SidecarDiscarded):
            kicad_dru.write_and_verify(
                self.pcb, [("min-track-width", "track_width", "min 0.5mm", "warning")]
            )

    # TEST-016
    def test_016_a_realistic_profile_reproduces_the_measured_headline(self):
        """SPEC-114 section 2.4: a plausible 2-layer profile yields 27 findings.

        Per CTX-114.1's own Prediction 2, the *shape* is what is asserted here
        rather than the total: the three headline findings all landing on D1 is
        the claim the pitch rests on, and it survives the profile numbers being
        replaced with a real board house's. The total is checked loosely, only
        to catch a collapse to the baseline or an explosion into the hundreds."""
        profile = [
            ("min-track-width", "track_width", "min 0.127mm", "warning"),
            ("min-clearance", "clearance", "min 0.127mm", "warning"),
            ("min-annular-ring", "annular_width", "min 0.13mm", "warning"),
            ("min-drill", "hole_size", "min 0.3mm", "warning"),
            ("min-hole-to-hole", "hole_to_hole", "min 0.5mm", "warning"),
            ("min-silk-clearance", "silk_clearance", "min 0.15mm", "warning"),
            ("min-text-height", "text_height", "min 1.0mm", "warning"),
            ("min-text-thickness", "text_thickness", "min 0.15mm", "warning"),
            ("min-edge-clearance", "edge_clearance", "min 0.2mm", "warning"),
        ]
        result = kicad_dru.write_and_verify(self.pcb, profile)
        self.assertEqual(result["state"], kicad_dru.APPLIED)

        violations = result["report"]["violations"]
        self.assertGreater(len(violations), BASELINE_VIOLATIONS,
                           "the profile must find more than KiCad's defaults do")
        self.assertLess(len(violations), 100, "and must not drown a first board")

        ours = [v for v in violations if "rule '" in v["description"]]
        components = set()
        for violation in ours:
            for item in violation.get("items", []):
                description = item.get("description", "")
                if "D1" in description:
                    components.add("D1")
        self.assertIn("D1", components,
                      "the headline findings land on D1, the same part SPEC-113 is built around")


@unittest.skipUnless(_kicad_cli_available(), REASON_NO_CLI)
@unittest.skipUnless(os.path.exists(EXAMPLE_PCB), REASON_NO_EXAMPLE)
class SidecarVerificationTests(unittest.TestCase):
    """The canary mechanism itself."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = os.path.join(self._tmp.name, "Copperplane_Blink_LEDs")
        shutil.copytree(EXAMPLE_PROJECT, self.project)
        self.pcb = os.path.join(self.project, "Copperplane_Blink_LEDs.kicad_pcb")
        self.dru = kicad_dru.sidecar_path_for(self.pcb)
        self.addCleanup(self._tmp.cleanup)

    def test_a_rule_that_finds_nothing_still_verifies_as_applied(self):
        """The distinction the whole design turns on.

        `courtyard_clearance` at 0.001mm finds nothing on this board because no
        two parts are that close. Without the canary that is indistinguishable
        from the file having been discarded, and the feature would either cry
        wolf on every compliant board or trust a file it never checked."""
        result = kicad_dru.write_and_verify(
            self.pcb,
            [("min-courtyard-clearance", "courtyard_clearance", "min 0.001mm", "warning")],
        )
        self.assertEqual(result["state"], kicad_dru.APPLIED)
        self.assertEqual(result["hits"]["min-courtyard-clearance"], 0,
                         "found nothing, which is a real result and not a failure")

    def test_the_canary_is_stripped_from_what_the_user_sees(self):
        result = kicad_dru.write_and_verify(
            self.pcb, [("min-track-width", "track_width", "min 0.5mm", "warning")]
        )
        self.assertNotIn(kicad_dru.CANARY_RULE_NAME, result["hits"])
        for violation in result["report"]["violations"]:
            self.assertNotIn(kicad_dru.CANARY_RULE_NAME, violation["description"])

    def test_an_unconfirmed_constraint_class_is_refused_before_it_is_written(self):
        with self.assertRaises(kicad_dru.SidecarError):
            kicad_dru.render_sidecar([("v", "via_diameter", "min 0.4mm", "warning")])

    def test_a_user_authored_sidecar_is_never_overwritten(self):
        with open(self.dru, "w", encoding="utf-8") as handle:
            handle.write('(version 1)\n# a rule the user wrote themselves\n')
        with self.assertRaises(kicad_dru.SidecarWouldOverwrite):
            kicad_dru.write_and_verify(
                self.pcb, [("min-track-width", "track_width", "min 0.5mm", "warning")]
            )
        with open(self.dru, encoding="utf-8") as handle:
            self.assertIn("a rule the user wrote themselves", handle.read())

    def test_our_own_generated_sidecar_is_replaceable(self):
        kicad_dru.write_and_verify(
            self.pcb, [("min-track-width", "track_width", "min 0.5mm", "warning")]
        )
        result = kicad_dru.write_and_verify(
            self.pcb, [("min-annular-ring", "annular_width", "min 0.13mm", "warning")]
        )
        self.assertEqual(result["state"], kicad_dru.APPLIED)

    def test_comments_in_the_generated_header_do_not_break_parsing(self):
        """Assumed-safe formatting is exactly what Limit 2 punishes."""
        text = kicad_dru.render_sidecar(
            [("min-track-width", "track_width", "min 0.5mm", "warning")]
        )
        self.assertIn("#", text)
        with open(self.dru, "w", encoding="utf-8") as handle:
            handle.write(text)
        hits = kicad_dru.rule_hits(kicad_cli.run_drc(self.pcb))
        self.assertGreater(hits[kicad_dru.CANARY_RULE_NAME], 0)
        self.assertGreater(hits["min-track-width"], 0)


if __name__ == "__main__":
    unittest.main()

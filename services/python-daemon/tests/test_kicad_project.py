"""SPEC-325 §2.1: resolving a KiCad project file to the files it owns.

The app's existing path derives a schematic from whatever board KiCad
currently has open, over IPC. That needs KiCad running, its API enabled,
and the right document focused -- three preconditions for a fact sitting
in a file. These tests use real files on disk and never touch KiCad.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kicad_project as kp  # noqa: E402


class TestResolveProject(unittest.TestCase):
    def _project(self, tmp, name="Widget", sch=True, pcb=True, sheets=None):
        pro = os.path.join(tmp, f"{name}.kicad_pro")
        body = {"meta": {"version": 3}}
        if sheets is not None:
            body["sheets"] = sheets
        with open(pro, "w", encoding="utf-8") as h:
            json.dump(body, h)
        if sch:
            open(os.path.join(tmp, f"{name}.kicad_sch"), "w").close()
        if pcb:
            open(os.path.join(tmp, f"{name}.kicad_pcb"), "w").close()
        return pro

    def test_001_resolves_the_siblings_by_kicads_own_naming_convention(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = kp.resolve_project(self._project(tmp))
        self.assertEqual("Widget", out["project_name"])
        self.assertTrue(out["schematic_path"].endswith("Widget.kicad_sch"))
        self.assertTrue(out["pcb_path"].endswith("Widget.kicad_pcb"))

    def test_002_a_project_with_no_board_yet_is_an_ordinary_state(self):
        """Refusing to load a project because it has no PCB would be worse
        than saying it has none -- a schematic-only project is normal."""
        with tempfile.TemporaryDirectory() as tmp:
            out = kp.resolve_project(self._project(tmp, pcb=False))
        self.assertIsNotNone(out["schematic_path"])
        self.assertIsNone(out["pcb_path"])

    def test_003_a_non_project_path_is_refused_by_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = os.path.join(tmp, "Widget.kicad_pcb")
            open(board, "w").close()
            with self.assertRaises(kp.KicadProjectError):
                kp.resolve_project(board)

    def test_004_a_missing_project_file_says_so(self):
        with self.assertRaises(kp.KicadProjectError):
            kp.resolve_project("/nonexistent/Widget.kicad_pro")

    def test_005_malformed_json_is_a_clean_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            pro = os.path.join(tmp, "Widget.kicad_pro")
            with open(pro, "w", encoding="utf-8") as h:
                h.write("{not json")
            with self.assertRaises(kp.KicadProjectError):
                kp.resolve_project(pro)

    def test_006_sheet_count_is_reported_so_a_caller_can_be_suspicious(self):
        """SPEC-325 §3: whether `kicad-cli sch export bom` walks a
        hierarchy from the root sheet is UNVERIFIED -- no multi-sheet
        project was available to test against. Reporting the count lets a
        caller treat a multi-sheet project's component list with
        appropriate suspicion rather than trusting it silently."""
        with tempfile.TemporaryDirectory() as tmp:
            out = kp.resolve_project(self._project(tmp, sheets=[["uuid-a", ""], ["uuid-b", "Power"]]))
        self.assertEqual(2, out["sheet_count"])

    def test_007_a_project_without_a_sheets_key_reports_unknown_not_zero(self):
        """None and 0 are different claims: 'this file did not say' versus
        'this project has no sheets'."""
        with tempfile.TemporaryDirectory() as tmp:
            out = kp.resolve_project(self._project(tmp))
        self.assertIsNone(out["sheet_count"])


class TestAgainstARealProject(unittest.TestCase):
    """The real thing, per CLAUDE.md's own norm. Skips cleanly when the
    maintainer's own KiCad projects are not present."""

    REAL = ("/Users/keithelliott/repos/PCBs/Hello_World_Blinky/"
            "Hello_World_Blinky/Hello_World_Blinky.kicad_pro")

    def setUp(self):
        if not os.path.isfile(self.REAL):
            self.skipTest("real KiCad project not present on this machine")

    def test_008_resolves_a_real_project_with_kicad_closed(self):
        out = kp.resolve_project(self.REAL)
        self.assertEqual("Hello_World_Blinky", out["project_name"])
        self.assertTrue(os.path.isfile(out["schematic_path"]))
        self.assertTrue(os.path.isfile(out["pcb_path"]))


if __name__ == "__main__":
    unittest.main()

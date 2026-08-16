import os
import shutil
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import kicad_cli
import kicad_pcb_import
from kicad_pcb_import import (
    BoardOutlineMissingError,
    _parse_dxf_edge_cuts_bbox,
    _parse_excellon_npth_holes,
    extract_board_outline,
    extract_mounting_holes,
)

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
_BOARD_WITH_OUTLINE = os.path.join(_FIXTURES_DIR, 'board_with_outline.kicad_pcb')
_EMPTY_BOARD = os.path.join(_FIXTURES_DIR, 'empty_board.kicad_pcb')


def _find_real_kicad_cli():
    """Same real-kicad-cli-location convention test_kicad_cli.py's own
    _find_real_kicad_cli already uses -- not the module under test's own
    find_kicad_cli."""
    on_path = shutil.which("kicad-cli")
    if on_path:
        return on_path
    macos_path = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
    if os.path.exists(macos_path):
        return macos_path
    return None


class TestParseDxfEdgeCutsBbox(unittest.TestCase):
    """Pure parsing logic -- no subprocess, no real kicad-cli needed.
    Expected values account for the real Y-axis sign flip between
    kicad-cli's DXF export (standard drafting convention, Y up) and
    KiCad's own internal board coordinates (Y down) that
    _parse_dxf_edge_cuts_bbox corrects for -- see that function's own
    comment. These fixture DXF snippets are written in DXF's raw,
    unflipped Y-up numbers; the assertions are the already-flipped,
    kicad_bridge-convention result."""

    def test_001_a_line_entity_bbox_is_the_pair_of_endpoints(self):
        dxf = """0
SECTION
2
ENTITIES
0
LINE
10
0.0
20
0.0
11
50.0
21
30.0
0
ENDSEC
"""
        outline = _parse_dxf_edge_cuts_bbox(dxf)
        self.assertEqual(outline, {"x_mm": 0.0, "y_mm": -30.0, "width_mm": 50.0, "height_mm": 30.0})

    def test_002_a_circle_entity_bbox_is_center_plus_minus_radius(self):
        dxf = """0
SECTION
2
ENTITIES
0
CIRCLE
10
10.0
20
10.0
40
5.0
0
ENDSEC
"""
        outline = _parse_dxf_edge_cuts_bbox(dxf)
        self.assertEqual(outline, {"x_mm": 5.0, "y_mm": -15.0, "width_mm": 10.0, "height_mm": 10.0})

    def test_003_an_lwpolyline_bbox_covers_all_its_vertices(self):
        dxf = """0
SECTION
2
ENTITIES
0
LWPOLYLINE
10
0.0
20
0.0
10
20.0
20
0.0
10
20.0
20
10.0
10
0.0
20
10.0
0
ENDSEC
"""
        outline = _parse_dxf_edge_cuts_bbox(dxf)
        self.assertEqual(outline, {"x_mm": 0.0, "y_mm": -10.0, "width_mm": 20.0, "height_mm": 10.0})

    def test_004_entities_outside_the_entities_section_are_ignored(self):
        dxf = """0
SECTION
2
HEADER
0
LINE
10
999.0
20
999.0
11
999.0
21
999.0
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
10
0.0
20
0.0
11
5.0
21
5.0
0
ENDSEC
"""
        outline = _parse_dxf_edge_cuts_bbox(dxf)
        self.assertEqual(outline, {"x_mm": 0.0, "y_mm": -5.0, "width_mm": 5.0, "height_mm": 5.0})

    def test_005_no_edge_cuts_geometry_at_all_raises_a_clean_error(self):
        dxf = """0
SECTION
2
ENTITIES
0
ENDSEC
"""
        with self.assertRaises(BoardOutlineMissingError) as ctx:
            _parse_dxf_edge_cuts_bbox(dxf)
        self.assertIn("no Edge.Cuts geometry", str(ctx.exception))


class TestParseExcellonNpthHoles(unittest.TestCase):
    """Pure parsing logic -- no subprocess needed. Same real Y-axis sign
    flip as the DXF parser (see TestParseDxfEdgeCutsBbox's own docstring)
    applies here too -- fixture coordinates are raw Excellon Y-up
    numbers, assertions are the already-flipped result."""

    def test_001_only_npth_tooled_holes_are_returned_pth_is_excluded(self):
        drill = """M48
; #@! TA.AperFunction,Plated,PTH
T1C0.8
; #@! TA.AperFunction,NonPlated,NPTH
T2C3.2
%
T1
X1.0Y1.0
T2
X5.0Y5.0
"""
        holes = _parse_excellon_npth_holes(drill)
        self.assertEqual(holes, [
            {"x_mm": 5.0, "y_mm": -5.0, "diameter_mm": 3.2, "recognized": True},
        ])

    def test_002_no_npth_tools_at_all_returns_an_empty_list(self):
        drill = """M48
; #@! TA.AperFunction,Plated,PTH
T1C0.8
%
T1
X1.0Y1.0
"""
        self.assertEqual(_parse_excellon_npth_holes(drill), [])

    def test_003_multiple_coordinates_under_the_same_npth_tool_all_come_back(self):
        drill = """M48
; #@! TA.AperFunction,NonPlated,NPTH
T1C3.2
%
T1
X0.0Y0.0
X10.0Y10.0
"""
        holes = _parse_excellon_npth_holes(drill)
        self.assertEqual(len(holes), 2)
        self.assertEqual(holes[0]["x_mm"], 0.0)
        self.assertEqual(holes[1]["x_mm"], 10.0)


class TestExtractFunctionsErrorHandling(unittest.TestCase):
    """Mocked kicad-cli subprocess boundary -- no real binary needed to
    verify the missing-export error path (mirrors
    test_kicad_cli.py's own TestRunReportErrorHandling)."""

    @patch('kicad_pcb_import.tempfile.TemporaryDirectory')
    @patch('kicad_pcb_import.subprocess.run')
    @patch('kicad_cli.find_kicad_cli', return_value='/fake/kicad-cli')
    def test_001_dxf_export_that_never_produces_a_file_raises_a_clean_error(
        self, mock_find, mock_run, mock_tmpdir,
    ):
        mock_tmpdir.return_value.__enter__.return_value = '/tmp/does-not-exist-dxf'
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "some real kicad-cli export failure"
        with self.assertRaises(kicad_cli.KicadCliError) as ctx:
            extract_board_outline(_BOARD_WITH_OUTLINE)
        self.assertIn("some real kicad-cli export failure", str(ctx.exception))

    @patch('kicad_pcb_import.tempfile.TemporaryDirectory')
    @patch('kicad_pcb_import.subprocess.run')
    @patch('kicad_cli.find_kicad_cli', return_value='/fake/kicad-cli')
    def test_002_drill_export_that_never_produces_a_file_raises_a_clean_error(
        self, mock_find, mock_run, mock_tmpdir,
    ):
        mock_tmpdir.return_value.__enter__.return_value = '/tmp/does-not-exist-drl'
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "some real kicad-cli drill failure"
        with self.assertRaises(kicad_cli.KicadCliError) as ctx:
            extract_mounting_holes(_BOARD_WITH_OUTLINE)
        self.assertIn("some real kicad-cli drill failure", str(ctx.exception))


class TestRealExtraction(unittest.TestCase):
    """Real, non-mocked kicad-cli subprocess calls against a real,
    committed fixture -- CLAUDE.md's 'verify for real' norm. Skips
    itself cleanly when kicad-cli isn't found on this machine, the same
    convention test_kicad_cli.py's own TestRealRunDrcAndErc uses."""

    def setUp(self):
        if not _find_real_kicad_cli():
            self.skipTest("kicad-cli not found on this machine.")

    def test_001_real_board_outline_matches_the_real_fixtures_known_rectangle(self):
        outline = extract_board_outline(_BOARD_WITH_OUTLINE)
        self.assertEqual(outline, {"x_mm": 0.0, "y_mm": 0.0, "width_mm": 50.0, "height_mm": 30.0})

    def test_002_real_mounting_holes_match_the_real_fixtures_two_npth_pads(self):
        holes = extract_mounting_holes(_BOARD_WITH_OUTLINE)

        self.assertEqual(len(holes), 2)
        for hole in holes:
            self.assertTrue(hole["recognized"])
            self.assertAlmostEqual(hole["diameter_mm"], 3.2)
        coords = sorted((h["x_mm"], h["y_mm"]) for h in holes)
        self.assertEqual(coords, [(5.0, 5.0), (45.0, 25.0)])

    def test_003_a_real_board_with_no_edge_cuts_raises_a_clean_error(self):
        with self.assertRaises(BoardOutlineMissingError):
            extract_board_outline(_EMPTY_BOARD)


if __name__ == '__main__':
    unittest.main()

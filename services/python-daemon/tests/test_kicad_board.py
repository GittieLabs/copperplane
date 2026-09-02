"""SPEC-326 §2.7: reading a `.kicad_pcb` directly, because the board is the
source of truth for anything physical."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import kicad_board
from kicad_board import BoardReadError, read_board_footprints

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
_MATCH = os.path.join(_FIXTURES_DIR, 'parity_match.kicad_pcb')
_EMPTY = os.path.join(_FIXTURES_DIR, 'empty_board.kicad_pcb')


class TestReadBoardFootprints(unittest.TestCase):
    def test_001_reads_a_real_footprint_with_its_library_id_and_reference(self):
        found = read_board_footprints(_MATCH)

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["reference"], "R1")
        self.assertEqual(found[0]["footprint"], "Resistor_SMD:R_0805_2012Metric")
        self.assertEqual(found[0]["value"], "10k")

    def test_002_a_board_with_no_footprints_is_an_empty_list_not_an_error(self):
        """An empty board is an ordinary state -- a project drawn but not laid
        out yet. One of the maintainer's own four projects is in exactly that
        state, so this is not a hypothetical."""
        self.assertEqual([], read_board_footprints(_EMPTY))

    def test_003_a_missing_file_raises_a_clean_error(self):
        with self.assertRaises(BoardReadError):
            read_board_footprints("/nope/does_not_exist.kicad_pcb")

    def test_004_a_file_that_is_not_a_board_raises_rather_than_reporting_empty(self):
        with tempfile.NamedTemporaryFile("w", suffix=".kicad_pcb", delete=False) as f:
            f.write('(kicad_sch (version 20231120))')
            path = f.name
        try:
            with self.assertRaises(BoardReadError):
                read_board_footprints(path)
        finally:
            os.unlink(path)

    def test_005_an_exclude_from_pos_files_footprint_is_still_read(self):
        """The reason this module exists instead of `kicad-cli pcb export pos`.
        Position files honour `exclude_from_pos_files`, which is routinely set
        on mounting holes, fiducials and test points -- exactly the board-only
        mechanical parts that decide whether a board fits in a box. Confirmed
        by running the real CLI against this exact content: the CSV comes back
        with a header and no rows."""
        with open(_MATCH, encoding="utf-8") as f:
            content = f.read().replace("(attr smd)", "(attr smd exclude_from_pos_files)")
        with tempfile.NamedTemporaryFile("w", suffix=".kicad_pcb", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            found = read_board_footprints(path)
        finally:
            os.unlink(path)

        self.assertEqual([f["reference"] for f in found], ["R1"])

    def test_006_the_pre_kicad7_reference_spelling_is_read(self):
        """Boards written before KiCad 7 carry `(fp_text reference "SW1" ...)`
        rather than `(property "Reference" ...)`. A real 2021 board on this
        machine (version 20211014) has 31 such footprints, every one of which
        reads as reference `None` if only the modern spelling is handled --
        a silent wrong answer, not a crash, so it would have shipped."""
        board = (
            '(kicad_pcb (version 20211014)\n'
            '  (footprint "Lib:SW" locked (layer "F.Cu")\n'
            '    (at 114.3 76.2)\n'
            '    (fp_text reference "SW1" (at 0 0) (layer "F.SilkS"))\n'
            '    (fp_text value "MX" (at 0 2) (layer "F.Fab"))))\n'
        )
        with tempfile.NamedTemporaryFile("w", suffix=".kicad_pcb", delete=False) as f:
            f.write(board)
            path = f.name
        try:
            found = read_board_footprints(path)
        finally:
            os.unlink(path)

        self.assertEqual(found[0]["reference"], "SW1")
        self.assertEqual(found[0]["value"], "MX")

    def test_007_a_parenthesis_inside_a_quoted_value_does_not_mis_nest(self):
        """Real footprint values contain parentheses -- "Battery_Cell (CR2032)"
        is one. A paren count over the raw text mis-nests on those, which is
        why this reads quoted strings as single tokens."""
        board = (
            '(kicad_pcb (version 20240108)\n'
            '  (footprint "Battery:Holder" (layer "F.Cu")\n'
            '    (property "Reference" "BT1" (at 0 0))\n'
            '    (property "Value" "Battery_Cell (CR2032)" (at 0 2)))\n'
            '  (footprint "Device:R" (layer "F.Cu")\n'
            '    (property "Reference" "R1" (at 0 0))))\n'
        )
        with tempfile.NamedTemporaryFile("w", suffix=".kicad_pcb", delete=False) as f:
            f.write(board)
            path = f.name
        try:
            found = read_board_footprints(path)
        finally:
            os.unlink(path)

        self.assertEqual([f["reference"] for f in found], ["BT1", "R1"])
        self.assertEqual(found[0]["value"], "Battery_Cell (CR2032)")

    def test_008_unbalanced_parentheses_raise_rather_than_returning_partial(self):
        with tempfile.NamedTemporaryFile("w", suffix=".kicad_pcb", delete=False) as f:
            f.write('(kicad_pcb (version 1) (footprint "A:B"')
            path = f.name
        try:
            with self.assertRaises(BoardReadError):
                read_board_footprints(path)
        finally:
            os.unlink(path)


class TestRealBoards(unittest.TestCase):
    """Against the maintainer's own real projects, when they are present.
    Skips cleanly elsewhere -- these live outside the repo."""

    _REAL = "/Users/keithelliott/repos/PCBs/Hello_World_Blinky/Hello_World_Blinky/Hello_World_Blinky.kicad_pcb"

    def setUp(self):
        if not os.path.exists(self._REAL):
            self.skipTest("the maintainer's real board is not on this machine.")

    def test_001_reads_every_footprint_on_a_real_board(self):
        found = read_board_footprints(self._REAL)

        refs = {f["reference"] for f in found}
        self.assertEqual(len(found), 14)
        # The four mounting holes are board-only by design -- they carry no
        # schematic symbol, and are exactly what a schematic-sourced list misses.
        self.assertTrue({"H1", "H2", "H3", "H4"} <= refs)
        self.assertIn("BT1", refs)

    def test_002_the_board_disagrees_with_the_schematic_about_bt1(self):
        """The live defect SPEC-326 §2.7 was written about."""
        found = read_board_footprints(self._REAL)
        bt1 = next(f for f in found if f["reference"] == "BT1")

        self.assertIn("VS1N_Vertical", bt1["footprint"])


if __name__ == "__main__":
    unittest.main()

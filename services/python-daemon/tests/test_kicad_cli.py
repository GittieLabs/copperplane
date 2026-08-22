import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import kicad_cli
import library_store
from kicad_cli import (
    KicadCliError, KicadCliUnavailableError, export_board_glb, export_footprint_svg,
    export_symbol_svg, find_kicad_cli, run_drc, run_erc,
)

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
_EMPTY_BOARD = os.path.join(_FIXTURES_DIR, 'empty_board.kicad_pcb')
_EMPTY_SCHEMATIC = os.path.join(_FIXTURES_DIR, 'empty_schematic.kicad_sch')


def _find_real_kicad_cli():
    """Same shutil.which-first, real-known-path-fallback convention
    test_library_store.py's own _find_kicad_cli already uses for the
    real, live kicad-cli verification tests -- not this module's own
    find_kicad_cli (which is exactly what's under test)."""
    on_path = shutil.which("kicad-cli")
    if on_path:
        return on_path
    macos_path = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
    if os.path.exists(macos_path):
        return macos_path
    return None


class TestFindKicadCli(unittest.TestCase):

    def setUp(self):
        kicad_cli._path_override = None

    def tearDown(self):
        kicad_cli._path_override = None

    @patch('kicad_cli.glob.glob', return_value=[])
    @patch('kicad_cli.shutil.which', return_value=None)
    def test_001_no_executable_found_raises_clean_error(self, mock_which, mock_glob):
        with self.assertRaises(KicadCliUnavailableError) as ctx:
            find_kicad_cli()
        self.assertIn("Could not find the kicad-cli executable", str(ctx.exception))

    @patch('kicad_cli.shutil.which', return_value='/usr/local/bin/kicad-cli')
    def test_002_finds_it_on_path(self, mock_which):
        self.assertEqual(find_kicad_cli(), '/usr/local/bin/kicad-cli')

    def test_003_a_configured_override_is_honored_when_it_is_a_real_file(self):
        with tempfile.NamedTemporaryFile() as fake_cli:
            kicad_cli.configure(path_override=fake_cli.name)
            self.assertEqual(find_kicad_cli(), fake_cli.name)

    def test_004_a_configured_override_that_does_not_exist_raises_clean_error(self):
        kicad_cli.configure(path_override='/nonexistent/kicad-cli')
        with self.assertRaises(KicadCliUnavailableError) as ctx:
            find_kicad_cli()
        self.assertIn("does not exist", str(ctx.exception))


class TestRunReportErrorHandling(unittest.TestCase):
    """Mocked -- no real kicad-cli needed to verify the error-mapping
    logic itself."""

    @patch('kicad_cli.find_kicad_cli', return_value='/fake/kicad-cli')
    def test_001_a_missing_input_file_raises_a_clean_error(self, mock_find):
        with self.assertRaises(KicadCliError) as ctx:
            run_drc('/nonexistent/board.kicad_pcb')
        self.assertIn("does not exist", str(ctx.exception))

    @patch('kicad_cli.subprocess.run')
    @patch('kicad_cli.find_kicad_cli', return_value='/fake/kicad-cli')
    def test_002_a_run_that_never_produces_a_report_raises_a_clean_error(self, mock_find, mock_run):
        """kicad-cli's own exit code alone never means "violations
        exist" (confirmed live: exit 0 with real violations present) --
        the only real failure signal this module trusts is the report
        file itself never being written."""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "some real kicad-cli failure text"
        with self.assertRaises(KicadCliError) as ctx:
            run_drc(_EMPTY_BOARD)
        self.assertIn("some real kicad-cli failure text", str(ctx.exception))


class TestRealRunDrcAndErc(unittest.TestCase):
    """Real, non-mocked kicad-cli calls against real, committed fixture
    files -- CLAUDE.md's 'verify for real' norm. Skips itself cleanly
    when kicad-cli isn't found on this machine, same convention every
    other real-tool test in this repo uses."""

    def setUp(self):
        if not _find_real_kicad_cli():
            self.skipTest("kicad-cli not found on this machine.")

    def test_001_run_drc_against_a_real_malformed_board_finds_the_real_violation(self):
        """empty_board.kicad_pcb has no Edge.Cuts outline at all --
        deterministically produces kicad-cli's own real
        "invalid_outline" error, confirmed by running this exact
        fixture through the real CLI during SPEC-309's own research,
        not assumed."""
        report = run_drc(_EMPTY_BOARD)

        self.assertEqual(len(report["violations"]), 1)
        violation = report["violations"][0]
        self.assertEqual(violation["type"], "invalid_outline")
        self.assertEqual(violation["severity"], "error")

    def test_002_run_erc_against_a_real_clean_schematic_finds_no_violations(self):
        """A genuinely empty schematic is ERC-clean by KiCad's own real
        rules -- confirmed the same way. Proves the real subprocess +
        JSON-parsing round trip for the "no violations" path; a
        real *violating* schematic fixture is deliberately not
        hand-crafted here (see CTX-309.1 Plan Drift) -- the "has
        violations" path is exercised for real via DRC above instead."""
        report = run_erc(_EMPTY_SCHEMATIC)

        self.assertEqual(report["sheets"][0]["violations"], [])

    def test_003_a_real_report_has_the_real_confirmed_top_level_shape(self):
        report = run_drc(_EMPTY_BOARD)
        for key in ("$schema", "coordinate_units", "kicad_version", "violations", "unconnected_items"):
            self.assertIn(key, report)


class TestRealExportBoardGlb(unittest.TestCase):
    """Real, non-mocked `kicad-cli pcb export glb` against the same
    real, committed fixture `TestRealRunDrcAndErc` already uses --
    CTX-311.1. Skips itself cleanly when kicad-cli isn't found, same
    convention as every other real-tool test in this module."""

    def setUp(self):
        if not _find_real_kicad_cli():
            self.skipTest("kicad-cli not found on this machine.")
        kicad_cli._output_dir_override = None

    def tearDown(self):
        kicad_cli._output_dir_override = None

    def test_001_produces_a_real_glb_file(self):
        output_path = export_board_glb(_EMPTY_BOARD)
        try:
            self.assertTrue(os.path.exists(output_path))
            self.assertGreater(os.path.getsize(output_path), 0)
            with open(output_path, 'rb') as f:
                # glTF's own real binary container magic (confirmed
                # live against this exact real export during SPEC-311's
                # own research).
                self.assertEqual(f.read(4), b'glTF')
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_002_respects_a_configured_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            kicad_cli.configure(output_dir=tmp_dir)
            output_path = export_board_glb(_EMPTY_BOARD)
            self.assertEqual(os.path.dirname(output_path), tmp_dir)
            self.assertTrue(os.path.exists(output_path))

    def test_003_a_missing_input_file_raises_a_clean_error(self):
        with self.assertRaises(KicadCliError) as ctx:
            export_board_glb('/nonexistent/board.kicad_pcb')
        self.assertIn("does not exist", str(ctx.exception))

    def test_004_a_real_origin_shifts_the_real_exported_bounding_box_by_exactly_that_amount(self):
        """CTX-311.15: `origin_x_mm`/`origin_y_mm` become `--user-origin
        {x}x{y}mm` -- this is the real mechanism `EnclosureViewer.tsx`
        relies on to composite the board glb inside the enclosure glb
        with a simple, already-known constant translation. Verified here
        against real `kicad-cli`, not assumed from the CLI's own
        `--help` text: the real exported bounding box's X/Z minimums
        shift by exactly `-origin_mm/1000` real meters relative to the
        unshifted (no-origin) export -- the same real relationship the
        live prototype that motivated this whole context found by hand
        before any of this was implemented."""
        import trimesh

        default_path = export_board_glb(_EMPTY_BOARD)
        shifted_path = export_board_glb(_EMPTY_BOARD, 10.0, 5.0)
        try:
            default_bounds = trimesh.load(default_path).bounds
            shifted_bounds = trimesh.load(shifted_path).bounds
            self.assertAlmostEqual(
                shifted_bounds[0][0] - default_bounds[0][0], -10.0 / 1000, places=5,
            )
            self.assertAlmostEqual(
                shifted_bounds[0][2] - default_bounds[0][2], -5.0 / 1000, places=5,
            )
        finally:
            for p in (default_path, shifted_path):
                if os.path.exists(p):
                    os.remove(p)


_ATTINY85_PINS = [
    {"number": "1", "name": "RESET", "electrical_type": "bidirectional"},
    {"number": "2", "name": "PB3", "electrical_type": "input"},
    {"number": "3", "name": "PB4", "electrical_type": "output"},
    {"number": "4", "name": "GND", "electrical_type": "ground"},
]
_SOIC4_PADS = [
    {"number": "1", "x_mm": -2.0, "y_mm": -1.27, "width_mm": 1.5, "height_mm": 0.6,
     "pad_type": "smd", "drill_mm": None},
    {"number": "2", "x_mm": -2.0, "y_mm": 1.27, "width_mm": 1.5, "height_mm": 0.6,
     "pad_type": "smd", "drill_mm": None},
]
_SOIC4_COURTYARD = {"length_mm": 5.4, "width_mm": 4.4}


class TestExportSymbolSvgErrorHandling(unittest.TestCase):
    """Mocked -- no real kicad-cli needed to verify the error-mapping
    logic itself, matching TestRunReportErrorHandling's own shape."""

    @patch('kicad_cli.find_kicad_cli', return_value='/fake/kicad-cli')
    def test_001_a_missing_input_file_raises_a_clean_error(self, mock_find):
        with self.assertRaises(KicadCliError) as ctx:
            export_symbol_svg('/nonexistent/Foo.kicad_sym')
        self.assertIn("does not exist", str(ctx.exception))

    @patch('kicad_cli.subprocess.run')
    @patch('kicad_cli.find_kicad_cli', return_value='/fake/kicad-cli')
    def test_002_a_run_that_never_produces_an_svg_raises_a_clean_error(self, mock_find, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "some real kicad-cli failure text"
        with tempfile.NamedTemporaryFile(suffix=".kicad_sym") as f:
            with self.assertRaises(KicadCliError) as ctx:
                export_symbol_svg(f.name)
        self.assertIn("some real kicad-cli failure text", str(ctx.exception))


class TestExportFootprintSvgErrorHandling(unittest.TestCase):

    @patch('kicad_cli.find_kicad_cli', return_value='/fake/kicad-cli')
    def test_001_a_missing_pretty_dir_raises_a_clean_error(self, mock_find):
        with self.assertRaises(KicadCliError) as ctx:
            export_footprint_svg('/nonexistent/Foo.pretty', 'Foo')
        self.assertIn("does not exist", str(ctx.exception))

    @patch('kicad_cli.subprocess.run')
    @patch('kicad_cli.find_kicad_cli', return_value='/fake/kicad-cli')
    def test_002_a_run_that_never_produces_an_svg_raises_a_clean_error(self, mock_find, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "some real kicad-cli failure text"
        with tempfile.TemporaryDirectory() as pretty_dir:
            with self.assertRaises(KicadCliError) as ctx:
                export_footprint_svg(pretty_dir, 'Foo')
        self.assertIn("some real kicad-cli failure text", str(ctx.exception))


class TestRealExportSymbolSvg(unittest.TestCase):
    """Real, non-mocked kicad-cli calls against a real, valid .kicad_sym
    file -- reusing library_store's own proven builder (already verified
    parseable by real kicad-cli in test_library_store.py) rather than
    hand-crafting new S-expression text here. Skips itself cleanly when
    kicad-cli isn't found, same convention as every other real-tool test
    in this module."""

    def setUp(self):
        if not _find_real_kicad_cli():
            self.skipTest("kicad-cli not found on this machine.")
        kicad_cli._output_dir_override = None

    def tearDown(self):
        kicad_cli._output_dir_override = None

    def test_001_produces_a_real_svg_file(self):
        text = library_store._build_kicad_sym_text(
            {"symbol_id": "ATtiny85_4pin", "reference_prefix": "U", "pins": _ATTINY85_PINS}
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            sym_path = os.path.join(tmp_dir, "ATtiny85_4pin.kicad_sym")
            with open(sym_path, "w", encoding="utf-8") as f:
                f.write(text)

            output_path = export_symbol_svg(sym_path)

            self.assertTrue(os.path.exists(output_path))
            self.assertTrue(output_path.endswith(".svg"))
            with open(output_path, encoding="utf-8") as f:
                self.assertIn("<svg", f.read())

    def test_002_respects_a_configured_output_dir(self):
        text = library_store._build_kicad_sym_text(
            {"symbol_id": "ATtiny85_4pin", "reference_prefix": "U", "pins": _ATTINY85_PINS}
        )
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as out_dir:
            sym_path = os.path.join(tmp_dir, "ATtiny85_4pin.kicad_sym")
            with open(sym_path, "w", encoding="utf-8") as f:
                f.write(text)
            kicad_cli.configure(output_dir=out_dir)

            output_path = export_symbol_svg(sym_path)

            self.assertEqual(os.path.dirname(os.path.dirname(output_path)), out_dir)


class TestRealExportFootprintSvg(unittest.TestCase):
    """Real, non-mocked kicad-cli calls against a real, valid .kicad_mod
    file inside a real .pretty directory -- same reused-builder
    convention as the symbol test above."""

    def setUp(self):
        if not _find_real_kicad_cli():
            self.skipTest("kicad-cli not found on this machine.")
        kicad_cli._output_dir_override = None

    def tearDown(self):
        kicad_cli._output_dir_override = None

    def test_001_produces_a_real_svg_file(self):
        text = library_store._build_kicad_mod_text(
            {"footprint_id": "SOIC-4_test", "pads": _SOIC4_PADS, "courtyard": _SOIC4_COURTYARD}
        )
        with tempfile.TemporaryDirectory() as parent_dir:
            pretty_dir = os.path.join(parent_dir, "test.pretty")
            os.makedirs(pretty_dir)
            with open(os.path.join(pretty_dir, "SOIC-4_test.kicad_mod"), "w", encoding="utf-8") as f:
                f.write(text)

            output_path = export_footprint_svg(pretty_dir, "SOIC-4_test")

            self.assertTrue(os.path.exists(output_path))
            self.assertTrue(output_path.endswith(".svg"))
            with open(output_path, encoding="utf-8") as f:
                self.assertIn("<svg", f.read())


if __name__ == '__main__':
    unittest.main()

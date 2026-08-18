import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import kicad_cli
from kicad_cli import (
    KicadCliError, KicadCliUnavailableError, export_board_glb, find_kicad_cli, run_drc, run_erc,
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


if __name__ == '__main__':
    unittest.main()

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import fp_lib_table as flt

# Captured directly from this machine's own real global fp-lib-table
# (~/Library/Preferences/kicad/10.0/fp-lib-table) -- not fabricated. Real
# content the parser must handle correctly: one direct entry, one nested
# Table entry it must skip without crashing.
_REAL_FP_LIB_TABLE_CONTENT = '''(fp_lib_table
\t(version 7)
\t(lib (name "KiCad") (type "Table") (uri "/Applications/KiCad/KiCad.app/Contents/SharedSupport/template/fp-lib-table") (options "") (descr "KiCad Default Libraries"))
\t(lib (name "MyPCBLibs") (type "KiCad") (uri "/Users/keithelliott/repos/PCBs/MyPCBLibs.pretty") (options "") (descr ""))
)
'''


class TestParseFpLibTable(unittest.TestCase):

    def test_001_extracts_direct_entry_and_skips_table_entry(self):
        """TEST-001: the real direct entry is extracted; the real nested
        Table entry is skipped, not a crash, per CTX-308.1's own scope."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fp-lib-table")
            with open(path, "w") as f:
                f.write(_REAL_FP_LIB_TABLE_CONTENT)

            entries = flt.parse_fp_lib_table(path)

            self.assertEqual(entries, [
                {"name": "MyPCBLibs", "type": "KiCad", "uri": "/Users/keithelliott/repos/PCBs/MyPCBLibs.pretty"},
            ])

    def test_001b_missing_file_raises_a_clean_error(self):
        with self.assertRaises(flt.FpLibTableNotFoundError):
            flt.parse_fp_lib_table("/nonexistent/fp-lib-table")


class TestDefaultFpLibTablePath(unittest.TestCase):

    def test_002_resolves_to_this_machines_real_global_fp_lib_table(self):
        """TEST-002: real, live -- this machine actually has KiCad 10.0
        installed with a real global fp-lib-table."""
        path = flt.default_fp_lib_table_path()
        if path is None:
            self.skipTest("No KiCad config directory found on this machine.")
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(path.endswith("fp-lib-table"))


class TestListFootprintNames(unittest.TestCase):

    def test_003_missing_directory_returns_empty_list_not_a_crash(self):
        """TEST-003: a stale fp-lib-table entry pointing at a
        moved/deleted directory must not take down search."""
        self.assertEqual(flt.list_footprint_names("/nonexistent/some.pretty"), [])

    def test_003b_lists_real_kicad_mod_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "Foo.kicad_mod"), "w").close()
            open(os.path.join(tmp, "Bar.kicad_mod"), "w").close()
            open(os.path.join(tmp, "readme.txt"), "w").close()

            names = flt.list_footprint_names(tmp)

            self.assertEqual(sorted(names), ["Bar", "Foo"])


class TestSearchFootprintsReal(unittest.TestCase):

    def test_004_real_search_against_this_machines_own_library(self):
        """TEST-004: real, live -- finds the real, currently-present
        MP1584EN_5V_Module footprint in this machine's own MyPCBLibs.pretty
        (see CTX-308.1's own notes on this real fixture), or skips cleanly
        if this machine's real library layout has since changed."""
        path = flt.default_fp_lib_table_path()
        if path is None:
            self.skipTest("No KiCad config directory found on this machine.")

        entries = flt.parse_fp_lib_table(path)
        my_pcb_libs = next((e for e in entries if e["name"] == "MyPCBLibs"), None)
        if my_pcb_libs is None or not os.path.isdir(my_pcb_libs["uri"]):
            self.skipTest("This machine's own MyPCBLibs.pretty library is not present.")

        results = flt.search_footprints("MP1584")

        self.assertIn({"library": "MyPCBLibs", "footprint_name": "MP1584EN_5V_Module"}, results)

    def test_004b_no_match_returns_an_empty_list(self):
        path = flt.default_fp_lib_table_path()
        if path is None:
            self.skipTest("No KiCad config directory found on this machine.")

        self.assertEqual(flt.search_footprints("definitely_not_a_real_footprint_name_xyz"), [])


if __name__ == '__main__':
    unittest.main()

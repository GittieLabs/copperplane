import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import fp_lib_table as flt

# Modeled on this machine's own real global fp-lib-table
# (~/Library/Preferences/kicad/10.0/fp-lib-table) -- one direct entry,
# one Table entry. The Table entry's uri is deliberately a nonexistent
# path (not this machine's real nested table path, unlike an earlier
# version of this fixture) so this test stays isolated from whatever
# KiCad install happens to be on the machine running it -- real
# Table-entry *resolution* is TestTableEntryResolution's own job, with
# its own fully self-contained temp-dir fixture.
_REAL_FP_LIB_TABLE_CONTENT = '''(fp_lib_table
\t(version 7)
\t(lib (name "KiCad") (type "Table") (uri "/nonexistent/template/fp-lib-table") (options "") (descr "KiCad Default Libraries"))
\t(lib (name "MyPCBLibs") (type "KiCad") (uri "/Users/keithelliott/repos/PCBs/MyPCBLibs.pretty") (options "") (descr ""))
)
'''


class TestParseFpLibTable(unittest.TestCase):

    def test_001_extracts_direct_entry_and_skips_a_table_entry_with_a_missing_nested_file(self):
        """TEST-001: the real direct entry is extracted; a Table entry
        pointing at a missing nested file is skipped, not a crash --
        real Table-entry resolution against an actually-present nested
        file is CTX-308.3's own TestTableEntryResolution, below."""
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


class TestTableEntryResolution(unittest.TestCase):
    """CTX-308.3: (type "Table") entries -- KiCad's own built-in library
    set -- are now resolved for real, not skipped."""

    def test_001_table_entry_is_resolved_not_skipped(self):
        """TEST-001/TEST-005: an outer table's Table entry is followed to
        a real nested table, and the nested table's own real entries
        (with placeholders resolved) come back alongside the outer
        table's own direct entries -- neither list regresses the other."""
        with tempfile.TemporaryDirectory() as tmp:
            kicad_root = os.path.join(tmp, "KiCad.app", "Contents", "SharedSupport")
            template_dir = os.path.join(kicad_root, "template")
            footprints_dir = os.path.join(kicad_root, "footprints", "Battery.pretty")
            os.makedirs(template_dir)
            os.makedirs(footprints_dir)
            open(os.path.join(footprints_dir, "BatteryHolder_Test.kicad_mod"), "w").close()

            nested_table_path = os.path.join(template_dir, "fp-lib-table")
            with open(nested_table_path, "w") as f:
                f.write(
                    '(fp_lib_table\n'
                    '\t(lib (name "Battery") (type "KiCad") '
                    '(uri "${KICAD10_FOOTPRINT_DIR}/Battery.pretty") (options "") (descr ""))\n'
                    ')\n'
                )

            outer_table_path = os.path.join(tmp, "fp-lib-table")
            with open(outer_table_path, "w") as f:
                f.write(
                    '(fp_lib_table\n'
                    f'\t(lib (name "KiCad") (type "Table") (uri "{nested_table_path}") (options "") (descr ""))\n'
                    '\t(lib (name "MyPCBLibs") (type "KiCad") (uri "/some/user/MyPCBLibs.pretty") (options "") (descr ""))\n'
                    ')\n'
                )

            entries = flt.parse_fp_lib_table(outer_table_path)

            names = {e["name"] for e in entries}
            self.assertIn("MyPCBLibs", names)  # the direct entry, not regressed
            self.assertIn("Battery", names)  # the nested entry, now resolved
            battery = next(e for e in entries if e["name"] == "Battery")
            self.assertEqual(battery["uri"], footprints_dir)

    def test_002_resolve_placeholder_matches_any_kicad_version_number(self):
        """TEST-002: matched by digits, not the literal "KICAD10" -- a
        future KiCad major version must not silently break this."""
        self.assertEqual(flt._resolve_placeholder("${KICAD10_FOOTPRINT_DIR}/X.pretty", "/real/dir"), "/real/dir/X.pretty")
        self.assertEqual(flt._resolve_placeholder("${KICAD11_FOOTPRINT_DIR}/X.pretty", "/real/dir"), "/real/dir/X.pretty")
        self.assertEqual(flt._resolve_placeholder("${KICAD99_FOOTPRINT_DIR}/X.pretty", "/real/dir"), "/real/dir/X.pretty")

    def test_003_unrecognized_placeholder_is_skipped_not_a_crash(self):
        """TEST-003: an entry using a placeholder this module doesn't
        recognize is logged and skipped, not a crash and not silently
        treated as a literal (nonexistent) path."""
        with tempfile.TemporaryDirectory() as tmp:
            template_dir = os.path.join(tmp, "template")
            os.makedirs(template_dir)
            nested_table_path = os.path.join(template_dir, "fp-lib-table")
            with open(nested_table_path, "w") as f:
                f.write(
                    '(fp_lib_table\n'
                    '\t(lib (name "Weird") (type "KiCad") '
                    '(uri "${SOME_OTHER_VAR}/Weird.pretty") (options "") (descr ""))\n'
                    ')\n'
                )
            outer_table_path = os.path.join(tmp, "fp-lib-table")
            with open(outer_table_path, "w") as f:
                f.write(
                    '(fp_lib_table\n'
                    f'\t(lib (name "KiCad") (type "Table") (uri "{nested_table_path}") (options "") (descr ""))\n'
                    ')\n'
                )

            entries = flt.parse_fp_lib_table(outer_table_path)

            self.assertEqual(entries, [])


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

    def test_005_real_search_finds_a_builtin_library_result(self):
        """TEST-004 (CTX-308.3): real, live -- KiCad's own built-in
        Battery library is now reachable through the Table entry, not
        just a user's own directly-configured libraries."""
        path = flt.default_fp_lib_table_path()
        if path is None:
            self.skipTest("No KiCad config directory found on this machine.")

        entries = flt.parse_fp_lib_table(path)
        battery = next((e for e in entries if e["name"] == "Battery"), None)
        if battery is None or not os.path.isdir(battery["uri"]):
            self.skipTest("This machine's own KiCad install has no built-in Battery.pretty library.")

        results = flt.search_footprints("Battery")

        self.assertTrue(any(r["library"] == "Battery" for r in results))

    def test_005b_builtin_results_do_not_crowd_out_the_users_own_library(self):
        """TEST-005 (CTX-308.3): the pre-existing direct-entry result
        still appears once built-in libraries are also searched --
        real regression check, not just a new-feature check."""
        path = flt.default_fp_lib_table_path()
        if path is None:
            self.skipTest("No KiCad config directory found on this machine.")

        results = flt.search_footprints("MP1584")
        if not results:
            self.skipTest("This machine's own MyPCBLibs.pretty library is not present.")

        self.assertIn({"library": "MyPCBLibs", "footprint_name": "MP1584EN_5V_Module"}, results)


if __name__ == '__main__':
    unittest.main()

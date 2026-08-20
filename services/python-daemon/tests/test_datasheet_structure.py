import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import datasheet_structure as ds


# CTX-205.1: a real, committed 8-page synthetic datasheet PDF (not a
# mock) -- generated once via reportlab to mirror a real datasheet's
# structure (Absolute Maximum Ratings, Recommended Operating
# Conditions, Power Supply Decoupling, Reset, Clock/Oscillator, Layout
# Considerations, Typical Application Circuit, one section per page).
# Exercises the real `pdfplumber` extraction path end-to-end, per
# CLAUDE.md's "verify against the real thing" norm -- no PDF library
# existed in this repo before this context, so there is no mock to
# fall back on even if one were wanted.
FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_datasheet.pdf")


class TestExtractPages(unittest.TestCase):

    def test_001_extracts_every_real_page_with_1_indexed_numbers(self):
        pages = ds.extract_pages(FIXTURE_PATH)

        self.assertEqual(len(pages), 8)
        self.assertEqual([p["page"] for p in pages], list(range(1, 9)))

    def test_002_each_page_carries_its_own_real_extracted_text(self):
        pages = ds.extract_pages(FIXTURE_PATH)

        self.assertIn("Absolute Maximum Ratings", pages[1]["text"])
        self.assertIn("Recommended Operating Conditions", pages[2]["text"])

    def test_003_a_real_unreadable_path_fails_closed_with_a_clean_error(self):
        with self.assertRaises(ds.DatasheetStructureError):
            ds.extract_pages(os.path.join(os.path.dirname(__file__), "fixtures", "does_not_exist.pdf"))

    def test_004_a_real_non_pdf_file_fails_closed_with_a_clean_error(self):
        not_a_pdf = os.path.join(os.path.dirname(__file__), "fixtures", "empty_schematic.kicad_sch")
        with self.assertRaises(ds.DatasheetStructureError):
            ds.extract_pages(not_a_pdf)


class TestLocateCandidateSections(unittest.TestCase):

    def setUp(self):
        self.pages = ds.extract_pages(FIXTURE_PATH)
        self.candidates = ds.locate_candidate_sections(self.pages)

    def test_005_every_real_category_is_present_in_the_result(self):
        self.assertEqual(set(self.candidates.keys()), set(ds.CATEGORY_PATTERNS.keys()))

    def test_006_absolute_maximum_ratings_is_found_on_its_real_page(self):
        self.assertEqual(self.candidates["absolute_maximum_ratings"], [2])

    def test_007_recommended_operating_conditions_is_found_on_its_real_page(self):
        self.assertEqual(self.candidates["recommended_operating_conditions"], [3])

    def test_008_power_and_decoupling_both_match_the_same_real_shared_page(self):
        # The fixture's own "9. Power Supply Decoupling" heading covers
        # both real categories on one page -- a category match is never
        # exclusive of another category matching the same page.
        self.assertIn(4, self.candidates["power"])
        self.assertIn(4, self.candidates["decoupling"])

    def test_009_reset_is_found_on_its_real_page(self):
        # Real cross-reference, not a false positive: page 2's Absolute
        # Maximum Ratings table also says "Voltage on any Pin except
        # RESET", and page 8's Typical Application text mentions "reset
        # circuit" -- a candidate match legitimately isn't exclusive to
        # one page, matching this function's own "candidates," not
        # "final assignment," contract.
        self.assertIn(5, self.candidates["reset"])

    def test_010_clock_oscillator_is_found_on_its_real_page(self):
        # Same real-cross-reference reasoning as test_009: page 1's
        # feature list says "Oscillator", page 7's Layout section
        # mentions "crystal"/"oscillator" pins too.
        self.assertIn(6, self.candidates["clock_oscillator"])

    def test_011_layout_is_found_on_its_real_page(self):
        self.assertEqual(self.candidates["layout"], [7])

    def test_012_typical_application_is_found_on_its_real_page(self):
        self.assertEqual(self.candidates["typical_application"], [8])

    def test_013_a_category_with_zero_real_matches_is_present_as_an_empty_list_not_omitted(self):
        pages = [{"page": 1, "text": "This document mentions nothing relevant at all."}]
        candidates = ds.locate_candidate_sections(pages)

        self.assertEqual(candidates["reset"], [])
        self.assertIn("reset", candidates)


if __name__ == "__main__":
    unittest.main()

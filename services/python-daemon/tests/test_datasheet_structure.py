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

    def test_009_reset_is_found_on_its_real_page_only(self):
        # CTX-205.5: previously a real cross-reference on page 2/8 also
        # matched (whole-page keyword search), asserted with assertIn.
        # Now that detection is heading-based (real "10. Reset Circuit"
        # heading found only on page 5), incidental mentions of the
        # word "reset" elsewhere no longer pollute this category at
        # all -- exactly the real fix a real 234-page datasheet needed
        # (see CTX-205.5's own Plan Drift).
        self.assertEqual(self.candidates["reset"], [5])

    def test_010_clock_oscillator_is_found_on_its_real_page_only(self):
        # CTX-205.5: same real fix as test_009.
        self.assertEqual(self.candidates["clock_oscillator"], [6])

    def test_011_layout_is_found_on_its_real_page(self):
        self.assertEqual(self.candidates["layout"], [7])

    def test_012_typical_application_is_found_on_its_real_page(self):
        self.assertEqual(self.candidates["typical_application"], [8])

    def test_013_a_category_with_zero_real_matches_is_present_as_an_empty_list_not_omitted(self):
        pages = [{"page": 1, "text": "This document mentions nothing relevant at all."}]
        candidates = ds.locate_candidate_sections(pages)

        self.assertEqual(candidates["reset"], [])
        self.assertIn("reset", candidates)


class TestFindHeadings(unittest.TestCase):
    """CTX-205.5: a real, serious bug found by testing against a real
    234-page ATtiny85 datasheet, not this module's own small synthetic
    fixture -- the original whole-page keyword search matched "reset"
    on 84 of 234 real pages and "clock"/"oscillator" on 141, since both
    words appear constantly in real register/peripheral descriptions,
    not just the real Reset/Clock sections. Heading-based detection
    fixes this; these tests cover the real, genuine false positive
    that surfaced while building the fix itself (a wrapped line
    starting with a number, indistinguishable from a real heading
    number by position alone)."""

    def test_014_a_real_numbered_heading_is_found(self):
        pages = [{"page": 1, "text": "8.2 Reset Sources\nThe RESET pin has an internal pull-up."}]

        headings = ds._find_headings(pages)

        self.assertEqual(headings, [{"page": 1, "title": "Reset Sources"}])

    def test_015_a_table_of_contents_dotted_leader_line_is_not_a_real_heading(self):
        pages = [{
            "page": 1,
            "text": "4.8 Reset and Interrupt Handling ...........................................................................12",
        }]

        self.assertEqual(ds._find_headings(pages), [])

    def test_016_a_wrapped_line_that_happens_to_start_with_a_number_is_not_a_real_heading(self):
        # The real false positive found while building this fix: real
        # prose wrapped across a line boundary can itself start with a
        # number ("...an external\n10 kOhm pull-up resistor to VCC
        # should be added...") -- indistinguishable from a real heading
        # number by position alone. Real headings in both this
        # datasheet and this module's own fixture are a handful of
        # words; this fake one runs to 13.
        pages = [{
            "page": 1,
            "text": "10 kOhm pull-up resistor to VCC should be added to the RESET pin to prevent spurious resets.",
        }]

        self.assertEqual(ds._find_headings(pages), [])

    def test_017_a_real_short_heading_at_the_word_cap_boundary_still_counts(self):
        # Exactly _MAX_HEADING_WORDS (8) real words -- must still count
        # as a real heading, not be rejected by an off-by-one in the cap.
        pages = [{"page": 1, "text": "1 One Two Three Four Five Six Seven"}]

        headings = ds._find_headings(pages)

        self.assertEqual(len(headings), 1)


class TestLocateCandidateSectionsHeadingBased(unittest.TestCase):
    """CTX-205.5: the real section-boundary logic (a category's section
    extends from its own real heading up to, but not including, the
    next real heading anywhere in the document, capped at
    `_MAX_SECTION_PAGES`), isolated from the real fixture PDF above so
    boundary behavior is exercised directly and precisely."""

    def test_018_a_section_extends_to_but_not_past_the_next_real_heading(self):
        pages = [
            {"page": 1, "text": "8 Reset\nSome real reset guidance here."},
            {"page": 2, "text": "More real reset guidance, still no new heading."},
            {"page": 3, "text": "9 Clock\nSome real clock guidance here."},
        ]

        candidates = ds.locate_candidate_sections(pages)

        self.assertEqual(candidates["reset"], [1, 2])
        self.assertEqual(candidates["clock_oscillator"], [3])

    def test_019_a_real_section_with_no_further_heading_runs_to_the_cap_not_the_document_end(self):
        pages = [{"page": n, "text": "irrelevant body text, no new heading here"} for n in range(1, 11)]
        pages[0] = {"page": 1, "text": "8 Reset\nSome real reset guidance here."}

        candidates = ds.locate_candidate_sections(pages)

        self.assertEqual(candidates["reset"], [1, 2, 3, 4])  # capped at _MAX_SECTION_PAGES, not all 10 pages

    def test_020_a_category_with_no_real_heading_anywhere_falls_back_to_the_real_keyword_search(self):
        pages = [
            {"page": 1, "text": "No numbered heading on this page, but it does mention reset in passing."},
            {"page": 2, "text": "Also just mentions reset here, still no real heading anywhere."},
        ]

        candidates = ds.locate_candidate_sections(pages)

        self.assertEqual(candidates["reset"], [1, 2])


if __name__ == "__main__":
    unittest.main()

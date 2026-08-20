import asyncio
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import datasheet_guidance as dg


def _load_dotenv_local() -> None:
    """Loads KEY=VALUE lines from the repo root's .env.local into
    os.environ, mirroring test_component_pipeline.py's own real
    convention for making a real ANTHROPIC_API_KEY available locally
    without ever committing one."""
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env.local'))
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv_local()

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_datasheet.pdf")


class TestExtractJson(unittest.TestCase):

    def test_001_parses_a_real_plain_json_array(self):
        result = dg._extract_json('[{"quote": "x", "page": 1}]')
        self.assertEqual(result, [{"quote": "x", "page": 1}])

    def test_002_strips_a_real_markdown_code_fence(self):
        result = dg._extract_json('```json\n[{"quote": "x", "page": 1}]\n```')
        self.assertEqual(result, [{"quote": "x", "page": 1}])

    def test_003_invalid_json_raises_datasheet_guidance_error(self):
        with self.assertRaises(dg.DatasheetGuidanceError):
            dg._extract_json("not real json at all {{{")


class TestQuoteAppearsOnPage(unittest.TestCase):

    def test_004_an_exact_real_substring_matches(self):
        self.assertTrue(dg._quote_appears_on_page("100 nF decoupling capacitor", "Use a 100 nF decoupling capacitor near VCC."))

    def test_005_whitespace_differences_still_match(self):
        page_text = "A 100 nF\nceramic   decoupling\ncapacitor should be placed close."
        self.assertTrue(dg._quote_appears_on_page("A 100 nF ceramic decoupling capacitor should be placed close.", page_text))

    def test_006_case_differences_still_match(self):
        self.assertTrue(dg._quote_appears_on_page("RESET PIN", "the reset pin has an internal pull-up"))

    def test_007_a_real_quote_not_on_the_page_does_not_match(self):
        self.assertFalse(dg._quote_appears_on_page("this text is nowhere on the page", "completely unrelated real content"))


class TestBuildPageExcerpt(unittest.TestCase):

    def test_008_builds_one_labeled_section_per_real_page_in_order(self):
        pages_by_number = {2: "AMR text", 5: "Reset text"}
        excerpt = dg._build_page_excerpt(pages_by_number, [2, 5])

        self.assertIn("--- Page 2 ---\nAMR text", excerpt)
        self.assertIn("--- Page 5 ---\nReset text", excerpt)
        self.assertLess(excerpt.index("Page 2"), excerpt.index("Page 5"))


class TestValidateHandler(unittest.IsolatedAsyncioTestCase):

    def _handler(self, pages_by_number=None, category="reset", page_numbers=None):
        pages_by_number = pages_by_number if pages_by_number is not None else {5: "The RESET pin has an internal pull-up."}
        page_numbers = page_numbers if page_numbers is not None else [5]
        return dg._make_validate_handler(pages_by_number, category, page_numbers)

    async def test_009_a_real_valid_item_is_kept(self):
        handler = self._handler()
        message = json.dumps([{"quote": "The RESET pin has an internal pull-up.", "page": 5}])

        output = await handler(message, {})

        self.assertEqual(output.artifacts["items"], [{"quote": "The RESET pin has an internal pull-up.", "page": 5, "category": "reset"}])

    async def test_010_an_item_citing_a_page_outside_this_categorys_real_candidates_is_dropped(self):
        handler = self._handler(page_numbers=[5])
        message = json.dumps([{"quote": "anything", "page": 99}])

        output = await handler(message, {})

        self.assertEqual(output.artifacts["items"], [])

    async def test_011_an_item_whose_quote_is_not_really_on_the_cited_page_is_dropped(self):
        handler = self._handler(pages_by_number={5: "The RESET pin has an internal pull-up."})
        message = json.dumps([{"quote": "this sentence does not appear on page 5 at all", "page": 5}])

        output = await handler(message, {})

        self.assertEqual(output.artifacts["items"], [])

    async def test_012_a_real_empty_array_response_is_a_valid_empty_result(self):
        handler = self._handler()

        output = await handler("[]", {})

        self.assertEqual(output.artifacts["items"], [])

    async def test_013_malformed_items_are_skipped_not_fatal(self):
        handler = self._handler()
        message = json.dumps([
            "not a dict",
            {"quote": "The RESET pin has an internal pull-up.", "page": "5"},  # page not an int
            {"page": 5},  # missing quote
            {"quote": "The RESET pin has an internal pull-up.", "page": 5},  # real, valid
        ])

        output = await handler(message, {})

        self.assertEqual(len(output.artifacts["items"]), 1)

    async def test_014_a_non_list_response_yields_a_real_empty_result_not_an_error(self):
        handler = self._handler()

        output = await handler(json.dumps({"not": "a list"}), {})

        self.assertEqual(output.artifacts["items"], [])


class TestGenerateDatasheetGuidanceShortCircuit(unittest.TestCase):
    """`generate_datasheet_guidance`'s own real "zero candidates, zero LLM
    calls" behavior -- CTX-205.1's own real extraction/location functions
    are mocked here specifically because they're already, separately,
    fully covered for real in test_datasheet_structure.py; this test's
    real subject is the orchestration short-circuit itself, which invalid
    `secrets` proves deterministically (a real LLM call with no real key
    would raise, so a call that returns cleanly never attempted one)."""

    @mock.patch("datasheet_guidance.locate_candidate_sections")
    @mock.patch("datasheet_guidance.extract_pages")
    def test_015_a_category_with_zero_real_candidates_never_calls_the_llm(self, mock_extract, mock_locate):
        mock_extract.return_value = [{"page": 1, "text": "irrelevant"}]
        mock_locate.return_value = {"reset": []}

        result = dg.generate_datasheet_guidance(
            "irrelevant/path.pdf", categories=["reset"], secrets={"anthropic_api_key": "not-a-real-key"},
        )

        self.assertEqual(result, {"categories": {"reset": []}, "summaries": {"reset": None}})


class TestRealGenerateDatasheetGuidance(unittest.TestCase):
    """Real, non-mocked runs of the full extract -> validate DAG against
    the real committed fixture -- CLAUDE.md's 'verify for real' norm.
    Skips itself cleanly when no real credential is available (e.g. in
    CI), matching test_component_pipeline.py's own established
    convention for this exact class of test."""

    def test_016_a_real_category_with_real_candidates_returns_real_cited_items(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        result = dg.generate_datasheet_guidance(
            FIXTURE_PATH, categories=["reset"], secrets={"anthropic_api_key": api_key},
        )

        self.assertIn("reset", result["categories"])
        items = result["categories"]["reset"]
        self.assertGreater(len(items), 0)
        for item in items:
            self.assertIn(item["page"], (2, 5, 8))  # the fixture's own real reset-mentioning pages
            self.assertTrue(item["quote"].strip())
            self.assertEqual(item["category"], "reset")

    def test_017_every_requested_category_is_present_in_the_real_result_even_when_not_all_run(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        result = dg.generate_datasheet_guidance(
            FIXTURE_PATH, categories=["reset", "layout"], secrets={"anthropic_api_key": api_key},
        )

        self.assertEqual(set(result["categories"].keys()), {"reset", "layout"})
        self.assertEqual(set(result["summaries"].keys()), {"reset", "layout"})

    def test_018_a_real_category_with_real_cited_items_gets_a_real_plain_language_summary(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.skipTest("ANTHROPIC_API_KEY not set. Add it to .env.local to run this test for real.")

        result = dg.generate_datasheet_guidance(
            FIXTURE_PATH, categories=["reset"], secrets={"anthropic_api_key": api_key},
        )

        self.assertGreater(len(result["categories"]["reset"]), 0)
        summary = result["summaries"]["reset"]
        self.assertIsInstance(summary, str)
        self.assertTrue(summary.strip())

class TestRunAllCategoriesSynthesisShortCircuit(unittest.IsolatedAsyncioTestCase):
    """CTX-205.7: the real "zero validated items, zero synthesis LLM
    call" short-circuit, proven deterministically via mocking at the
    `_run_all_categories_and_close` level -- every real category in the
    committed fixture has at least one real candidate page (CTX-205.1's
    own fixture design), so this can't be exercised end-to-end against
    real content without an artificially impoverished fixture."""

    @mock.patch("datasheet_guidance._run_synthesis_workflow")
    @mock.patch("datasheet_guidance._run_category_workflow")
    async def test_019_a_category_with_zero_validated_items_never_calls_synthesis(self, mock_category, mock_synthesis):
        mock_category.return_value = []

        results, summaries = await dg._run_all_categories_and_close(
            {"reset": [5]}, {5: "irrelevant"}, mock.Mock(), {}, None, None,
        )

        self.assertEqual(results, {"reset": []})
        self.assertIsNone(summaries["reset"])
        mock_synthesis.assert_not_called()

    @mock.patch("datasheet_guidance._run_synthesis_workflow")
    @mock.patch("datasheet_guidance._run_category_workflow")
    async def test_020_a_category_with_real_validated_items_calls_synthesis_once(self, mock_category, mock_synthesis):
        items = [{"quote": "x", "page": 5, "category": "reset"}]
        mock_category.return_value = items
        mock_synthesis.return_value = "A real plain-language summary."

        results, summaries = await dg._run_all_categories_and_close(
            {"reset": [5]}, {5: "irrelevant"}, mock.Mock(), {}, None, None,
        )

        self.assertEqual(results, {"reset": items})
        self.assertEqual(summaries["reset"], "A real plain-language summary.")
        mock_synthesis.assert_called_once()


if __name__ == "__main__":
    unittest.main()

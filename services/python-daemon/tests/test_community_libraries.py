import json
import os
import sys
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import community_libraries as cl


class CommunityLibrariesTestCase(unittest.TestCase):
    def setUp(self):
        # The tree cache is module-level and real, hand-verified content
        # is worth reusing across a real test run -- but each test must
        # start from a known, empty state so a mocked test never
        # accidentally reuses a real, live-fetched entry from a
        # different test.
        cl._tree_cache.clear()


class TestSearchCommunityFootprintsReal(CommunityLibrariesTestCase):
    """Real, live GitHub API calls -- CLAUDE.md's own 'verify against
    the real thing when it's available' norm. Skips itself cleanly on
    any real network failure or rate limit, rather than failing the
    whole suite for an environment reason outside this code's control."""

    def test_001_a_real_query_finds_a_real_espressif_footprint(self):
        try:
            results = cl.search_community_footprints("ESP32-C3-MINI")
        except cl.CommunityLibraryError as e:
            self.skipTest(f"Real GitHub API call failed (network/rate limit): {e}")

        matching = [r for r in results if r["owner"] == "espressif"]
        self.assertGreater(len(matching), 0)
        self.assertTrue(matching[0]["path"].endswith(".kicad_mod"))
        self.assertEqual(matching[0]["kind"], "footprint")
        self.assertIn("download_url", matching[0])

    def test_002_a_real_query_finds_a_real_sparkfun_footprint(self):
        try:
            results = cl.search_community_footprints("C_0201")
        except cl.CommunityLibraryError as e:
            self.skipTest(f"Real GitHub API call failed (network/rate limit): {e}")

        matching = [r for r in results if r["owner"] == "sparkfun"]
        self.assertGreater(len(matching), 0)
        self.assertEqual(matching[0]["license"], "CC-BY-4.0")

    def test_003_a_query_with_no_real_match_anywhere_returns_an_empty_list_not_an_error(self):
        try:
            results = cl.search_community_footprints("totally-nonexistent-part-xyz-12345")
        except cl.CommunityLibraryError as e:
            self.skipTest(f"Real GitHub API call failed (network/rate limit): {e}")

        self.assertEqual(results, [])


class TestTreeCache(CommunityLibrariesTestCase):
    """Mocked -- verifies the in-process cache behavior itself, which a
    real, slow, rate-limited API call can't reliably exercise (a live
    test can't force a cache miss vs. hit on demand)."""

    def test_001_a_second_search_within_ttl_does_not_re_fetch_the_tree(self):
        call_count = {"n": 0}

        def fake_request(path, github_token):
            call_count["n"] += 1
            if "/git/trees/" in path:
                return {"tree": [{"path": "footprints/x.pretty/Foo.kicad_mod", "type": "blob"}]}
            return {"default_branch": "main"}

        with patch.object(cl, "_github_request", side_effect=fake_request):
            cl.search_community_footprints("Foo")
            first_call_count = call_count["n"]
            cl.search_community_footprints("Foo")
            second_call_count = call_count["n"]

        self.assertEqual(first_call_count, second_call_count)

    def test_002_an_expired_entry_triggers_a_real_re_fetch(self):
        call_count = {"n": 0}

        def fake_request(path, github_token):
            call_count["n"] += 1
            if "/git/trees/" in path:
                return {"tree": [{"path": "footprints/x.pretty/Foo.kicad_mod", "type": "blob"}]}
            return {"default_branch": "main"}

        with patch.object(cl, "_github_request", side_effect=fake_request):
            cl.search_community_footprints("Foo")
            after_first = call_count["n"]
            # Backdate every cached entry rather than sleeping past the
            # real TTL -- deterministic, matches this test suite's own
            # established convention (test_library_store.py's now-
            # removed supplier-pricing test used the identical
            # backdating approach for the same reason).
            for key in list(cl._tree_cache.keys()):
                _, tree = cl._tree_cache[key]
                cl._tree_cache[key] = (cl._tree_cache[key][0] - cl._TREE_CACHE_TTL_S - 1, tree)
            cl.search_community_footprints("Foo")
            after_second = call_count["n"]

        self.assertGreater(after_second, after_first)


class TestGithubRequestErrorHandling(CommunityLibrariesTestCase):
    """Mocked -- real error shapes urllib actually raises, verified
    against this module's own real error-translation logic."""

    def test_001_a_rate_limit_response_raises_a_clear_community_library_error(self):
        error = urllib.error.HTTPError(
            url="https://api.github.com/x", code=403, msg="rate limit exceeded",
            hdrs=None, fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(cl.CommunityLibraryError) as ctx:
                cl._github_request("/x", None)
            self.assertIn("rate limit", str(ctx.exception).lower())

    def test_002_a_real_network_timeout_raises_community_library_error_not_a_bare_exception(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(cl.CommunityLibraryError):
                cl._github_request("/x", None)

    def test_003_a_non_200_response_raises_community_library_error(self):
        class FakeResponse:
            status = 500
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            with self.assertRaises(cl.CommunityLibraryError):
                cl._github_request("/x", None)


if __name__ == "__main__":
    unittest.main()

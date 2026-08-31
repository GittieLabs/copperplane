"""SPEC-324: model identity verification.

The listers are substituted rather than mocked at import level -- the real
vendor SDKs are not installed in every environment this suite runs in, and
the behaviour worth pinning is the dispatch, the error-to-reason mapping,
and the "cannot list is not invalid" rule, none of which need a real SDK.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm_providers as lp  # noqa: E402


def _record(kind="anthropic", record_id="anthropic", base_url=None, api_key_ref="anthropic_api_key"):
    return {
        "id": record_id, "kind": kind, "base_url": base_url,
        "api_key_ref": api_key_ref, "models": {}, "capabilities": {},
    }


class TestListModels(unittest.TestCase):
    def setUp(self):
        self._saved = dict(lp._MODEL_LISTERS)

    def tearDown(self):
        lp._MODEL_LISTERS.clear()
        lp._MODEL_LISTERS.update(self._saved)

    def test_001_every_kind_this_repo_has_is_dispatchable(self):
        """TEST-001: the three kinds SPEC-208 defines all have a lister.
        A kind with no entry is the failure this catches -- it would report
        'unknown provider kind' at runtime rather than at review."""
        self.assertEqual({"anthropic", "openai_compat", "google"}, set(lp._MODEL_LISTERS))

    def test_002_returns_sorted_deduplicated_ids(self):
        lp._MODEL_LISTERS["anthropic"] = lambda key, url: ["b", "a", "b", ""]
        out = lp.list_models(_record(), "k")
        self.assertTrue(out["supported"])
        self.assertEqual(["a", "b"], out["models"])
        self.assertIsNone(out["reason"])

    def test_003_a_provider_that_cannot_list_is_reported_not_raised(self):
        """TEST-002: an openai_compat record may point at a server with no
        /v1/models. That is ordinary (SPEC-324 §2.1), so it must come back
        as supported=False with a reason, never as an exception."""
        def boom(key, url):
            raise RuntimeError("404 page not found")
        lp._MODEL_LISTERS["openai_compat"] = boom
        out = lp.list_models(_record(kind="openai_compat", record_id="custom"), "k")
        self.assertFalse(out["supported"])
        self.assertIn("404 page not found", out["reason"])
        self.assertEqual([], out["models"])

    def test_004_a_missing_sdk_says_so_rather_than_crashing(self):
        def missing(key, url):
            raise ImportError("No module named 'anthropic'")
        lp._MODEL_LISTERS["anthropic"] = missing
        out = lp.list_models(_record(), "k")
        self.assertFalse(out["supported"])
        self.assertIn("not installed", out["reason"])

    def test_005_no_api_key_is_reported_before_any_network_call(self):
        called = []
        lp._MODEL_LISTERS["anthropic"] = lambda key, url: called.append(key) or []
        out = lp.list_models(_record(), "")
        self.assertFalse(out["supported"])
        self.assertIn("no API key", out["reason"])
        self.assertEqual([], called, "must not reach the network without a key")

    def test_006_ollama_lists_without_a_key(self):
        """Ollama is a local server with no key (llm_providers' own
        placeholder convention), so the no-key guard must not block it."""
        seen = {}
        lp._MODEL_LISTERS["openai_compat"] = lambda key, url: seen.setdefault("key", key) and [] or ["llama3.2:1b"]
        out = lp.list_models(_record(kind="openai_compat", record_id="ollama", api_key_ref=None), "")
        self.assertTrue(out["supported"])
        self.assertEqual(["llama3.2:1b"], out["models"])

    def test_007_an_unknown_kind_is_a_reason_not_a_branch_error(self):
        out = lp.list_models(_record(kind="not-a-kind"), "k")
        self.assertFalse(out["supported"])
        self.assertIn("unknown provider kind", out["reason"])


class TestValidateModel(unittest.TestCase):
    def setUp(self):
        self._saved = dict(lp._MODEL_LISTERS)

    def tearDown(self):
        lp._MODEL_LISTERS.clear()
        lp._MODEL_LISTERS.update(self._saved)

    def test_008_a_listed_model_is_valid(self):
        lp._MODEL_LISTERS["anthropic"] = lambda key, url: ["claude-opus-5"]
        out = lp.validate_model(_record(), "k", "claude-opus-5")
        self.assertTrue(out["valid"])

    def test_009_an_unlisted_model_says_it_may_still_work(self):
        """SPEC-324 §2.2: free text is the floor. An id the provider did not
        list is reported honestly WITHOUT claiming it is wrong -- a private
        deployment or a model newer than the SDK's list is a real case."""
        lp._MODEL_LISTERS["anthropic"] = lambda key, url: ["claude-opus-5"]
        out = lp.validate_model(_record(), "k", "some-private-deployment")
        self.assertFalse(out["valid"])
        self.assertIn("may still work", out["reason"])

    def test_010_a_provider_that_cannot_list_is_unknown_not_invalid(self):
        """The rule that keeps this honest: never call a model wrong just
        because the server has no /v1/models. Saying nothing beats guessing."""
        def boom(key, url):
            raise RuntimeError("connection refused")
        lp._MODEL_LISTERS["openai_compat"] = boom
        out = lp.validate_model(_record(kind="openai_compat", record_id="custom"), "k", "anything")
        self.assertFalse(out["valid"])
        self.assertIn("could not check", out["reason"])
        self.assertNotIn("did not list", out["reason"])

    def test_011_whitespace_and_empty_ids_are_handled(self):
        lp._MODEL_LISTERS["anthropic"] = lambda key, url: ["claude-opus-5"]
        self.assertTrue(lp.validate_model(_record(), "k", "  claude-opus-5  ")["valid"])
        self.assertIn("no model id", lp.validate_model(_record(), "k", "   ")["reason"])

    def test_012_validation_never_sends_a_completion(self):
        """SPEC-324 §2.3/§3: quota is a real cost even for a cheap check, so
        validation is an existence check only. If this ever starts routing
        through chat(), this test is what catches it."""
        lp._MODEL_LISTERS["anthropic"] = lambda key, url: ["claude-opus-5"]
        calls = []
        saved = lp.chat
        lp.chat = lambda *a, **k: calls.append(a)  # type: ignore[assignment]
        try:
            lp.validate_model(_record(), "k", "claude-opus-5")
        finally:
            lp.chat = saved  # type: ignore[assignment]
        self.assertEqual([], calls, "validate_model must not send a completion")


if __name__ == "__main__":
    unittest.main()

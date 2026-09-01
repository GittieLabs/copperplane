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


class TestProbeEndpoint(unittest.TestCase):
    """CTX-321.3. A NEW openai_compat record starts with a blank base URL,
    and blank means the OpenAI SDK's own default -- api.openai.com. Nothing
    told a user a local server lives elsewhere, so the editor could not
    offer what list_models would happily have listed.

    Takes a URL rather than a provider id because the record being
    configured does not exist yet: _resolve_record_and_key has nothing to
    resolve for a draft.
    """

    def setUp(self):
        self._saved = lp._list_openai_compat

    def tearDown(self):
        lp._list_openai_compat = self._saved  # type: ignore[assignment]

    def test_013_a_reachable_endpoint_reports_its_models(self):
        lp._list_openai_compat = lambda key, base: ["llama3.2:1b", "qwen3:4b"]  # type: ignore[assignment]
        out = lp.probe_endpoint(lp.LOCAL_OLLAMA_BASE_URL)
        self.assertTrue(out["reachable"])
        self.assertEqual(["llama3.2:1b", "qwen3:4b"], out["models"])
        self.assertIsNone(out["reason"])

    def test_014_nothing_listening_is_an_ordinary_answer_not_a_raise(self):
        """The common case by far. A machine with no local server must see
        no error, because the editor stays silent rather than suggesting a
        URL that would not work."""
        def boom(key, base):
            raise ConnectionError("connection refused")

        lp._list_openai_compat = boom  # type: ignore[assignment]
        out = lp.probe_endpoint("http://localhost:11434/v1")
        self.assertFalse(out["reachable"])
        self.assertEqual([], out["models"])
        self.assertIn("connection refused", out["reason"])

    def test_015_a_blank_url_never_reaches_the_network(self):
        calls = []
        lp._list_openai_compat = lambda key, base: calls.append(base) or []  # type: ignore[assignment]
        for value in ("", "   ", None):
            out = lp.probe_endpoint(value)
            self.assertFalse(out["reachable"])
            self.assertEqual("no base URL given", out["reason"])
        self.assertEqual([], calls, "a blank URL must not be probed")

    def test_016_no_api_key_is_sent(self):
        """This probes unauthenticated local servers. It must never reach
        for a configured key -- there is no record to take one from, and a
        local endpoint does not want one."""
        seen = []
        lp._list_openai_compat = lambda key, base: seen.append(key) or ["m"]  # type: ignore[assignment]
        lp.probe_endpoint(lp.LOCAL_OLLAMA_BASE_URL)
        self.assertEqual([lp._OLLAMA_PLACEHOLDER_API_KEY], seen)

    def test_017_the_offered_url_is_the_ollama_preset_s_own(self):
        """The editor's suggestion and the preset's base_url are the same
        constant, so they cannot drift apart."""
        self.assertEqual(lp._OLLAMA_BASE_URL, lp.LOCAL_OLLAMA_BASE_URL)


class TestNetworkRoutesAreAsync(unittest.TestCase):
    """CTX-314.2 found this the expensive way: a route that makes a real
    network call but is left out of ASYNC_ROUTES runs inline in the
    daemon's stdin read loop and blocks every other request while it
    waits. It was true of a GitHub-calling route for a whole release.

    Nothing asserted the property afterwards, so the next route to make a
    network call could reintroduce it silently. CTX-321.3 added one, which
    is why this guard exists now rather than as a comment.
    """

    def test_018_every_vendor_calling_llm_route_is_async_registered(self):
        import daemon

        for route in ("llm.list_models", "llm.validate_model", "llm.probe_endpoint"):
            self.assertIn(
                route, daemon.ASYNC_ROUTES,
                f"{route} makes a real network call and must not run inline in the request path",
            )


if __name__ == "__main__":
    unittest.main()


class TestRecordParams(unittest.TestCase):
    """CTX-209.1. A provider record's vendor params reach AgentFlow 0.11.1's
    own verbatim passthrough. This repo adds no second mechanism for
    something the framework already carries -- they ride on AgentConfig,
    which is where AgentFlow expects per-agent params to live.
    """

    def test_019_a_record_without_params_yields_an_empty_dict(self):
        """Absent and empty must be the same answer: AgentFlow treats a
        falsy params as 'send nothing', so a record that never had params
        and one whose params were cleared produce an identical request."""
        self.assertEqual({}, lp.record_params({"providers": [
            {"id": "p", "kind": "openai_compat", "models": {}, "capabilities": {}}
        ]}, "p"))

    def test_020_a_record_s_params_are_returned(self):
        out = lp.record_params({"providers": [
            {"id": "p", "kind": "openai_compat", "models": {}, "capabilities": {},
             "params": {"reasoning_effort": "high"}}
        ]}, "p")
        self.assertEqual({"reasoning_effort": "high"}, out)

    def test_021_an_unknown_provider_id_is_empty_not_an_error(self):
        """Called on every dispatch. Raising here would turn a stale role
        binding into a crash rather than the existing, clearer error."""
        self.assertEqual({}, lp.record_params({}, "nope"))

    def test_022_the_caller_cannot_mutate_the_stored_record(self):
        config = {"providers": [
            {"id": "p", "kind": "openai_compat", "models": {}, "capabilities": {},
             "params": {"reasoning_effort": "high"}}
        ]}
        out = lp.record_params(config, "p")
        out["reasoning_effort"] = "low"
        self.assertEqual("high", config["providers"][0]["params"]["reasoning_effort"])

    def test_023_a_preset_record_has_no_params_by_default(self):
        """Shipping a default param would be a claim about what a model
        supports -- exactly what SPEC-209 §1 declines to make."""
        for pid in ("anthropic", "google", "openai", "perplexity", "ollama"):
            self.assertEqual({}, lp.record_params({}, pid), pid)

#!/usr/bin/env python3
"""
Runs the Python daemon's test suites and asserts that the known live-CAD
integration tests are reported as SKIPPED on this machine, not silently
absent. A test that vanishes from the discovered suite (e.g. a broken
import, a typo'd test method name after a refactor) still exits 0 under
a bare `python -m unittest discover` -- this is the check that would
catch that, per ROADMAP.md SPEC-903: "verify the skips actually happen
rather than silently passing zero assertions."

On a machine with KiCad and/or FreeCAD actually installed (e.g. Keith's
Mac), these tests run for real instead of skipping -- that is the
correct, desired behavior there (see CTX-103.1/CTX-104.1), and this
script will report a mismatch in that case. It is meant to run in CI,
where neither tool is installed.
"""
import sys
import unittest

EXPECTED_SKIPS = {
    "test_002_real_kicad_version_round_trip",
    "test_004_real_enclosure_round_trip",
    # SPEC-201: no LLM provider credential or local Ollama server exists
    # on a CI runner, so every real-provider test skips itself cleanly.
    "test_001_real_anthropic_chat",
    "test_002_real_google_chat",
    "test_003_real_perplexity_chat",
    "test_004_real_ollama_chat",
    "test_005_real_openai_chat_not_verified_no_key_available",
    "test_001_llm_chat_dispatched_through_handle_request_reports_job_completed",
}


def run_and_collect_skips(start_dir: str) -> set[str]:
    suite = unittest.TestLoader().discover(start_dir)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        print(f"::error::{start_dir}: test suite had failures or errors", file=sys.stderr)
        sys.exit(1)
    return {test.id().rsplit(".", 1)[-1] for test, _reason in result.skipped}


def main() -> None:
    skipped = set()
    skipped |= run_and_collect_skips("services/python-daemon/tests")
    skipped |= run_and_collect_skips("scripts/tests")

    missing = EXPECTED_SKIPS - skipped
    if missing:
        print(
            f"::error::Expected these tests to report as SKIPPED (no KiCad/FreeCAD on this "
            f"runner), but they did not: {sorted(missing)}. A test that silently stopped "
            f"running would also show zero failures here -- this is exactly the check meant "
            f"to catch that.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"OK: confirmed expected live-CAD tests actually skipped: {sorted(EXPECTED_SKIPS)}")


if __name__ == "__main__":
    main()

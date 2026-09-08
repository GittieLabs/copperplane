"""Tests for `.kicad_dru` sidecar generation and its mandatory verification run.

SPEC-114 section 2.2, Limit 2: a malformed sidecar is discarded entirely and
silently -- no stderr, unchanged exit code, normal-looking report. A generated
file therefore may never be assumed to have taken effect. These tests are the
regression fence around that, and around Limit 1 (a rule cannot resurrect a
check the project has set to `ignore`).

Planned by CTX-114.1. Implemented phase by phase; this module is the harness
Phase 1 builds, before any profile object exists.
"""

import unittest


class DruSidecarPlaceholder(unittest.TestCase):
    def test_placeholder_until_ctx_114_1_phase_1(self):
        self.skipTest("CTX-114.1 Phase 1 has not been implemented yet")


if __name__ == "__main__":
    unittest.main()

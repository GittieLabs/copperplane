"""Tests for the CapabilityProfile record and its per-field provenance.

SPEC-114 section 2.6: every field is optional, an absent field produces no rule
rather than a guess, and each value carries its source URL, the date it was
recorded, and whether the user confirmed it. Mask dam and mask expansion are
recorded and displayed but can never be enforced through the sidecar.

Planned by CTX-114.1.
"""

import unittest


class CapabilityProfilePlaceholder(unittest.TestCase):
    def test_placeholder_until_ctx_114_1_phase_2(self):
        self.skipTest("CTX-114.1 Phase 2 has not been implemented yet")


if __name__ == "__main__":
    unittest.main()

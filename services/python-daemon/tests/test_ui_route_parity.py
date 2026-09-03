"""SPEC-407: the UI and the daemon must agree on what routes exist.

`CTX-407.5` made the frozen artifact prove it has the same routes as the
checkout. This is the same disagreement one boundary further out: the UI names
routes in string literals, and nothing checks them against the daemon that has
to answer. A renamed or removed route compiles, type-checks, passes every unit
test, and fails the first time a user clicks the thing.
"""
import glob
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import daemon

_UI_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "apps", "tauri-ui", "src")
)

#: `dispatch('x.y')` and `submitJob<T>('x.y')`, the two ways the UI reaches a
#: route. Only literals: a computed route name cannot be checked statically,
#: and there are none today.
_CALL = re.compile(r"""(?:dispatch|submitJob)\s*<?[^(]*\(\s*['"]([a-z_]+\.[a-z_]+)['"]""")


def _routes_the_ui_calls() -> dict:
    found = {}
    for pattern in ("**/*.ts", "**/*.tsx"):
        for path in glob.glob(os.path.join(_UI_SRC, pattern), recursive=True):
            if ".test." in os.path.basename(path):
                continue
            with open(path, encoding="utf-8") as handle:
                for match in _CALL.finditer(handle.read()):
                    found.setdefault(match.group(1), set()).add(os.path.basename(path))
    return found


@unittest.skipUnless(os.path.isdir(_UI_SRC), "the UI source tree is not present")
class TestEveryRouteTheUICallsExists(unittest.TestCase):
    def test_001_the_ui_calls_only_routes_the_daemon_registers(self):
        called = _routes_the_ui_calls()
        self.assertGreater(len(called), 50, "the scan found suspiciously few routes")

        missing = {
            route: sorted(files)
            for route, files in called.items()
            if route not in daemon.ROUTES
        }

        self.assertEqual(
            missing, {},
            "the UI calls routes this daemon does not register -- a rename or removal that "
            "compiles, type-checks, and fails on the first click",
        )

    def test_002_the_scan_would_notice_a_missing_route(self):
        """A check that cannot fail is not evidence. This proves the comparison
        reacts, rather than trusting that it would."""
        called = dict(_routes_the_ui_calls())
        called["project.definitely_not_a_route"] = {"invented.ts"}

        missing = [r for r in called if r not in daemon.ROUTES]

        self.assertEqual(missing, ["project.definitely_not_a_route"])

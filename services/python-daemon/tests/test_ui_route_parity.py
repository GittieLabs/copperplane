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


_DEGRADED_MAP = os.path.join(_UI_SRC, "lib", "degradedModules.ts")

#: `_note_degraded("kicad_cli", ...)` — every module the daemon can report as
#: having failed to import.
_NOTE_DEGRADED = re.compile(r'_note_degraded\(\s*"([a-z_]+)"')


@unittest.skipUnless(os.path.isfile(_DEGRADED_MAP), "the UI degraded-module map is not present")
class TestEveryDegradableModuleIsDescribed(unittest.TestCase):
    """SPEC-407 §5: the notice names what is lost in the user's terms.

    The UI falls back to naming an unknown module as itself, so a gap here is
    not a crash — it is a worse sentence at the worst moment. This keeps the
    two lists together, the same way `test_001` keeps routes together.
    """

    def test_001_every_module_the_daemon_can_degrade_has_a_plain_description(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "daemon.py"), encoding="utf-8") as f:
            modules = set(_NOTE_DEGRADED.findall(f.read()))
        with open(_DEGRADED_MAP, encoding="utf-8") as f:
            described = set(re.findall(r"^  ([a-z_]+):\s*['\"]", f.read(), re.M))

        self.assertGreater(len(modules), 10, "the scan found suspiciously few modules")
        self.assertEqual(
            sorted(modules - described), [],
            "these modules can fail to import and the app has no plain-language description for "
            "them, so a user would be shown a bare module name at the moment they are most "
            "confused",
        )

    def test_002_the_map_does_not_describe_modules_that_cannot_degrade(self):
        """A description for a module the daemon never reports is dead copy
        that reads as coverage."""
        with open(os.path.join(os.path.dirname(__file__), "..", "daemon.py"), encoding="utf-8") as f:
            modules = set(_NOTE_DEGRADED.findall(f.read()))
        with open(_DEGRADED_MAP, encoding="utf-8") as f:
            described = set(re.findall(r"^  ([a-z_]+):\s*['\"]", f.read(), re.M))

        self.assertEqual(sorted(described - modules), [])

"""A documentation page may not deny a capability the daemon ships.

The existing docs tests check names, versions, links and images -- everything
*about* a page except whether what it says is true. That is the gap this one
closes, and it is not hypothetical: `what-it-is.md` listed **"Reading your
schematic's contents"** under *"What is not built yet"* while the netlist reader
it denied was shipping a feature a day, and `board-checks.md` said there was
*"no AI review of your schematic yet"* after eight consideration packs had
landed. Both were written truthfully and neither was revisited.

The mechanism is deliberately narrow. It does not try to judge prose. It pairs a
**specific sentence** with the **route that falsifies it**, so the failure names
both and the fix is obvious. Adding a row is the cost of shipping a capability
the docs previously disclaimed, which is the moment someone is actually thinking
about it.
"""
import os
import re
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_PAGES = os.path.join(_ROOT, "docs", "site", "src", "content", "docs")
_DAEMON = os.path.join(os.path.dirname(__file__), "..", "daemon.py")

#: phrase -> the route whose existence makes that phrase false.
#:
#: Phrases are matched case-insensitively with runs of whitespace collapsed, so
#: a rewrap does not silently disarm a row. They are short on purpose: long
#: enough to be unambiguous, short enough to survive an edit that keeps the
#: claim while changing the sentence around it.
DISPROVED_BY_ROUTE = {
    "reading your schematic's contents": "kicad.list_schematic_components",
    "no ai review of your schematic": "project.considerations",
    "nothing that looks at the whole design and volunteers concerns":
        "project.considerations",
    "you have to choose it explicitly, every time": "kicad.resolve_project",
    "there is no way to know which schematic you are looking at":
        "kicad.resolve_project",
}

_WHITESPACE = re.compile(r"\s+")


def _normalised(text: str) -> str:
    return _WHITESPACE.sub(" ", text).lower()


def _pages():
    for root, _, files in os.walk(_PAGES):
        for name in files:
            if name.endswith((".md", ".mdx")):
                yield os.path.join(root, name)


def _registered_routes() -> set:
    """Route names the daemon registers, read from its source.

    Source rather than an import: this test must run on a machine where the
    daemon's optional dependencies are absent, and a route's registration line
    is present in the file either way.
    """
    with open(_DAEMON, encoding="utf-8") as handle:
        text = handle.read()
    return set(re.findall(r'routes\["([a-z_]+\.[a-z_]+)"\]', text)) | set(
        re.findall(r'^\s*"([a-z_]+\.[a-z_]+)":\s', text, re.M)
    )


@unittest.skipUnless(os.path.isdir(_PAGES), "the docs site is not present")
class DocsClaimsMatchDaemonTests(unittest.TestCase):

    def test_001_no_page_denies_a_capability_the_daemon_ships(self):
        routes = _registered_routes()
        found = []
        for page in _pages():
            with open(page, encoding="utf-8") as handle:
                text = _normalised(handle.read())
            for phrase, route in DISPROVED_BY_ROUTE.items():
                if phrase in text and route in routes:
                    found.append(
                        f"{os.path.relpath(page, _ROOT)} says {phrase!r}, "
                        f"but the daemon registers {route!r}"
                    )
        self.assertEqual(found, [], "\n  " + "\n  ".join(found))

    def test_002_every_named_route_is_one_the_daemon_actually_has(self):
        """A row naming a route that does not exist can never fire.

        `CLAUDE.md`: a check that cannot fail is not evidence. A typo here
        would disarm the row silently and leave the docs unguarded.
        """
        routes = _registered_routes()
        for phrase, route in DISPROVED_BY_ROUTE.items():
            self.assertIn(route, routes, f"{phrase!r} names a route that does not exist")

    def test_003_the_check_would_notice(self):
        """Exercised against the real sentence this context removed."""
        stale = _normalised(
            "## What is not built yet\n\n- **Reading your schematic's\n  contents.** "
            "KiCad's live IPC has no path-resolution call."
        )

        self.assertIn("reading your schematic's contents", stale)
        self.assertIn("kicad.list_schematic_components", _registered_routes())

    def test_004_a_rewrapped_sentence_is_still_caught(self):
        """The failure mode that would quietly disarm this whole file.

        A docs edit that rewraps a paragraph changes the newlines inside a
        sentence without changing a word of it.
        """
        rewrapped = _normalised("there is\n    no way to know which\n    schematic you are looking at")

        self.assertIn("there is no way to know which schematic you are looking at", rewrapped)


if __name__ == "__main__":
    unittest.main()

"""SPEC-408: the README makes claims, and claims go stale.

Written after finding that the README told a new macOS user to look for
`v0.1.1` (three releases old), drag **Hardware Agent Studio** into
`/Applications` (the app has been **Copperplane** since SPEC-405), and repair it
with `xattr -cr` against a path that does not exist. Every one of those was
wrong, none of them was caught, and the first person to notice would have been
someone trying to install it for the first time.
"""
import json
import os
import re
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_README = os.path.join(_ROOT, "README.md")
#: Other authored markdown whose relative links have to resolve. Deliberately a
#: list rather than a glob: docs/site has 16 pages with their own link rules,
#: and docs/research is archived thinking that is allowed to rot.
_ALSO_CHECKED = [
    os.path.join(_ROOT, "docs", "video", "product-video-script.md"),
    os.path.join(_ROOT, "docs", "video", "example-project.md"),
]
_TAURI_CONF = os.path.join(_ROOT, "core", "tauri-rust", "tauri.conf.json")

#: Names this product has had. A superseded one in install instructions sends a
#: user looking for an app that is not there.
#: Both spellings. The spaced form appears in prose; the concatenated form
#: appears in code, and was stamped into every footprint this app wrote into a
#: user's board for the entire life of the rename -- invisible to a guard that
#: only knew the spaced one.
_SUPERSEDED_NAMES = ["Hardware Agent Studio", "HardwareAgentStudio"]

#: `v1.2.3` in prose. A version in the README is a fact with an expiry date,
#: and this one expired three times before anyone noticed.
_VERSION = re.compile(r"\bv\d+\.\d+\.\d+\b")

#: `[text](target)` where target is not a URL or an anchor.
_RELATIVE_LINK = re.compile(r"\[[^\]]*\]\((?!https?://|#|mailto:)([^)]+)\)")


def _plain(text: str) -> str:
    """Shell-escaped paths hide a name from a literal search.

    `xattr -cr /Applications/Hardware\\ Agent\\ Studio.app` contains the old
    product name and does not contain the string "Hardware Agent Studio". The
    docs carried exactly that for weeks, and the first version of this check
    walked straight past it.
    """
    return text.replace("\\ ", " ")


def _readme() -> str:
    with open(_README, encoding="utf-8") as handle:
        return handle.read()


@unittest.skipUnless(os.path.isfile(_README), "README.md is not present")
class TestReadmeStaysTrue(unittest.TestCase):
    def test_001_uses_the_products_real_name(self):
        with open(_TAURI_CONF, encoding="utf-8") as handle:
            product = json.load(handle)["productName"]

        self.assertIn(product, _readme(), "the README never names the product")

    def test_002_names_no_superseded_product_name(self):
        readme = _plain(_readme())
        found = [name for name in _SUPERSEDED_NAMES if name in readme]

        self.assertEqual(
            found, [],
            "the README uses a name this product no longer has, which sends a new user looking "
            "for an application that does not exist",
        )

    def test_003_hardcodes_no_release_version(self):
        """Link Releases instead. The README claimed `v0.1.1` was current
        through v0.2.0, v0.3.0 and v0.3.1."""
        versions = sorted(set(_VERSION.findall(_readme())))

        self.assertEqual(
            versions, [],
            "the README names a specific release; link ../../releases instead, because a version "
            "in prose is a fact with an expiry date",
        )

    def test_004_every_relative_link_resolves(self):
        readme = _readme()
        broken = []
        for target in _RELATIVE_LINK.findall(readme):
            # `../../releases` and friends are GitHub-relative, not paths on disk.
            if target.startswith("../../"):
                continue
            path = os.path.join(_ROOT, target.split("#")[0])
            if not os.path.exists(path):
                broken.append(target)

        self.assertEqual(broken, [], "these README links point at files that do not exist")

    def test_005_the_checks_would_notice(self):
        """A check that cannot fail is not evidence -- and these run against a
        file nobody edits often, so their silence is easy to trust wrongly."""
        stale = "Drag Hardware Agent Studio to /Applications. Get v0.1.1. See [x](nope/missing.md)."

        self.assertTrue(any(n in stale for n in _SUPERSEDED_NAMES))
        self.assertEqual(_VERSION.findall(stale), ["v0.1.1"])
        self.assertEqual(_RELATIVE_LINK.findall(stale), ["nope/missing.md"])
        self.assertFalse(os.path.exists(os.path.join(_ROOT, "nope/missing.md")))


class TestAuthoredDocsLinksResolve(unittest.TestCase):
    """The same check, for documents a person follows while doing something --
    a dead link in a recording script is discovered at the worst moment."""

    def test_001_every_relative_link_resolves(self):
        broken = []
        for path in _ALSO_CHECKED:
            if not os.path.isfile(path):
                broken.append(f"{path} does not exist")
                continue
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            for target in _RELATIVE_LINK.findall(text):
                if target.startswith("../../"):
                    continue
                resolved = os.path.join(os.path.dirname(path), target.split("#")[0])
                if not os.path.exists(resolved):
                    broken.append(f"{os.path.basename(path)} -> {target}")

        self.assertEqual(broken, [])


_DOCS_PAGES = os.path.join(_ROOT, "docs", "site", "src", "content", "docs")


@unittest.skipUnless(os.path.isdir(_DOCS_PAGES), "the docs site is not present")
class TestDocsPagesStayTrue(unittest.TestCase):
    """The docs site had the same stale version the README did -- its index
    announced `v0.1.1` through v0.2.0, v0.3.0 and v0.3.1. Same failure, same
    check, one directory over."""

    def _pages(self):
        for root, _, files in os.walk(_DOCS_PAGES):
            for name in files:
                if name.endswith((".md", ".mdx")):
                    yield os.path.join(root, name)

    def test_001_no_page_names_a_superseded_product_name(self):
        offenders = []
        for path in self._pages():
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            for name in _SUPERSEDED_NAMES:
                if name in _plain(text):
                    offenders.append(f"{os.path.relpath(path, _DOCS_PAGES)}: {name}")

        self.assertEqual(offenders, [])

    def test_002_no_page_hardcodes_a_release_version(self):
        """A version in prose is a fact with an expiry date. Requirements like
        "KiCad 9+" are not release claims and use no `v` prefix."""
        offenders = []
        for path in self._pages():
            with open(path, encoding="utf-8") as handle:
                found = _VERSION.findall(handle.read())
            if found:
                offenders.append(f"{os.path.relpath(path, _DOCS_PAGES)}: {sorted(set(found))}")

        self.assertEqual(
            offenders, [],
            "link the releases page instead of naming a version that will be wrong within weeks",
        )


class SupersededNameInShippedStringsTests(unittest.TestCase):
    """The product name a user can end up holding.

    `HardwareAgentStudio` was the library nickname stamped onto every
    footprint injected into a KiCad board. It survived the rename because the
    documentation guard reads for "Hardware Agent Studio" -- with spaces, in
    prose -- and this is the concatenated form, in Python.

    Found in a real board file: `HardwareAgentStudio:NE555`.
    """

    #: Modules whose strings can reach a user's files or screen.
    _MODULES = ("kicad_write.py", "library_store.py", "daemon.py", "component_pipeline.py")

    def test_001_no_module_writes_a_superseded_name_into_user_data(self):
        offenders = []
        for name in self._MODULES:
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), name)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as handle:
                for number, line in enumerate(handle, 1):
                    if line.lstrip().startswith("#"):
                        continue  # a comment explaining the history is fine
                    for superseded in _SUPERSEDED_NAMES:
                        if superseded in line:
                            offenders.append(f"{name}:{number}: {line.strip()[:80]}")

        self.assertEqual(
            offenders, [],
            "these put a superseded product name where a user can see it:\n  " + "\n  ".join(offenders),
        )

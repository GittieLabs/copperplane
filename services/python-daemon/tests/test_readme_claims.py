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
_TAURI_CONF = os.path.join(_ROOT, "core", "tauri-rust", "tauri.conf.json")

#: Names this product has had. A superseded one in install instructions sends a
#: user looking for an app that is not there.
_SUPERSEDED_NAMES = ["Hardware Agent Studio"]

#: `v1.2.3` in prose. A version in the README is a fact with an expiry date,
#: and this one expired three times before anyone noticed.
_VERSION = re.compile(r"\bv\d+\.\d+\.\d+\b")

#: `[text](target)` where target is not a URL or an anchor.
_RELATIVE_LINK = re.compile(r"\[[^\]]*\]\((?!https?://|#|mailto:)([^)]+)\)")


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
        readme = _readme()
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

"""Every image a documentation page points at has to exist.

Astro serves `public/` verbatim and does not check it, so a page referencing
a deleted image builds green and 404s in the reader's browser. That is how
six screenshots showing the pre-rename product name -- "Hardware Agent
Studio", in the window title bar -- stayed on the site through the rename:
`test_readme_claims.py` guards that string in prose and cannot read a PNG,
and nothing checked the references at all.

Deleting a stale image is the right call. Leaving a page pointing at nothing
is not, and this is what tells the difference.
"""
import os
import re
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_PAGES = os.path.join(_ROOT, "docs", "site", "src", "content", "docs")
_PUBLIC = os.path.join(_ROOT, "docs", "site", "public")

#: Both the markdown form and a raw src attribute, since Starlight pages mix
#: markdown and MDX components.
_IMAGE_REF = re.compile(r"/copperplane/(images/[A-Za-z0-9._-]+)")


def _pages():
    for root, _, files in os.walk(_PAGES):
        for name in files:
            if name.endswith((".md", ".mdx")):
                yield os.path.join(root, name)


@unittest.skipUnless(os.path.isdir(_PAGES), "the docs site is not present")
class DocsImagesTests(unittest.TestCase):
    def test_001_every_referenced_image_exists(self):
        missing = []
        for page in _pages():
            with open(page, encoding="utf-8") as handle:
                text = handle.read()
            for ref in sorted(set(_IMAGE_REF.findall(text))):
                if not os.path.exists(os.path.join(_PUBLIC, ref)):
                    missing.append(f"{os.path.relpath(page, _PAGES)} -> {ref}")

        self.assertEqual(missing, [], "pages pointing at images that are not there:\n  " + "\n  ".join(missing))

    def test_002_the_check_would_notice(self):
        """A check that cannot fail is not evidence."""
        invented = _IMAGE_REF.findall("![x](/copperplane/images/definitely-not-here.png)")

        self.assertEqual(invented, ["images/definitely-not-here.png"])
        self.assertFalse(os.path.exists(os.path.join(_PUBLIC, invented[0])))

    def test_003_no_image_is_left_unused(self):
        """The other direction. An image nobody references is either a
        forgotten reference or dead weight in the published site."""
        referenced = set()
        for page in _pages():
            with open(page, encoding="utf-8") as handle:
                referenced.update(_IMAGE_REF.findall(handle.read()))

        images_dir = os.path.join(_PUBLIC, "images")
        if not os.path.isdir(images_dir):
            self.skipTest("no images directory")
        on_disk = {f"images/{n}" for n in os.listdir(images_dir) if n.endswith(".png")}

        # Reported, not failed: an image can legitimately land before the page
        # that will use it. This names them so they do not simply accumulate.
        unused = sorted(on_disk - referenced)
        if unused:
            print(f"\n  note: {len(unused)} image(s) not referenced by any page yet: {', '.join(unused)}")


_BRAND = os.path.join(_ROOT, "brand")
_SITE = os.path.join(_ROOT, "docs", "site")

#: The pale step Starlight needs for tinted backgrounds. The kit has no light
#: tint, so this one is derived (Copperplane green at 12% into Paper) and is
#: documented as such in custom.css. Everything else must be a kit colour.
_DERIVED_TINTS = {"#d9e7dd"}


@unittest.skipUnless(os.path.isdir(_BRAND), "the brand kit is not present")
class DocsBrandAssetsTests(unittest.TestCase):
    """The site's copies of the mark are copies, not forks.

    `brand/README.md` states the kit is generated and never hand-edited, and
    `brand/` sits outside the Astro project, so Starlight cannot reference it
    directly. Copying is the mechanism; this is what stops a copy going stale
    when the kit is regenerated. Same reasoning as the app's own
    `brandAssets.test.ts`, applied to the second consumer.
    """

    COPIES = {
        os.path.join("src", "assets", "copperplane-mark.svg"): "mark.svg",
        os.path.join("src", "assets", "copperplane-mark-on-dark.svg"): "mark-on-dark.svg",
        os.path.join("public", "favicon.svg"): "favicon.svg",
    }

    def test_101_each_copy_is_byte_identical_to_the_generated_original(self):
        for served, generated in self.COPIES.items():
            with self.subTest(served):
                with open(os.path.join(_SITE, served), "rb") as a, \
                     open(os.path.join(_BRAND, "svg", generated), "rb") as b:
                    self.assertEqual(a.read(), b.read())

    def test_102_the_accents_are_brand_colours_not_approximations(self):
        """The site's accent used to be a soldermask green picked by eye, while
        the kit had one by name. They were not the same colour."""
        with open(os.path.join(_BRAND, "README.md"), encoding="utf-8") as handle:
            palette = {m.lower() for m in re.findall(r"`(#[0-9A-Fa-f]{6})`", handle.read())}
        self.assertGreater(len(palette), 3, "could not read the brand palette")

        with open(os.path.join(_SITE, "src", "styles", "custom.css"), encoding="utf-8") as handle:
            css = handle.read()
        accents = {m.lower() for m in re.findall(r"--sl-color-accent[a-z-]*:\s*(#[0-9a-fA-F]{6})", css)}
        self.assertTrue(accents, "no accent colours found in custom.css")

        stray = sorted(accents - palette - _DERIVED_TINTS)
        self.assertEqual(
            stray, [],
            f"accent colours that are neither in the brand palette nor a documented "
            f"derived tint: {stray}",
        )

    def test_103_the_logo_is_actually_wired_up(self):
        """A copied asset nobody references is just a file."""
        with open(os.path.join(_SITE, "astro.config.mjs"), encoding="utf-8") as handle:
            config = handle.read()

        self.assertIn("copperplane-mark.svg", config)
        self.assertIn("copperplane-mark-on-dark.svg", config)

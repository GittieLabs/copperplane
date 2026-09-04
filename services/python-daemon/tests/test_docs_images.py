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

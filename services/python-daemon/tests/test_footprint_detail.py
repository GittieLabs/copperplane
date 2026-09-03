"""SPEC-334: what a footprint is, read from its own file."""
import glob
import os
import random
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import footprint_detail as fd

_KICAD_FOOTPRINTS = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"


def _write(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".kicad_mod", delete=False)
    handle.write(text)
    handle.close()
    return handle.name


class TestDescribeFootprint(unittest.TestCase):
    def test_001_the_description_is_read_from_the_file(self):
        path = _write('(footprint "x" (descr "Through hole straight pin header, 1x04, 2.54mm pitch"))')
        try:
            out = fd.describe_footprint("Lib:PinHeader_1x04_P2.54mm_Vertical", path)
        finally:
            os.unlink(path)

        self.assertIn("2.54mm pitch", out["description"])

    def test_002_a_datasheet_url_is_lifted_out_of_the_description(self):
        """KiCad's own Battery library puts one there, and a URL glued to the
        end of a sentence reads badly."""
        path = _write('(footprint "x" (descr "Panasonic CR-2032/HFN battery, https://example.com/x.pdf"))')
        try:
            out = fd.describe_footprint("Battery:B", path)
        finally:
            os.unlink(path)

        self.assertEqual(out["datasheet_url"], "https://example.com/x.pdf")
        self.assertNotIn("http", out["description"])
        self.assertIn("Panasonic", out["description"])

    def test_003_mounting_style_is_counted_from_the_pads(self):
        """Through-hole versus surface-mount is the most consequential thing a
        footprint choice decides, and is not always in the name."""
        path = _write('(footprint "x" (pad "1" thru_hole circle) (pad "2" thru_hole circle))')
        try:
            out = fd.describe_footprint("Lib:X", path)
        finally:
            os.unlink(path)

        self.assertEqual(out["pad_count"], 2)
        self.assertIn("through-hole", out["mounting"])

    def test_004_surface_mount_pads_are_named_as_such(self):
        path = _write('(footprint "x" (pad "1" smd rect) (pad "2" smd rect))')
        try:
            out = fd.describe_footprint("Lib:X", path)
        finally:
            os.unlink(path)

        self.assertIn("surface-mount", out["mounting"])

    def test_005_a_missing_file_still_decodes_the_name(self):
        """A personal or community library may carry no descr at all. The
        surface degrades to the naming decoder rather than showing nothing."""
        out = fd.describe_footprint("Lib:PinHeader_1x04_P2.54mm_Vertical", "/nope.kicad_mod")

        self.assertIsNone(out["description"])
        self.assertTrue(out["name_notes"])
        self.assertTrue(any("pitch" in n for n in out["name_notes"]))


class TestNameDecoding(unittest.TestCase):
    """The maintainer's own question: "it's hard to know what P2.54mm_Vertical
    means when to use over P2.00mm_Horizontal"."""

    def _notes(self, name):
        return fd.describe_footprint(f"Lib:{name}", "/nope")["name_notes"]

    def test_001_pitch_is_explained_as_a_physical_distance(self):
        notes = self._notes("PinHeader_1x04_P2.54mm_Vertical")

        self.assertTrue(any("2.54mm" in n and "centre-to-centre" in n for n in notes))
        # And that two pitches are not interchangeable, which is the actual
        # decision the user is making.
        self.assertTrue(any("not" in n and "interchangeable" in n for n in notes))

    def test_002_vertical_is_explained_in_terms_of_the_enclosure(self):
        self.assertTrue(any("height" in n for n in self._notes("PinHeader_1x04_P2.54mm_Vertical")))

    def test_003_horizontal_is_recognised_before_an_underscore(self):
        """`\\b` does not match between "Horizontal" and "_", so this note never
        fired on Battery_..._Horizontal_CircularHoles."""
        notes = self._notes("Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles")

        self.assertTrue(any("lies flat" in n for n in notes))
        self.assertTrue(any("CircularHoles" in n or "round drill" in n for n in notes))

    def test_004_a_single_row_grid_reads_as_english(self):
        """"1x04 means 1 rows of 04" was the first attempt."""
        notes = self._notes("PinHeader_1x04_P2.54mm_Vertical")

        self.assertTrue(any("a single row of 4 pads" in n for n in notes))

    def test_005_a_multi_row_grid_gives_the_total(self):
        notes = self._notes("PinHeader_2x05_P2.00mm_Horizontal")

        self.assertTrue(any("2 rows of 5 pads each, 10 in total" in n for n in notes))

    def test_006_an_unrecognised_name_gets_no_invented_reading(self):
        """SPEC-326 §1's rule: silence beats a confident wrong answer."""
        self.assertEqual(self._notes("SomeVendorPartXYZ"), [])


class TestRealKicadLibraries(unittest.TestCase):
    """Against KiCad's own installed footprints. Skips cleanly elsewhere."""

    def setUp(self):
        if not os.path.isdir(_KICAD_FOOTPRINTS):
            self.skipTest("KiCad's bundled footprints are not on this machine.")

    def test_001_descr_is_populated_broadly_enough_to_rely_on(self):
        """The claim SPEC-334 §2 rests on, re-measured rather than assumed:
        the first draft of that spec called these fields "often empty"."""
        files = glob.glob(os.path.join(_KICAD_FOOTPRINTS, "*.pretty", "*.kicad_mod"))
        random.seed(7)
        sample = random.sample(files, min(200, len(files)))

        with_descr = 0
        for path in sample:
            with open(path, encoding="utf-8", errors="replace") as handle:
                if re.search(r'\(descr\s+"[^"]+"', handle.read(4000)):
                    with_descr += 1

        self.assertGreater(with_descr / len(sample), 0.95)

    def test_002_a_real_pin_header_answers_the_pitch_question(self):
        path = os.path.join(_KICAD_FOOTPRINTS, "Connector_PinHeader_2.54mm.pretty",
                            "PinHeader_1x04_P2.54mm_Vertical.kicad_mod")
        if not os.path.isfile(path):
            self.skipTest("that footprint is not in this KiCad install.")

        out = fd.describe_footprint("Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", path)

        self.assertIn("pitch", out["description"])
        self.assertEqual(out["pad_count"], 4)
        self.assertIn("through-hole", out["mounting"])




class TestUrlDoesNotWreckTheSentence(unittest.TestCase):
    """Found by reading the frozen daemon's real output, not the regex: the
    0805 hand-solder resistor came back ending mid-clause at "page 72"."""

    def test_001_a_url_inside_a_bracket_leaves_the_bracket_closed(self):
        path = _write(
            '(footprint "x" (descr "Resistor SMD 0805, nominal. '
            '(Body size source: IPC-SM-782 page 72, https://example.com/a_1_and_2.pdf)"))'
        )
        try:
            out = fd.describe_footprint("Resistor_SMD:X", path)
        finally:
            os.unlink(path)

        self.assertEqual(out["datasheet_url"], "https://example.com/a_1_and_2.pdf")
        self.assertTrue(out["description"].endswith("page 72)"), out["description"])

    def test_002_a_url_ending_a_sentence_keeps_no_stray_punctuation(self):
        path = _write('(footprint "x" (descr "A part, see https://example.com/x.pdf."))')
        try:
            out = fd.describe_footprint("Lib:X", path)
        finally:
            os.unlink(path)

        self.assertEqual(out["datasheet_url"], "https://example.com/x.pdf")
        self.assertEqual(out["description"], "A part, see.")

    def test_003_a_url_with_its_own_parens_keeps_them(self):
        path = _write('(footprint "x" (descr "See https://en.wikipedia.org/wiki/Foo_(bar) here"))')
        try:
            out = fd.describe_footprint("Lib:X", path)
        finally:
            os.unlink(path)

        self.assertEqual(out["datasheet_url"], "https://en.wikipedia.org/wiki/Foo_(bar)")


class TestEveryRealDescriptionSurvives(unittest.TestCase):
    def setUp(self):
        if not os.path.isdir(_KICAD_FOOTPRINTS):
            self.skipTest("KiCad's bundled footprints are not on this machine.")

    def test_001_no_description_is_left_with_an_unclosed_bracket(self):
        """Across every footprint in KiCad's libraries that carries a URL --
        the only check that would have caught the 0805 defect before shipping."""
        files = glob.glob(os.path.join(_KICAD_FOOTPRINTS, "*.pretty", "*.kicad_mod"))
        random.seed(11)
        checked, mangled = 0, []
        for path in random.sample(files, min(400, len(files))):
            out = fd.describe_footprint("Lib:X", path)
            text = out["description"]
            if not out["datasheet_url"] or not text:
                continue
            checked += 1
            if text.count("(") != text.count(")") or text.rstrip()[-1] in ",;:":
                mangled.append((os.path.basename(path), text[-60:]))

        self.assertGreater(checked, 20, "the sample found too few URLs to prove anything")
        self.assertEqual(mangled, [])


if __name__ == "__main__":
    unittest.main()

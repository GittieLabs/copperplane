import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import check_shotlist as cs

with open(cs.SHOTLIST, encoding='utf-8') as f:
    REAL = json.load(f)


def shot(shotlist, shot_id):
    return next(s for s in shotlist['shots'] if s['id'] == shot_id)


class TestNumbers(unittest.TestCase):

    def test_001_a_number_on_screen_with_more_decimals_still_matches(self):
        self.assertEqual(cs.missing_numbers('Ring: 0.085 mm. Minimum: 0.100 mm.',
                                            'min annular width 0.1000 mm; actual 0.0850 mm'), [])

    def test_002_the_stale_0_15_mm_the_script_once_carried_is_caught(self):
        self.assertEqual(cs.missing_numbers('Minimum: 0.15 mm.', 'min annular width 0.1000 mm'), [0.15])

    def test_003_a_caption_with_no_numbers_has_nothing_missing(self):
        self.assertEqual(cs.missing_numbers('No rule was broken.', ''), [])


class TestBannedPhrases(unittest.TestCase):

    def test_001_just_is_caught_as_a_word(self):
        self.assertEqual(cs.banned_phrases('It just works.'), ['just'])

    def test_002_just_inside_another_word_is_not(self):
        self.assertEqual(cs.banned_phrases('Adjust the pad.'), [])

    def test_003_case_does_not_hide_a_banned_phrase(self):
        self.assertEqual(cs.banned_phrases('Simply open it.'), ['simply'])


class TestCropInside(unittest.TestCase):

    def test_001_a_crop_touching_the_far_edges_is_inside(self):
        self.assertTrue(cs.crop_inside([0, 0, 2560, 1800], 2560, 1800))

    def test_002_one_pixel_past_the_edge_is_not(self):
        self.assertFalse(cs.crop_inside([1, 0, 2560, 1800], 2560, 1800))


class TestTheRealShotlist(unittest.TestCase):
    """The committed shot list must pass its own structural checks."""

    def test_001_the_committed_shotlist_has_no_structural_problems(self):
        self.assertEqual(cs.structural_problems(REAL), [])

    def test_002_every_caption_that_states_a_number_names_a_frame_to_check_it_against(self):
        for s in REAL['shots']:
            for c in s['captions']:
                if cs.numbers_in(c['text']):
                    self.assertIn('verify', c, f"{s['id']}: {c['text']!r}")


class TestStructuralChecksCanFail(unittest.TestCase):
    """Each check, broken on purpose, on a copy of the real shot list."""

    def problems_after(self, mutate):
        shotlist = copy.deepcopy(REAL)
        mutate(shotlist)
        return cs.structural_problems(shotlist)

    def test_001_a_cut_that_no_longer_adds_up(self):
        def mutate(sl):
            shot(sl, 's0-cold-open')['duration']['15'] += 1
        self.assertTrue(any('cut 15' in p for p in self.problems_after(mutate)))

    def test_002_a_caption_too_long_for_a_phone(self):
        def mutate(sl):
            shot(sl, 's8-close')['captions'][0]['text'] = 'Free, open, and it runs entirely on your own machine.'
        self.assertTrue(any('chars' in p for p in self.problems_after(mutate)))

    def test_003_a_number_with_no_frame_to_check_it_against(self):
        def mutate(sl):
            shot(sl, 's5-what-no-check-reports')['captions'][3]['text'] = 'No rule of 3 was broken.'
        self.assertTrue(any('names no frame' in p for p in self.problems_after(mutate)))

    def test_004_a_caption_shown_in_a_cut_its_shot_is_not_in(self):
        def mutate(sl):
            shot(sl, 's6-the-case')['captions'][0]['cuts'].append('15')
        self.assertTrue(any('not in that cut' in p for p in self.problems_after(mutate)))

    def test_005_a_shot_too_short_to_read_its_captions(self):
        def mutate(sl):
            shot(sl, 's5-what-no-check-reports')['duration']['15'] = 2.0
        self.assertTrue(any('to read' in p for p in self.problems_after(mutate)))

    def test_006_a_close_card_url_that_is_not_the_site(self):
        def mutate(sl):
            shot(sl, 's8-close')['card_text'] = ['gittielabs.github.io/hardware-agent-studio']
        self.assertTrue(any('site URL' in p for p in self.problems_after(mutate)))

    def test_008_a_caption_that_shows_a_pullout_that_does_not_exist(self):
        def mutate(sl):
            shot(sl, 's3-it-already-knew')['captions'][1]['shows'] = 4
        self.assertTrue(any('names no pullout' in p for p in self.problems_after(mutate)))

    def test_009_a_caption_that_shows_a_clip_on_a_shot_without_one(self):
        def mutate(sl):
            shot(sl, 's3-it-already-knew')['captions'][1]['shows'] = 'clip'
        self.assertTrue(any('has none' in p for p in self.problems_after(mutate)))

    def test_010_a_continuation_that_does_not_share_its_card(self):
        def mutate(sl):
            shot(sl, 's5-what-no-check-reports')['pullouts'][2]['crop'] = [476, 854, 1738, 400]
        self.assertTrue(any('continues a card' in p for p in self.problems_after(mutate)))

    def test_011_the_morph_belongs_only_to_the_illustration(self):
        def mutate(sl):
            shot(sl, 's3-it-already-knew')['captions'][2]['shows'] = 'morph'
        self.assertTrue(any('only the illustration' in p for p in self.problems_after(mutate)))

    def test_007_a_banned_phrase(self):
        def mutate(sl):
            shot(sl, 's7-whose-machine')['captions'][0]['text'] = 'It just reads your files.'
        self.assertTrue(any('avoid' in p for p in self.problems_after(mutate)))


if __name__ == '__main__':
    unittest.main()

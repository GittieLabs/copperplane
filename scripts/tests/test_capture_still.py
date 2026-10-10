import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import capture_still as cs

BUILD = {'app_bundle': 'x/Copperplane.app', 'core_built_at': '2026-10-10T23:05:00+00:00', 'sidecar_sha1': 'ab' * 20}


def entry(name):
    return cs.manifest_entry(name, f'{name}.png', 'f' * 64, 2560, 1800, BUILD, 'n', '2026-10-10T23:10:00+00:00')


class TestManifestEntry(unittest.TestCase):

    def test_001_records_the_build_that_was_on_screen(self):
        self.assertEqual(entry('seg3-overview')['build']['sidecar_sha1'], 'ab' * 20)

    def test_002_records_pixel_size_because_crop_rectangles_are_in_these_pixels(self):
        self.assertEqual(entry('seg3-overview')['pixels'], [2560, 1800])

    def test_003_a_name_that_is_a_path_is_refused(self):
        with self.assertRaises(cs.CaptureError):
            entry(os.path.join('..', 'escape'))

    def test_004_an_empty_name_is_refused(self):
        with self.assertRaises(cs.CaptureError):
            entry('')


class TestAppendToManifest(unittest.TestCase):

    def test_001_appends_in_order(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'manifest.json')
            cs.append_to_manifest(path, entry('a'))
            cs.append_to_manifest(path, entry('b'))
            with open(path) as f:
                self.assertEqual([e['name'] for e in json.load(f)], ['a', 'b'])

    def test_002_a_duplicate_name_is_refused_and_the_first_capture_survives(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'manifest.json')
            cs.append_to_manifest(path, entry('a'))
            with self.assertRaises(cs.CaptureError):
                cs.append_to_manifest(path, dict(entry('a'), sha256='0' * 64))
            with open(path) as f:
                self.assertEqual(json.load(f)[0]['sha256'], 'f' * 64)


class TestBuildIdentity(unittest.TestCase):

    def test_001_a_missing_bundle_is_a_clean_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(cs.CaptureError) as ctx:
                cs.build_identity(os.path.join(d, 'Copperplane.app'))
            self.assertIn('build it first', str(ctx.exception))

    def test_002_two_builds_with_the_same_version_string_differ_by_sidecar(self):
        with tempfile.TemporaryDirectory() as d:
            ids = []
            for i, payload in enumerate([b'one', b'two']):
                macos = os.path.join(d, str(i), 'Copperplane.app', 'Contents', 'MacOS')
                os.makedirs(macos)
                for exe in ('copperplane-core', 'hardware-agent-studio-daemon'):
                    with open(os.path.join(macos, exe), 'wb') as f:
                        f.write(payload)
                ids.append(cs.build_identity(os.path.dirname(os.path.dirname(macos))))
            self.assertNotEqual(ids[0]['sidecar_sha1'], ids[1]['sidecar_sha1'])


class TestRepoRelative(unittest.TestCase):

    def test_001_a_path_inside_the_repo_is_recorded_relative(self):
        inside = os.path.join(cs.REPO_ROOT, 'core', 'Copperplane.app')
        self.assertEqual(cs.repo_relative(inside), os.path.join('core', 'Copperplane.app'))

    def test_002_a_path_outside_the_repo_is_recorded_absolute_not_as_dot_dot(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(cs.repo_relative(d), os.path.abspath(d))


if __name__ == '__main__':
    unittest.main()

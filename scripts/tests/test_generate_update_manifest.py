import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import generate_update_manifest as gum


class TestPlatformKeyFor(unittest.TestCase):

    def test_001_aarch64_apple_darwin_maps_to_the_real_darwin_aarch64_key(self):
        self.assertEqual(gum.platform_key_for('aarch64-apple-darwin'), 'darwin-aarch64')

    def test_002_x86_64_apple_darwin_maps_to_the_real_darwin_x86_64_key(self):
        self.assertEqual(gum.platform_key_for('x86_64-apple-darwin'), 'darwin-x86_64')

    def test_003_an_unknown_target_triple_raises_a_clean_error_naming_the_known_ones(self):
        with self.assertRaises(gum.UnknownTargetTripleError) as ctx:
            gum.platform_key_for('x86_64-unknown-linux-gnu')
        self.assertIn('aarch64-apple-darwin', str(ctx.exception))


class TestGenerateManifest(unittest.TestCase):

    def test_001_produces_the_real_tauri_updater_manifest_shape(self):
        manifest = gum.generate_manifest(
            version='v0.1.0',
            pub_date='2026-08-16T21:00:00Z',
            notes='### CTX-999.1: Fixture\n\nreal notes',
            target_triple='aarch64-apple-darwin',
            signature='dW50cnVzdGVkIGNvbW1lbnQ6...',
            download_url='https://github.com/GittieLabs/hardware-agent-studio/releases/download/v0.1.0/hardware-agent-studio.app.tar.gz',
        )

        self.assertEqual(manifest['version'], 'v0.1.0')
        self.assertEqual(manifest['pub_date'], '2026-08-16T21:00:00Z')
        self.assertIn('real notes', manifest['notes'])
        self.assertEqual(
            manifest['platforms']['darwin-aarch64'],
            {
                'signature': 'dW50cnVzdGVkIGNvbW1lbnQ6...',
                'url': 'https://github.com/GittieLabs/hardware-agent-studio/releases/download/v0.1.0/hardware-agent-studio.app.tar.gz',
            },
        )

    def test_002_exactly_one_platform_key_is_present_a_real_named_limitation_not_a_bug(self):
        """This pipeline only ever builds the CI runner's single native
        macOS architecture (CTX-401.2's own established scope) -- the
        manifest must carry exactly one platform entry, not silently
        fabricate a second one for an architecture never actually built."""
        manifest = gum.generate_manifest(
            'v0.1.0', '2026-08-16T21:00:00Z', 'notes', 'x86_64-apple-darwin', 'sig', 'url',
        )
        self.assertEqual(len(manifest['platforms']), 1)

    def test_003_an_unknown_target_triple_propagates_the_real_error(self):
        with self.assertRaises(gum.UnknownTargetTripleError):
            gum.generate_manifest('v0.1.0', '2026-08-16T21:00:00Z', 'notes', 'unknown-triple', 'sig', 'url')


if __name__ == '__main__':
    unittest.main()

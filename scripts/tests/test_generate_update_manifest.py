import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import generate_update_manifest as gum


class TestPlatformKeyFor(unittest.TestCase):

    def test_001_aarch64_apple_darwin_maps_to_the_real_darwin_aarch64_key(self):
        self.assertEqual(gum.platform_key_for('aarch64-apple-darwin'), 'darwin-aarch64')

    def test_002_x86_64_apple_darwin_maps_to_the_real_darwin_x86_64_key(self):
        self.assertEqual(gum.platform_key_for('x86_64-apple-darwin'), 'darwin-x86_64')

    def test_003_x86_64_pc_windows_msvc_maps_to_the_real_windows_x86_64_key(self):
        self.assertEqual(gum.platform_key_for('x86_64-pc-windows-msvc'), 'windows-x86_64')

    def test_004_x86_64_unknown_linux_gnu_maps_to_the_real_linux_x86_64_key(self):
        self.assertEqual(gum.platform_key_for('x86_64-unknown-linux-gnu'), 'linux-x86_64')

    def test_005_an_unknown_target_triple_raises_a_clean_error_naming_the_known_ones(self):
        with self.assertRaises(gum.UnknownTargetTripleError) as ctx:
            gum.platform_key_for('aarch64-unknown-linux-gnu')
        self.assertIn('aarch64-apple-darwin', str(ctx.exception))


class TestGenerateManifest(unittest.TestCase):

    def test_001_produces_the_real_tauri_updater_manifest_shape(self):
        manifest = gum.generate_manifest(
            version='v0.1.0',
            pub_date='2026-08-16T21:00:00Z',
            notes='### CTX-999.1: Fixture\n\nreal notes',
            platforms=[(
                'aarch64-apple-darwin',
                'dW50cnVzdGVkIGNvbW1lbnQ6...',
                'https://github.com/GittieLabs/copperplane/releases/download/v0.1.0/Copperplane.app.tar.gz',
            )],
        )

        self.assertEqual(manifest['version'], 'v0.1.0')
        self.assertEqual(manifest['pub_date'], '2026-08-16T21:00:00Z')
        self.assertIn('real notes', manifest['notes'])
        self.assertEqual(
            manifest['platforms']['darwin-aarch64'],
            {
                'signature': 'dW50cnVzdGVkIGNvbW1lbnQ6...',
                'url': 'https://github.com/GittieLabs/copperplane/releases/download/v0.1.0/Copperplane.app.tar.gz',
            },
        )

    def test_002_a_single_platform_produces_exactly_one_platform_key(self):
        manifest = gum.generate_manifest(
            'v0.1.0', '2026-08-16T21:00:00Z', 'notes',
            [('x86_64-apple-darwin', 'sig', 'url')],
        )
        self.assertEqual(len(manifest['platforms']), 1)

    def test_003_an_unknown_target_triple_propagates_the_real_error(self):
        with self.assertRaises(gum.UnknownTargetTripleError):
            gum.generate_manifest('v0.1.0', '2026-08-16T21:00:00Z', 'notes', [('unknown-triple', 'sig', 'url')])

    def test_004_real_two_architecture_manifest_carries_both_platform_keys(self):
        """CTX-402.4: a real matrix build produces both a real Apple
        Silicon and a real Intel artifact in the same release -- the
        manifest must carry both, not just whichever was built first."""
        manifest = gum.generate_manifest(
            'v0.1.1', '2026-08-17T21:00:00Z', 'notes',
            [
                ('aarch64-apple-darwin', 'sig-arm', 'url-arm'),
                ('x86_64-apple-darwin', 'sig-x86', 'url-x86'),
            ],
        )
        self.assertEqual(len(manifest['platforms']), 2)
        self.assertEqual(manifest['platforms']['darwin-aarch64'], {'signature': 'sig-arm', 'url': 'url-arm'})
        self.assertEqual(manifest['platforms']['darwin-x86_64'], {'signature': 'sig-x86', 'url': 'url-x86'})

    def test_005_real_four_platform_manifest_carries_all_four_keys(self):
        """CTX-402.5: a real release now carries two macOS architectures
        plus real, unsigned pre-release Windows and Linux builds -- all
        four must appear, each under its own real platform key."""
        manifest = gum.generate_manifest(
            'v0.1.3', '2026-08-18T21:00:00Z', 'notes',
            [
                ('aarch64-apple-darwin', 'sig-arm', 'url-arm'),
                ('x86_64-apple-darwin', 'sig-x86-mac', 'url-x86-mac'),
                ('x86_64-pc-windows-msvc', 'sig-win', 'url-win'),
                ('x86_64-unknown-linux-gnu', 'sig-linux', 'url-linux'),
            ],
        )
        self.assertEqual(len(manifest['platforms']), 4)
        self.assertEqual(manifest['platforms']['windows-x86_64'], {'signature': 'sig-win', 'url': 'url-win'})
        self.assertEqual(manifest['platforms']['linux-x86_64'], {'signature': 'sig-linux', 'url': 'url-linux'})


class TestCliInvocation(unittest.TestCase):

    def test_001_real_cli_invocation_with_two_repeated_platform_flags(self):
        """End-to-end reproduction of how release.yml's real publish job
        invokes this script post-CTX-402.4: two --platform groups, one
        real matrix leg each."""
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'generate_update_manifest.py'))
        with tempfile.TemporaryDirectory() as tmpdir:
            notes_path = os.path.join(tmpdir, 'notes.md')
            arm_sig_path = os.path.join(tmpdir, 'arm.sig')
            x86_sig_path = os.path.join(tmpdir, 'x86.sig')
            with open(notes_path, 'w', encoding='utf-8') as f:
                f.write('real release notes')
            with open(arm_sig_path, 'w', encoding='utf-8') as f:
                f.write('arm-signature\n')
            with open(x86_sig_path, 'w', encoding='utf-8') as f:
                f.write('x86-signature\n')

            result = subprocess.run(
                [
                    sys.executable, script,
                    '--version', 'v0.1.1',
                    '--pub-date', '2026-08-17T21:00:00Z',
                    '--notes-file', notes_path,
                    '--platform', 'aarch64-apple-darwin', arm_sig_path, 'https://example.com/arm.app.tar.gz',
                    '--platform', 'x86_64-apple-darwin', x86_sig_path, 'https://example.com/x86.app.tar.gz',
                ],
                capture_output=True, text=True, check=True,
            )

        manifest = json.loads(result.stdout)
        self.assertEqual(len(manifest['platforms']), 2)
        self.assertEqual(manifest['platforms']['darwin-aarch64']['signature'], 'arm-signature')
        self.assertEqual(manifest['platforms']['darwin-x86_64']['signature'], 'x86-signature')


if __name__ == '__main__':
    unittest.main()

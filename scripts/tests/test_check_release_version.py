import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import check_release_version as crv


class _FixtureTestCase(unittest.TestCase):
    """Real, throwaway temp files -- never this repo's own real
    Cargo.toml/tauri.conf.json, so a broken fixture can never accidentally
    corrupt real project state."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        os.makedirs('core/tauri-rust', exist_ok=True)

    def tearDown(self):
        os.chdir(self.orig_cwd)

    def write_cargo_toml(self, version):
        with open('core/tauri-rust/Cargo.toml', 'w', encoding='utf-8') as f:
            f.write(f'[package]\nname = "hardware-agent-studio-core"\nversion = "{version}"\n')

    def write_tauri_conf(self, version):
        with open('core/tauri-rust/tauri.conf.json', 'w', encoding='utf-8') as f:
            json.dump({"productName": "hardware-agent-studio", "version": version}, f)


class TestCargoTomlVersion(_FixtureTestCase):

    def test_001_extracts_the_real_version_string(self):
        self.write_cargo_toml('0.1.0')
        self.assertEqual(crv.cargo_toml_version(), '0.1.0')

    def test_002_a_missing_version_line_raises_a_clean_error(self):
        with open('core/tauri-rust/Cargo.toml', 'w', encoding='utf-8') as f:
            f.write('[package]\nname = "x"\n')
        with self.assertRaises(crv.VersionMismatchError):
            crv.cargo_toml_version()


class TestTauriConfVersion(_FixtureTestCase):

    def test_001_extracts_the_real_version_field(self):
        self.write_tauri_conf('0.1.0')
        self.assertEqual(crv.tauri_conf_version(), '0.1.0')

    def test_002_a_missing_version_field_raises_a_clean_error(self):
        with open('core/tauri-rust/tauri.conf.json', 'w', encoding='utf-8') as f:
            json.dump({"productName": "x"}, f)
        with self.assertRaises(crv.VersionMismatchError):
            crv.tauri_conf_version()


class TestCheckTagMatches(_FixtureTestCase):

    def test_001_a_matching_v_prefixed_tag_passes_silently(self):
        self.write_cargo_toml('0.2.0')
        self.write_tauri_conf('0.2.0')
        crv.check_tag_matches('v0.2.0')  # must not raise

    def test_002_a_cargo_toml_mismatch_names_cargo_toml_specifically(self):
        self.write_cargo_toml('0.1.0')
        self.write_tauri_conf('0.2.0')
        with self.assertRaises(crv.VersionMismatchError) as ctx:
            crv.check_tag_matches('v0.2.0')
        self.assertIn("Cargo.toml has '0.1.0'", str(ctx.exception))

    def test_003_a_tauri_conf_mismatch_names_tauri_conf_specifically(self):
        self.write_cargo_toml('0.2.0')
        self.write_tauri_conf('0.1.0')
        with self.assertRaises(crv.VersionMismatchError) as ctx:
            crv.check_tag_matches('v0.2.0')
        self.assertIn("tauri.conf.json has '0.1.0'", str(ctx.exception))

    def test_004_both_mismatched_names_both_in_one_error(self):
        self.write_cargo_toml('0.1.0')
        self.write_tauri_conf('0.1.5')
        with self.assertRaises(crv.VersionMismatchError) as ctx:
            crv.check_tag_matches('v0.2.0')
        message = str(ctx.exception)
        self.assertIn("Cargo.toml has '0.1.0'", message)
        self.assertIn("tauri.conf.json has '0.1.5'", message)

    def test_005_a_tag_without_the_v_prefix_is_accepted_too(self):
        self.write_cargo_toml('0.3.0')
        self.write_tauri_conf('0.3.0')
        crv.check_tag_matches('0.3.0')  # must not raise


class TestAgainstThisRepoForReal(unittest.TestCase):
    """CLAUDE.md's 'verify against the real thing' norm: this repo's own
    real Cargo.toml/tauri.conf.json, from the real repo root, not a
    fixture -- proves the parser actually works on the real files it will
    run against in CI, not just a hand-crafted stand-in."""

    def test_001_this_repos_own_real_versions_are_parseable_and_currently_match(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        orig_cwd = os.getcwd()
        os.chdir(repo_root)
        try:
            cargo_version = crv.cargo_toml_version()
            tauri_version = crv.tauri_conf_version()
            self.assertRegex(cargo_version, r'^\d+\.\d+\.\d+$')
            self.assertEqual(cargo_version, tauri_version)
            crv.check_tag_matches(f'v{cargo_version}')  # must not raise
        finally:
            os.chdir(orig_cwd)


if __name__ == '__main__':
    unittest.main()

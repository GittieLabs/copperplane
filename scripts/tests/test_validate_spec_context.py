import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import validate_spec_context as vsc


class TestPathExclusionMatcher(unittest.TestCase):
    """TEST-001: the path matcher correctly exempts README/lockfiles/nested
    specs-context dirs, and still flags ordinary code files."""

    def test_001_root_and_module_readmes_are_excluded(self):
        self.assertTrue(vsc.is_excluded_from_code('README.md'))
        self.assertTrue(vsc.is_excluded_from_code('services/python-daemon/README.md'))

    def test_002_lockfiles_are_excluded_regardless_of_directory(self):
        self.assertTrue(vsc.is_excluded_from_code('apps/tauri-ui/package-lock.json'))
        self.assertTrue(vsc.is_excluded_from_code('core/tauri-rust/Cargo.lock'))

    def test_003_nested_specs_and_context_dirs_are_excluded(self):
        self.assertTrue(vsc.is_excluded_from_code('services/python-daemon/specs/SPEC-902.md'))
        self.assertTrue(vsc.is_excluded_from_code('services/python-daemon/context/CTX-902.1.md'))

    def test_004_root_license_is_excluded(self):
        self.assertTrue(vsc.is_excluded_from_code('LICENSE'))

    def test_005_ordinary_code_files_are_not_excluded(self):
        self.assertFalse(vsc.is_excluded_from_code('services/python-daemon/daemon.py'))
        self.assertFalse(vsc.is_excluded_from_code('apps/tauri-ui/src/App.tsx'))
        # A non-lockfile .json config is still code-like and must NOT be exempted.
        self.assertFalse(vsc.is_excluded_from_code('core/tauri-rust/tauri.conf.json'))


class SpecGraphFixtureTestCase(unittest.TestCase):
    """Base class: builds fixture SPEC-*.md files in a throwaway temp
    directory and runs validate_spec_graph() against it via chdir, never
    against this repo's own real specs/context trees."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write_spec(self, relpath, spec_id, location=None, parent_spec=None, child_specs=None):
        full = os.path.join(self.tmpdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        lines = [
            '---',
            f'id: {spec_id}',
            'title: "Test Spec"',
            'status: Draft',
            f'location: "{location if location is not None else relpath}"',
        ]
        lines.append(f'parent_spec: "{parent_spec}"' if parent_spec else 'parent_spec: null')
        lines.append('child_specs:')
        for c in (child_specs or []):
            lines.append(f'  - "{c}"')
        if not child_specs:
            lines[-1] = 'child_specs: []'
        lines += ['---', f'# {spec_id}']
        with open(full, 'w') as f:
            f.write('\n'.join(lines) + '\n')


class TestSpecGraphHardFailures(SpecGraphFixtureTestCase):
    """TEST-002/TEST-003: dangling links, id collisions, id/filename and
    location mismatches, and one-directional links are all detected."""

    def test_001_dangling_parent_spec_detected(self):
        self.write_spec('specs/SPEC-100-child.md', 'SPEC-100', parent_spec='SPEC-999-nonexistent.md')
        errors, _info = vsc.validate_spec_graph()
        self.assertTrue(any('DANGLING parent_spec' in e for e in errors), errors)

    def test_002_dangling_child_specs_entry_detected(self):
        self.write_spec('specs/SPEC-100-parent.md', 'SPEC-100', child_specs=['SPEC-999-nonexistent.md'])
        errors, _info = vsc.validate_spec_graph()
        self.assertTrue(any('DANGLING child_specs entry' in e for e in errors), errors)

    def test_003_duplicate_id_detected(self):
        self.write_spec('specs/SPEC-100-a.md', 'SPEC-100')
        self.write_spec('specs/SPEC-100-b.md', 'SPEC-100')
        errors, _info = vsc.validate_spec_graph()
        self.assertTrue(any('DUPLICATE SPEC ID' in e for e in errors), errors)

    def test_004_id_filename_mismatch_detected(self):
        self.write_spec('specs/SPEC-999-wrong-name.md', 'SPEC-100')
        errors, _info = vsc.validate_spec_graph()
        self.assertTrue(any('ID/FILENAME MISMATCH' in e for e in errors), errors)

    def test_005_location_mismatch_detected(self):
        self.write_spec('specs/SPEC-100-x.md', 'SPEC-100', location='specs/SPEC-WRONG-PATH.md')
        errors, _info = vsc.validate_spec_graph()
        self.assertTrue(any('LOCATION MISMATCH' in e for e in errors), errors)

    def test_006_one_directional_link_detected(self):
        # Child points to parent, but parent's child_specs doesn't list it back.
        self.write_spec('specs/SPEC-100-parent.md', 'SPEC-100', child_specs=[])
        self.write_spec('specs/SPEC-101-child.md', 'SPEC-101', parent_spec='SPEC-100-parent.md')
        errors, _info = vsc.validate_spec_graph()
        self.assertTrue(any('ONE-DIRECTIONAL LINK' in e for e in errors), errors)

    def test_007_bidirectional_link_is_clean(self):
        self.write_spec('specs/SPEC-100-parent.md', 'SPEC-100', child_specs=['SPEC-101-child.md'])
        self.write_spec('specs/SPEC-101-child.md', 'SPEC-101', parent_spec='SPEC-100-parent.md')
        errors, _info = vsc.validate_spec_graph()
        link_errors = [e for e in errors if 'ONE-DIRECTIONAL' in e or 'DANGLING' in e]
        self.assertEqual([], link_errors)


class TestSpecGraphInformationalFindings(SpecGraphFixtureTestCase):
    """TEST-004: 'no context yet' and 'orphan root spec' are informational
    only -- they must never appear in the hard-error list."""

    def test_001_no_context_is_informational_not_an_error(self):
        self.write_spec('specs/SPEC-100-solo.md', 'SPEC-100')
        errors, info = vsc.validate_spec_graph()
        self.assertTrue(any('NO CONTEXT YET' in n for n in info), info)
        self.assertFalse(any('NO CONTEXT' in e for e in errors))

    def test_002_known_parentless_spec_does_not_trigger_orphan_note(self):
        self.write_spec('specs/SPEC-901-agent-operating-manual.md', 'SPEC-901')
        _errors, info = vsc.validate_spec_graph()
        self.assertFalse(any('ORPHAN ROOT SPEC' in n for n in info), info)

    def test_003_unrecognized_parentless_spec_triggers_orphan_note(self):
        self.write_spec('specs/SPEC-500-standalone.md', 'SPEC-500')
        _errors, info = vsc.validate_spec_graph()
        self.assertTrue(any('ORPHAN ROOT SPEC' in n for n in info), info)


class TestEndToEndCLI(unittest.TestCase):
    """TEST-005: the real CLI, invoked via subprocess against a real
    temporary git repo with a real commit history -- not a helper
    function's return value."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'validate_spec_context.py')
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _git(self, *args):
        subprocess.run(['git', *args], cwd=self.tmpdir, check=True, capture_output=True, text=True)

    def _write(self, relpath, content):
        full = os.path.join(self.tmpdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w') as f:
            f.write(content)

    def test_001_real_cli_detects_dangling_parent_spec(self):
        self._git('init', '-q')
        self._git('config', 'user.email', 'test@example.com')
        self._git('config', 'user.name', 'Test')

        self._write(
            'specs/SPEC-100-base.md',
            '---\nid: SPEC-100\ntitle: "Base"\nstatus: Draft\n'
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n---\n# base\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'base')
        self._git('branch', '-q', '-m', 'develop')

        self._git('checkout', '-q', '-b', 'feature')
        self._write(
            'specs/SPEC-101-child.md',
            '---\nid: SPEC-101\ntitle: "Child"\nstatus: Draft\n'
            'location: "specs/SPEC-101-child.md"\n'
            'parent_spec: "SPEC-999-nonexistent.md"\nchild_specs: []\n---\n# child\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'add child with dangling parent')

        result = subprocess.run(
            [sys.executable, self.script_path, '--base', 'develop'],
            cwd=self.tmpdir, capture_output=True, text=True,
        )
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn('DANGLING parent_spec', result.stdout)

    def test_002_real_cli_passes_on_a_clean_graph(self):
        self._git('init', '-q')
        self._git('config', 'user.email', 'test@example.com')
        self._git('config', 'user.name', 'Test')

        self._write(
            'specs/SPEC-100-base.md',
            '---\nid: SPEC-100\ntitle: "Base"\nstatus: Draft\n'
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n---\n# base\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'base')
        self._git('branch', '-q', '-m', 'develop')

        self._git('checkout', '-q', '-b', 'feature')
        self._write('README.md', '# untouched\n')
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'unrelated docs change')

        result = subprocess.run(
            [sys.executable, self.script_path, '--base', 'develop'],
            cwd=self.tmpdir, capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_003_real_cli_detects_dangling_ctx_spec_ref(self):
        # Exercises the CTX-level spec_ref check specifically -- distinct
        # from test_001, which exercises the SPEC-level parent_spec check.
        # Before SPEC-902, spec_ref was only checked for presence, never
        # that its path actually resolves.
        self._git('init', '-q')
        self._git('config', 'user.email', 'test@example.com')
        self._git('config', 'user.name', 'Test')

        self._write(
            'specs/SPEC-100-base.md',
            '---\nid: SPEC-100\ntitle: "Base"\nstatus: Draft\n'
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n---\n# base\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'base')
        self._git('branch', '-q', '-m', 'develop')

        self._git('checkout', '-q', '-b', 'feature')
        self._write('daemon.py', 'x = 1\n')  # trip the code_changed check too
        self._write(
            'context/CTX-100.1-base.md',
            '---\nid: CTX-100.1\nspec_ref: "../specs/SPEC-999-nonexistent.md"\ntitle: "x"\n'
            'status: Planned\nbranch: "feat/CTX-100.1-x"\ncommit_hashes:\n  - "abc123 - x"\n'
            '---\n# CTX-100.1\n\n## 2. Testing Requirements Matrix\n\n'
            '| Test ID | Test Description | Test File Location | Status |\n'
            '| :--- | :--- | :--- | :--- |\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'add ctx with dangling spec_ref')

        result = subprocess.run(
            [sys.executable, self.script_path, '--base', 'develop'],
            cwd=self.tmpdir, capture_output=True, text=True,
        )
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn('DANGLING spec_ref', result.stdout)


class TestAgainstRealRepo(unittest.TestCase):
    """TEST-006: the upgraded validator, run against this repo's own real,
    current SPEC-*.md/CTX-*.md state, must report zero hard errors -- this
    is the check that would otherwise break every future PR's gatekeeper
    run."""

    def test_001_real_repo_graph_has_no_hard_errors(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        orig_cwd = os.getcwd()
        os.chdir(repo_root)
        try:
            errors, _info = vsc.validate_spec_graph()
        finally:
            os.chdir(orig_cwd)
        self.assertEqual([], errors, f"Real repo graph has hard errors: {errors}")


if __name__ == '__main__':
    unittest.main()

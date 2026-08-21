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

    def write_spec(self, relpath, spec_id, location=None, parent_spec=None, child_specs=None,
                    user_facing=False):
        full = os.path.join(self.tmpdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        lines = [
            '---',
            f'id: {spec_id}',
            'title: "Test Spec"',
            'status: Draft',
            f'location: "{location if location is not None else relpath}"',
            f'user_facing: {"true" if user_facing else "false"}',
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


class TestUserFacingFieldRequired(SpecGraphFixtureTestCase):
    """CTX-901.2 TEST-007: user_facing missing entirely is a repo-wide hard
    error, checked the same way as id/title/status/location already are."""

    def test_001_missing_user_facing_field_is_a_hard_error(self):
        full = os.path.join(self.tmpdir, 'specs/SPEC-100-x.md')
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w') as f:
            f.write(
                '---\nid: SPEC-100\ntitle: "X"\nstatus: Draft\n'
                'location: "specs/SPEC-100-x.md"\nparent_spec: null\nchild_specs: []\n'
                '---\n# SPEC-100\n'
            )
        errors, _info = vsc.validate_spec_graph()
        self.assertTrue(
            any('MISSING SPEC FRONTMATTER FIELD' in e and 'user_facing' in e for e in errors),
            errors,
        )

    def test_002_explicit_false_is_not_flagged(self):
        self.write_spec('specs/SPEC-100-x.md', 'SPEC-100', user_facing=False)
        errors, _info = vsc.validate_spec_graph()
        self.assertFalse(any('user_facing' in e for e in errors), errors)


class TestUserFacingSectionCheck(SpecGraphFixtureTestCase):
    """CTX-901.2 TEST-007: a SPEC-*.md declaring user_facing: true must have
    a '## 5. User & Interaction' section -- structural presence only, so a
    TODO-marked stub (the backfill pattern used for SPEC-301/302/108) still
    passes without inventing real content."""

    def _write_raw(self, relpath, content):
        full = os.path.join(self.tmpdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w') as f:
            f.write(content)

    def test_001_user_facing_true_without_section_is_flagged(self):
        self._write_raw(
            'specs/SPEC-100-x.md',
            '---\nid: SPEC-100\ntitle: "X"\nstatus: Draft\n'
            'location: "specs/SPEC-100-x.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: true\n---\n# SPEC-100\n\n## 1. Executive Summary & Goals\n',
        )
        errors = vsc.validate_user_facing_section('specs/SPEC-100-x.md')
        self.assertTrue(any('MISSING USER & INTERACTION SECTION' in e for e in errors), errors)

    def test_002_user_facing_true_with_real_section_passes(self):
        self._write_raw(
            'specs/SPEC-100-x.md',
            '---\nid: SPEC-100\ntitle: "X"\nstatus: Draft\n'
            'location: "specs/SPEC-100-x.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: true\n---\n# SPEC-100\n\n## 5. User & Interaction\n* real content\n',
        )
        errors = vsc.validate_user_facing_section('specs/SPEC-100-x.md')
        self.assertEqual([], errors)

    def test_003_todo_stub_section_still_passes_structural_check(self):
        self._write_raw(
            'specs/SPEC-100-x.md',
            '---\nid: SPEC-100\ntitle: "X"\nstatus: Draft\n'
            'location: "specs/SPEC-100-x.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: true\n---\n# SPEC-100\n\n## 5. User & Interaction\n*TODO*\n',
        )
        errors = vsc.validate_user_facing_section('specs/SPEC-100-x.md')
        self.assertEqual([], errors)

    def test_004_user_facing_false_without_section_is_not_flagged(self):
        self._write_raw(
            'specs/SPEC-100-x.md',
            '---\nid: SPEC-100\ntitle: "X"\nstatus: Draft\n'
            'location: "specs/SPEC-100-x.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: false\n---\n# SPEC-100\n',
        )
        errors = vsc.validate_user_facing_section('specs/SPEC-100-x.md')
        self.assertEqual([], errors)


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
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: false\n---\n# base\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'base')
        self._git('branch', '-q', '-m', 'develop')

        self._git('checkout', '-q', '-b', 'feature')
        self._write(
            'specs/SPEC-101-child.md',
            '---\nid: SPEC-101\ntitle: "Child"\nstatus: Draft\n'
            'location: "specs/SPEC-101-child.md"\n'
            'parent_spec: "SPEC-999-nonexistent.md"\nchild_specs: []\n'
            'user_facing: false\n---\n# child\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'add child with dangling parent')

        result = subprocess.run(
            [sys.executable, self.script_path, '--base', 'develop'],
            cwd=self.tmpdir, capture_output=True, text=True, encoding='utf-8',
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
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: false\n---\n# base\n',
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
            cwd=self.tmpdir, capture_output=True, text=True, encoding='utf-8',
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
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: false\n---\n# base\n',
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
            cwd=self.tmpdir, capture_output=True, text=True, encoding='utf-8',
        )
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn('DANGLING spec_ref', result.stdout)


    def test_004_real_cli_flags_a_changed_user_facing_spec_missing_section(self):
        self._git('init', '-q')
        self._git('config', 'user.email', 'test@example.com')
        self._git('config', 'user.name', 'Test')

        self._write(
            'specs/SPEC-100-base.md',
            '---\nid: SPEC-100\ntitle: "Base"\nstatus: Draft\n'
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: false\n---\n# base\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'base')
        self._git('branch', '-q', '-m', 'develop')

        self._git('checkout', '-q', '-b', 'feature')
        self._write(
            'specs/SPEC-100-base.md',
            '---\nid: SPEC-100\ntitle: "Base"\nstatus: Draft\n'
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: true\n---\n# base\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'flip to user-facing without adding the section')

        result = subprocess.run(
            [sys.executable, self.script_path, '--base', 'develop'],
            cwd=self.tmpdir, capture_output=True, text=True, encoding='utf-8',
        )
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn('MISSING USER & INTERACTION SECTION', result.stdout)

    def test_005_real_cli_does_not_flag_an_untouched_user_facing_spec(self):
        # RULE 5 is changed-files-only, unlike RULE 4's repo-wide graph
        # checks -- a pre-existing user_facing:true spec missing the
        # section must not fail a PR that never touches it (CTX-901.2's
        # backfill pattern for SPEC-301/302/108 relies on this).
        self._git('init', '-q')
        self._git('config', 'user.email', 'test@example.com')
        self._git('config', 'user.name', 'Test')

        self._write(
            'specs/SPEC-100-base.md',
            '---\nid: SPEC-100\ntitle: "Base"\nstatus: Draft\n'
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: true\n---\n# base\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'base, already user_facing, no section (pre-existing debt)')
        self._git('branch', '-q', '-m', 'develop')

        self._git('checkout', '-q', '-b', 'feature')
        self._write('README.md', '# unrelated\n')
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'unrelated docs change')

        result = subprocess.run(
            [sys.executable, self.script_path, '--base', 'develop'],
            cwd=self.tmpdir, capture_output=True, text=True, encoding='utf-8',
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class TestCommitHashesAreReal(unittest.TestCase):
    """A real bug found and fixed across ten of this repo's own context
    files: a commit_hashes entry can look entirely valid (correct hex
    format, matches this repo's own "<hash> - <description>"
    convention) while referring to a commit that was never actually
    pushed -- the real, concrete cause being `git commit --amend` used
    to fold the hash into the very commit it describes, which discards
    the original pre-amend commit. These tests reproduce that exact
    real mechanism (commit, then amend), not a synthetic fake hash --
    the same real CLI-via-subprocess pattern TestEndToEndCLI already
    established for this file's other checks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'validate_spec_context.py')
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _git(self, *args):
        subprocess.run(['git', *args], cwd=self.tmpdir, check=True, capture_output=True, text=True)

    def _git_hash(self, *args):
        result = subprocess.run(
            ['git', *args], cwd=self.tmpdir, check=True, capture_output=True, text=True,
        )
        return result.stdout.strip()

    def _write(self, relpath, content):
        full = os.path.join(self.tmpdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w') as f:
            f.write(content)

    def _ctx_fixture(self, commit_hashes_yaml):
        return (
            '---\nid: CTX-100.1\nspec_ref: "../specs/SPEC-100-base.md"\ntitle: "x"\n'
            f'status: Planned\nbranch: "feat/CTX-100.1-x"\n{commit_hashes_yaml}\n'
            '---\n# CTX-100.1\n\n## 2. Testing Requirements Matrix\n\n'
            '| Test ID | Test Description | Test File Location | Status |\n'
            '| :--- | :--- | :--- | :--- |\n'
        )

    def _run_validator(self):
        return subprocess.run(
            [sys.executable, self.script_path, '--base', 'develop'],
            cwd=self.tmpdir, capture_output=True, text=True, encoding='utf-8',
        )

    def _init_base(self):
        self._git('init', '-q')
        self._git('config', 'user.email', 'test@example.com')
        self._git('config', 'user.name', 'Test')
        self._write(
            'specs/SPEC-100-base.md',
            '---\nid: SPEC-100\ntitle: "Base"\nstatus: Draft\n'
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: false\n---\n# base\n',
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'base')
        self._git('branch', '-q', '-m', 'develop')
        self._git('checkout', '-q', '-b', 'feature')

    def test_001_real_cli_detects_a_hash_discarded_by_git_commit_amend(self):
        # The exact real mechanism, not a synthetic fake hash: commit,
        # capture that real commit's own hash, record it in the
        # context file, then amend -- which rewrites the commit to a
        # new hash and discards the one just recorded, before it's
        # ever pushed.
        self._init_base()
        self._write('daemon.py', 'x = 1\n')
        self._write('context/CTX-100.1-base.md', self._ctx_fixture('commit_hashes:\n  - "placeholder"'))
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'add feature')
        real_hash = self._git_hash('rev-parse', 'HEAD')

        self._write(
            'context/CTX-100.1-base.md',
            self._ctx_fixture(f'commit_hashes:\n  - "{real_hash} - add feature"'),
        )
        self._git('add', '.')
        self._git('commit', '-q', '--amend', '-m', 'add feature (amended)')

        result = self._run_validator()

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn('DANGLING COMMIT HASH', result.stdout)
        self.assertIn(real_hash, result.stdout)

    def test_002_real_cli_passes_when_the_recorded_hash_is_real_and_reachable(self):
        # The real, correct close-context flow this repo's own
        # convention describes: an implementation commit, then a
        # separate commit recording that real, already-pushed commit's
        # own hash -- never amended, so the recorded hash stays real.
        self._init_base()
        self._write('daemon.py', 'x = 1\n')
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'add feature')
        real_hash = self._git_hash('rev-parse', 'HEAD')

        self._write(
            'context/CTX-100.1-base.md',
            self._ctx_fixture(f'commit_hashes:\n  - "{real_hash} - add feature"'),
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'record commit hash')

        result = self._run_validator()

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_003_real_cli_does_not_reflag_an_old_unchanged_hash_it_cannot_verify(self):
        # This repo's own established, legitimate convention (e.g.
        # CTX-315.2's own precedent): an older, already-merged context
        # file can cite a real commit from a since-deleted feature
        # branch that is genuinely not fetchable in an unrelated,
        # later PR's own scoped checkout -- through no fault of its
        # own. A PR that edits the file for an unrelated reason,
        # without touching commit_hashes, must not be blocked by a
        # hash it was never asked to re-verify.
        self._git('init', '-q')
        self._git('config', 'user.email', 'test@example.com')
        self._git('config', 'user.name', 'Test')
        self._write(
            'specs/SPEC-100-base.md',
            '---\nid: SPEC-100\ntitle: "Base"\nstatus: Draft\n'
            'location: "specs/SPEC-100-base.md"\nparent_spec: null\nchild_specs: []\n'
            'user_facing: false\n---\n# base\n',
        )
        old_hash = 'deadbeef00112233445566778899aabbccddeef'  # well-formed, never a real object here
        self._write(
            'context/CTX-100.1-base.md',
            self._ctx_fixture(f'commit_hashes:\n  - "{old_hash} - some earlier, now-unreachable work"'),
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'base, already closed out')
        self._git('branch', '-q', '-m', 'develop')

        self._git('checkout', '-q', '-b', 'feature')
        self._write(
            'context/CTX-100.1-base.md',
            self._ctx_fixture(f'commit_hashes:\n  - "{old_hash} - some earlier, now-unreachable work"')
            .replace('# CTX-100.1\n', '# CTX-100.1\n\nAn unrelated Plan Drift correction.\n'),
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'unrelated edit, commit_hashes untouched')

        result = self._run_validator()

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_004_real_cli_flags_a_malformed_commit_hash_entry(self):
        self._init_base()
        self._write('daemon.py', 'x = 1\n')
        self._write(
            'context/CTX-100.1-base.md',
            self._ctx_fixture('commit_hashes:\n  - "not-a-real-hash-at-all"'),
        )
        self._git('add', '.')
        self._git('commit', '-q', '-m', 'add feature with a garbled hash entry')

        result = self._run_validator()

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn('MALFORMED COMMIT HASH', result.stdout)


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

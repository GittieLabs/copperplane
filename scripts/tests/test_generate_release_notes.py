import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import generate_release_notes as grn


_SAMPLE_CTX = """---
id: CTX-999.1
spec_ref: "../specs/SPEC-999-fixture.md"
title: "Fixture Context"
status: Completed
branch: "feat/CTX-999.1-fixture"
created: 2026-01-01
last_touched: 2026-01-01
version_included: "v0.1.0"
commit_hashes:
  - "abc1234 - fixture commit"
---

# CTX-999.1: Fixture Context

## 1. Feature Definition & Execution Plan

Some real phase content.

---

## 2. Testing Requirements Matrix

| Test ID | Test Description | Test File Location | Status |
| :--- | :--- | :--- | :--- |
| `TEST-001` | A fixture test | fixtures/test.py | Passed |

---

## 3. Implementation Log & Commit History

| Date | Phase | Description | Commit Hash |
| :--- | :--- | :--- | :--- |
| 2026-01-01 | Phase 1 | Fixture implementation | `abc1234` |

---

## 4. Plan Drift & Architectural Changes

None.
"""


class TestParseFrontmatter(unittest.TestCase):

    def test_001_extracts_real_yaml_frontmatter(self):
        frontmatter = grn.parse_frontmatter(_SAMPLE_CTX)
        self.assertEqual(frontmatter['id'], 'CTX-999.1')
        self.assertEqual(frontmatter['title'], 'Fixture Context')

    def test_002_no_frontmatter_returns_an_empty_dict_not_none(self):
        self.assertEqual(grn.parse_frontmatter("# Just a heading\n"), {})


class TestExtractImplementationLogTable(unittest.TestCase):

    def test_001_extracts_the_real_table_verbatim(self):
        table = grn.extract_implementation_log_table(_SAMPLE_CTX)
        self.assertIn('| Date | Phase | Description | Commit Hash |', table)
        self.assertIn('Fixture implementation', table)
        # The next section's own heading must not leak into the table.
        self.assertNotIn('Plan Drift', table)

    def test_002_no_matching_section_returns_an_empty_string(self):
        self.assertEqual(grn.extract_implementation_log_table("# No such section\n"), '')


class _RealGitRepoTestCase(unittest.TestCase):
    """Real git subprocess calls against a real, throwaway temp repo --
    CLAUDE.md's 'verify against the real thing' norm applied to a script
    whose entire job is real git plumbing, not something a mock could
    meaningfully stand in for."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        self._git('init', '-q', '-b', 'main')
        self._git('config', 'user.email', 'test@example.com')
        self._git('config', 'user.name', 'Test')

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _git(self, *args):
        subprocess.run(['git', *args], check=True, capture_output=True, text=True)

    def _commit_file(self, relpath, content, message):
        full = os.path.join(self.tmpdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(content)
        self._git('add', relpath)
        self._git('commit', '-q', '-m', message)


class TestChangedCtxFiles(_RealGitRepoTestCase):

    def test_001_finds_a_real_ctx_file_added_after_the_from_ref(self):
        self._commit_file('README.md', 'hello', 'initial commit')
        self._git('tag', 'v0.1.0')
        self._commit_file('services/python-daemon/context/CTX-100.1-fixture.md', _SAMPLE_CTX, 'add ctx')

        self.assertEqual(
            grn.changed_ctx_files('v0.1.0', 'HEAD'),
            ['services/python-daemon/context/CTX-100.1-fixture.md'],
        )

    def test_002_a_non_ctx_file_change_is_not_included(self):
        self._commit_file('README.md', 'hello', 'initial commit')
        self._git('tag', 'v0.1.0')
        self._commit_file('daemon.py', 'print("no")', 'unrelated code change')

        self.assertEqual(grn.changed_ctx_files('v0.1.0', 'HEAD'), [])

    def test_003_multiple_ctx_files_at_different_real_depths_are_all_found(self):
        self._commit_file('README.md', 'hello', 'initial commit')
        self._git('tag', 'v0.1.0')
        self._commit_file('context/CTX-100.1-root.md', _SAMPLE_CTX, 'root ctx')
        self._commit_file('apps/tauri-ui/context/CTX-100.2-ui.md', _SAMPLE_CTX, 'ui ctx')

        self.assertEqual(
            grn.changed_ctx_files('v0.1.0', 'HEAD'),
            ['apps/tauri-ui/context/CTX-100.2-ui.md', 'context/CTX-100.1-root.md'],
        )


class TestLatestTagAndFirstCommit(_RealGitRepoTestCase):

    def test_001_latest_tag_returns_none_when_the_repo_has_never_been_tagged(self):
        self._commit_file('README.md', 'hello', 'initial commit')
        self.assertIsNone(grn.latest_tag())

    def test_002_latest_tag_returns_the_most_recent_tag_before_the_given_ref(self):
        self._commit_file('README.md', 'hello', 'initial commit')
        self._git('tag', 'v0.1.0')
        self._commit_file('a.txt', 'a', 'second commit')
        self._commit_file('b.txt', 'b', 'third commit')
        self._git('tag', 'v0.2.0')

        self.assertEqual(grn.latest_tag(), 'v0.1.0')

    def test_003_latest_tag_excludes_a_tag_on_the_ref_itself(self):
        """The real production bug (v0.1.1's release notes): a CI run
        checks out a commit that is itself the just-pushed tag, so
        describing that ref naively returns its own tag back, producing a
        from_ref == to_ref null diff. latest_tag() must skip past it."""
        self._commit_file('README.md', 'hello', 'initial commit')
        self._git('tag', 'v0.1.0')
        self._commit_file('a.txt', 'a', 'second commit')
        self._git('tag', 'v0.2.0')

        self.assertEqual(grn.latest_tag('v0.2.0'), 'v0.1.0')

    def test_004_latest_tag_returns_none_when_the_only_tag_is_on_the_ref_itself(self):
        self._commit_file('README.md', 'hello', 'initial commit')
        self._git('tag', 'v0.1.0')

        self.assertIsNone(grn.latest_tag('v0.1.0'))

    def test_005_first_commit_returns_the_real_root_commit(self):
        self._commit_file('README.md', 'hello', 'initial commit')
        root = grn._run_git('rev-parse', 'HEAD').strip()
        self._commit_file('a.txt', 'a', 'second commit')

        self.assertEqual(grn.first_commit(), root)


class TestGenerateReleaseNotes(_RealGitRepoTestCase):

    def test_001_a_real_untagged_repo_produces_real_notes_from_its_first_commit(self):
        self._commit_file('README.md', 'hello', 'initial commit')
        self._commit_file('context/CTX-100.1-fixture.md', _SAMPLE_CTX, 'add ctx')
        root = grn.first_commit()

        notes = grn.generate_release_notes(root, 'HEAD')

        self.assertIn('CTX-999.1: Fixture Context', notes)
        self.assertIn('Fixture implementation', notes)

    def test_002_no_ctx_changes_in_range_says_so_plainly_not_silently_empty(self):
        self._commit_file('README.md', 'hello', 'initial commit')
        self._git('tag', 'v0.1.0')
        self._commit_file('a.txt', 'a', 'unrelated')

        notes = grn.generate_release_notes('v0.1.0', 'HEAD')

        self.assertIn('No CTX-*.md changes', notes)

    def test_003_cli_invocation_with_only_to_ref_finds_real_notes_not_a_null_diff(self):
        """End-to-end reproduction of the real v0.1.1 production bug via
        the actual CLI entry point, the same way release.yml invokes it:
        `--to-ref <tag>` only, no explicit --from-ref. HEAD is checked out
        at a commit that is itself tagged v0.1.1 -- exactly CI's real
        state after `git push` of a tag triggers the workflow."""
        self._commit_file('README.md', 'hello', 'initial commit')
        self._git('tag', 'v0.1.0')
        self._commit_file('context/CTX-100.1-fixture.md', _SAMPLE_CTX, 'add ctx')
        self._git('tag', 'v0.1.1')

        script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'generate_release_notes.py'))
        result = subprocess.run(
            [sys.executable, script, '--to-ref', 'v0.1.1'],
            capture_output=True, text=True, check=True,
        )

        self.assertIn('CTX-999.1: Fixture Context', result.stdout)
        self.assertNotIn('No CTX-*.md changes', result.stdout)


if __name__ == '__main__':
    unittest.main()

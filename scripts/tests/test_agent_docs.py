import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CLAUDE_MD = os.path.join(REPO_ROOT, 'CLAUDE.md')
COMMANDS_DIR = os.path.join(REPO_ROOT, '.claude', 'commands')
COMMAND_FILES = ['spec-status.md', 'new-spec.md', 'new-context.md', 'close-context.md']
MAX_CLAUDE_MD_LINES = 150


class TestAgentDocs(unittest.TestCase):
    """Mechanical guard on the bloat risk SPEC-901 Sec 3 calls out: CLAUDE.md
    must stay short enough to actually be read, and every slash command it
    references must exist."""

    def test_001_claude_md_exists(self):
        """TEST-001: CLAUDE.md exists at the repo root."""
        self.assertTrue(os.path.isfile(CLAUDE_MD), f"{CLAUDE_MD} does not exist")

    def test_002_claude_md_within_line_budget(self):
        """TEST-002: CLAUDE.md stays within its 150-line hard budget."""
        with open(CLAUDE_MD, encoding='utf-8') as f:
            line_count = sum(1 for _ in f)
        self.assertLessEqual(
            line_count, MAX_CLAUDE_MD_LINES,
            f"CLAUDE.md is {line_count} lines, over the {MAX_CLAUDE_MD_LINES}-line budget "
            "from SPEC-901 -- trim it, or move content into CONTRIBUTING.md instead."
        )

    def test_003_all_command_files_exist_and_are_nonempty(self):
        """TEST-003: all four slash command files exist and are non-empty."""
        for name in COMMAND_FILES:
            path = os.path.join(COMMANDS_DIR, name)
            with self.subTest(command=name):
                self.assertTrue(os.path.isfile(path), f"{path} does not exist")
                self.assertGreater(os.path.getsize(path), 0, f"{path} exists but is empty")


if __name__ == '__main__':
    unittest.main()

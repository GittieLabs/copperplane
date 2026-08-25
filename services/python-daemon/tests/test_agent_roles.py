import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_roles import AgentRoleError, load_agent_roles


def _write_prompt_file(directory: Path, filename: str, frontmatter: str, body: str = "Body.") -> None:
    (directory / filename).write_text(f"---\n{frontmatter}\n---\n{body}\n")


class TestLoadAgentRoles(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.agents_dir = Path(self._tmp.name)

    def test_001_a_missing_directory_returns_an_empty_dict_not_an_error(self):
        roles = load_agent_roles(self.agents_dir / "does-not-exist")
        self.assertEqual(roles, {})

    def test_002_real_repo_prompt_files_all_load_cleanly(self):
        """Against the actual, edited agentflow/agents/ directory -- not a
        synthetic fixture."""
        real_dir = Path(__file__).parent.parent / "agentflow" / "agents"
        roles = load_agent_roles(real_dir)
        self.assertEqual(len(roles), 12)
        self.assertEqual(roles["chat_overview"]["model_role"], "fast")
        self.assertEqual(roles["component_extraction"]["model_role"], "reasoning")

    def test_003_a_valid_model_role_and_requires_are_parsed(self):
        _write_prompt_file(
            self.agents_dir, "x.prompt.md",
            "name: x\nmodel_role: reasoning\nrequires:\n  - tool_use\n  - strict_json",
        )
        roles = load_agent_roles(self.agents_dir)
        self.assertEqual(roles["x"], {"model_role": "reasoning", "requires": ["tool_use", "strict_json"]})

    def test_004_requires_defaults_to_an_empty_list_when_absent(self):
        _write_prompt_file(self.agents_dir, "x.prompt.md", "name: x\nmodel_role: fast")
        roles = load_agent_roles(self.agents_dir)
        self.assertEqual(roles["x"]["requires"], [])

    def test_005_a_missing_model_role_is_a_load_time_error(self):
        _write_prompt_file(self.agents_dir, "x.prompt.md", "name: x")
        with self.assertRaises(AgentRoleError):
            load_agent_roles(self.agents_dir)

    def test_006_a_typoed_model_role_is_a_load_time_error_not_silently_dropped(self):
        """The exact gotcha SPEC-208 §2.3.3 names: AgentConfig's own
        extra='ignore' would silently discard this -- this sidecar must
        not repeat that mistake."""
        _write_prompt_file(self.agents_dir, "x.prompt.md", "name: x\nmodel_role: resoning")
        with self.assertRaises(AgentRoleError):
            load_agent_roles(self.agents_dir)

    def test_007_an_unrecognized_requires_entry_is_a_load_time_error(self):
        _write_prompt_file(self.agents_dir, "x.prompt.md", "name: x\nmodel_role: fast\nrequires:\n  - telepathy")
        with self.assertRaises(AgentRoleError):
            load_agent_roles(self.agents_dir)

    def test_008_a_missing_name_is_a_load_time_error(self):
        _write_prompt_file(self.agents_dir, "x.prompt.md", "model_role: fast")
        with self.assertRaises(AgentRoleError):
            load_agent_roles(self.agents_dir)

    def test_009_non_prompt_files_in_the_directory_are_ignored(self):
        _write_prompt_file(self.agents_dir, "x.prompt.md", "name: x\nmodel_role: fast")
        (self.agents_dir / "README.md").write_text("not a prompt file")
        roles = load_agent_roles(self.agents_dir)
        self.assertEqual(set(roles.keys()), {"x"})


if __name__ == '__main__':
    unittest.main()

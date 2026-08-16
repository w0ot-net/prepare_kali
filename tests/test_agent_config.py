import json
import tempfile
import unittest
from pathlib import Path

from prepare_debian.tasks import configure_agents
from prepare_debian.utils import config_utils


class AgentConfigTests(unittest.TestCase):
    def test_disables_attribution_and_preserves_other_values(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            codex_home = home / ".codex"
            codex_home.mkdir()
            codex_path = codex_home / "config.toml"
            codex_path.write_text(
                'model = "gpt-test"\n[projects."/tmp"]\ntrust_level = "trusted"\n',
                encoding="utf-8",
            )

            claude_path = home / ".claude" / "settings.json"
            claude_path.parent.mkdir()
            claude_path.write_text(
                json.dumps({"permissions": {"allow": ["Read"]}}),
                encoding="utf-8",
            )

            configure_agents.apply_agent_config(home, codex_home)

            codex_content = codex_path.read_text(encoding="utf-8")
            self.assertIn('model = "gpt-test"', codex_content)
            self.assertIn('commit_attribution = ""', codex_content)
            self.assertLess(
                codex_content.index("commit_attribution"),
                codex_content.index("[projects"),
            )

            claude_values = json.loads(claude_path.read_text(encoding="utf-8"))
            self.assertEqual(claude_values["permissions"], {"allow": ["Read"]})
            self.assertEqual(
                claude_values["attribution"],
                {"commit": "", "pr": "", "sessionUrl": False},
            )
            self.assertIs(claude_values["includeCoAuthoredBy"], False)

    def test_second_update_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            codex_home = home / ".codex"

            configure_agents.apply_agent_config(home, codex_home)
            codex_path = codex_home / "config.toml"
            claude_path = home / ".claude" / "settings.json"
            before = (codex_path.read_bytes(), claude_path.read_bytes())

            configure_agents.apply_agent_config(home, codex_home)

            self.assertEqual(before, (codex_path.read_bytes(), claude_path.read_bytes()))

    def test_invalid_json_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not json\n", encoding="utf-8")

            with self.assertRaises(config_utils.ConfigUpdateError):
                config_utils.update_json_values(path, configure_agents.CLAUDE_VALUES)

            self.assertEqual(path.read_text(encoding="utf-8"), "not json\n")


if __name__ == "__main__":
    unittest.main()

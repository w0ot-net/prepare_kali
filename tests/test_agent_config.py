import io
import json
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from prepare_debian.tasks import configure_agents
from prepare_debian.utils import config_utils


class AgentConfigTests(unittest.TestCase):
    def test_disables_attribution_and_preserves_other_values(self) -> None:
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

    def test_second_update_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            codex_home = home / ".codex"

            configure_agents.apply_agent_config(home, codex_home)
            codex_path = codex_home / "config.toml"
            claude_path = home / ".claude" / "settings.json"
            before = (codex_path.read_bytes(), claude_path.read_bytes())

            configure_agents.apply_agent_config(home, codex_home)

            self.assertEqual(
                before, (codex_path.read_bytes(), claude_path.read_bytes())
            )

    def test_invalid_json_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not json\n", encoding="utf-8")

            with self.assertRaises(config_utils.ConfigUpdateError):
                config_utils.update_json_values(path, configure_agents.CLAUDE_VALUES)

            self.assertEqual(path.read_text(encoding="utf-8"), "not json\n")


def completed(command: str = "tool") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([command], 0, "1.0.0", "")


def test_local_bin_is_added_to_shell_profiles_idempotently(tmp_path: Path) -> None:
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("# existing\n", encoding="utf-8")

    assert configure_agents.ensure_local_bin_on_path(tmp_path) is True
    assert configure_agents.ensure_local_bin_on_path(tmp_path) is True

    for filename in configure_agents.PROFILE_FILES:
        content = (tmp_path / filename).read_text(encoding="utf-8")
        assert content.count(configure_agents.LOCAL_BIN_EXPORT) == 1
    assert bashrc.read_text(encoding="utf-8").startswith("# existing\n")


def test_existing_cli_skips_installer(tmp_path: Path) -> None:
    spec = configure_agents.CLI_SPECS[0]
    executable = tmp_path / spec.command
    executable.write_text("", encoding="utf-8")
    with (
        mock.patch.object(configure_agents, "locate_cli", return_value=executable),
        mock.patch.object(configure_agents, "run_installer") as installer,
        mock.patch.object(
            configure_agents.process_utils, "run", return_value=completed(spec.command)
        ),
    ):
        assert configure_agents.ensure_cli(spec, tmp_path) is True

    installer.assert_not_called()


def test_missing_cli_runs_installer_then_verifies(tmp_path: Path) -> None:
    spec = configure_agents.CLI_SPECS[1]
    executable = tmp_path / spec.command
    with (
        mock.patch.object(
            configure_agents, "locate_cli", side_effect=[None, executable]
        ),
        mock.patch.object(configure_agents, "run_installer", return_value=True),
        mock.patch.object(
            configure_agents.process_utils, "run", return_value=completed(spec.command)
        ),
    ):
        assert configure_agents.ensure_cli(spec, tmp_path) is True


def test_failed_cli_installer_is_propagated(tmp_path: Path) -> None:
    spec = configure_agents.CLI_SPECS[0]
    with (
        mock.patch.object(configure_agents, "locate_cli", return_value=None),
        mock.patch.object(configure_agents, "run_installer", return_value=False),
    ):
        assert configure_agents.ensure_cli(spec, tmp_path) is False


def test_installer_download_failure_is_propagated() -> None:
    with mock.patch.object(
        configure_agents.urllib.request,
        "urlopen",
        side_effect=urllib.error.URLError("offline"),
    ) as urlopen:
        assert configure_agents.run_installer(configure_agents.CLI_SPECS[0]) is False

    request = urlopen.call_args.args[0]
    assert request.get_header("User-agent") == configure_agents.DOWNLOAD_USER_AGENT


def test_installers_run_with_automation_environment() -> None:
    for spec in configure_agents.CLI_SPECS:
        with (
            mock.patch.object(
                configure_agents.urllib.request,
                "urlopen",
                return_value=io.BytesIO(b"#!/bin/sh\n"),
            ),
            mock.patch.object(
                configure_agents.process_utils,
                "run",
                return_value=completed(spec.command),
            ) as run,
        ):
            assert configure_agents.run_installer(spec) is True

        command = run.call_args.args[0]
        assert command[:3] == ["env", spec.installer_environment, spec.interpreter]


def test_cli_version_failure_is_propagated(tmp_path: Path) -> None:
    spec = configure_agents.CLI_SPECS[0]
    executable = tmp_path / spec.command
    failed = subprocess.CompletedProcess([spec.command], 1, "", "failed")
    with (
        mock.patch.object(configure_agents, "locate_cli", return_value=executable),
        mock.patch.object(configure_agents.process_utils, "run", return_value=failed),
    ):
        assert configure_agents.ensure_cli(spec, tmp_path) is False


def make_skill(checkout: Path, name: str) -> Path:
    skill = checkout / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    return skill


def test_skills_are_linked_for_both_agents_and_idempotent(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    skill = make_skill(checkout, "review")
    home = tmp_path / "home"

    assert configure_agents.install_skills(checkout, home) is True
    assert configure_agents.install_skills(checkout, home) is True
    for root in (home / ".claude" / "skills", home / ".agents" / "skills"):
        link = root / "review"
        assert link.is_symlink()
        assert link.resolve() == skill.resolve()


def test_stale_managed_links_are_removed(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    make_skill(checkout, "current")
    home = tmp_path / "home"
    root = home / ".claude" / "skills"
    root.mkdir(parents=True)
    stale = root / "removed"
    stale.symlink_to(checkout / "skills" / "removed", target_is_directory=True)

    assert configure_agents.install_skills(checkout, home) is True
    assert stale.is_symlink() is False


def test_user_owned_skill_conflict_is_preserved(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    make_skill(checkout, "review")
    home = tmp_path / "home"
    conflict = home / ".claude" / "skills" / "review"
    conflict.mkdir(parents=True)
    marker = conflict / "keep.txt"
    marker.write_text("keep\n", encoding="utf-8")

    assert configure_agents.install_skills(checkout, home) is False
    assert marker.read_text(encoding="utf-8") == "keep\n"


def test_repository_failure_prevents_skill_installation() -> None:
    with (
        mock.patch.object(configure_agents, "apply_agent_config"),
        mock.patch.object(
            configure_agents, "ensure_local_bin_on_path", return_value=True
        ),
        mock.patch.object(configure_agents, "ensure_cli", return_value=True),
        mock.patch.object(
            configure_agents.set_tools, "ensure_tools_dir", return_value=True
        ),
        mock.patch.object(
            configure_agents.set_tools,
            "synchronize_repository",
            return_value=False,
        ),
        mock.patch.object(configure_agents, "install_skills") as install,
    ):
        assert configure_agents.main() is False

    install.assert_not_called()


if __name__ == "__main__":
    unittest.main()

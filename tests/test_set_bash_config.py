import subprocess
from pathlib import Path
from unittest import mock

from prepare_debian.tasks import set_bash_config


def test_installer_is_gated_on_repository_sync() -> None:
    with (
        mock.patch.object(
            set_bash_config.apt_utils, "update_apt_cache", return_value=True
        ),
        mock.patch.object(
            set_bash_config.apt_utils, "ensure_apt_package", return_value=True
        ),
        mock.patch.object(
            set_bash_config.set_tools, "ensure_tools_dir", return_value=True
        ),
        mock.patch.object(
            set_bash_config, "ensure_bash_config_repo", return_value=False
        ),
        mock.patch.object(set_bash_config, "run_install") as install,
    ):
        assert set_bash_config.main() is False

    install.assert_not_called()


def test_failed_installer_is_propagated(tmp_path: Path) -> None:
    install_script = tmp_path / "install.py"
    install_script.write_text("pass\n", encoding="utf-8")
    result = subprocess.CompletedProcess(["python"], 1, "", "failed")
    with (
        mock.patch.object(
            set_bash_config.set_tools, "repository_path", return_value=tmp_path
        ),
        mock.patch.object(set_bash_config.process_utils, "run", return_value=result),
    ):
        assert set_bash_config.run_install() is False

from unittest import mock

from prepare_debian.repositories import RepositorySpec
from prepare_debian.tasks import (
    install_packages,
    prepare_impacket,
    set_bash_config,
    set_shell_to_bash,
    set_tools,
)


def test_install_packages_stops_when_cache_update_fails() -> None:
    with (
        mock.patch.object(
            install_packages.apt_utils, "update_apt_cache", return_value=False
        ),
        mock.patch.object(install_packages.apt_utils, "ensure_apt_package") as install,
    ):
        assert install_packages.main() is False

    install.assert_not_called()


def test_install_packages_include_requested_system_tools() -> None:
    assert {
        "accountsservice",
        "impacket-scripts",
        "kali-root-login",
        "masscan",
        "open-vm-tools",
        "open-vm-tools-desktop",
        "snmp",
        "ssh",
        "tailscale",
        "virtualbox-guest-x11",
        "vim",
    } <= set(install_packages.PACKAGES)


def test_prepare_impacket_stops_when_package_install_fails() -> None:
    with (
        mock.patch.object(
            prepare_impacket.apt_utils, "ensure_apt_package", return_value=False
        ),
        mock.patch.object(prepare_impacket, "ensure_path_in_profile") as configure,
    ):
        assert prepare_impacket.main() is False

    configure.assert_not_called()


def test_set_tools_aggregates_repository_failures() -> None:
    repositories = (
        RepositorySpec("one", "https://example.com/one", "1" * 40),
        RepositorySpec("two", "https://example.com/two", "2" * 40),
    )
    with (
        mock.patch.object(set_tools, "ensure_tools_dir", return_value=True),
        mock.patch.object(set_tools, "TOOL_REPOSITORIES", repositories),
        mock.patch.object(
            set_tools, "synchronize_repository", side_effect=[False, True]
        ) as ensure,
    ):
        assert set_tools.main() is False

    ensure.assert_called_once_with(repositories[0])


def test_bash_config_stops_before_installer_on_repository_failure() -> None:
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


def test_shell_task_reports_missing_root_privileges() -> None:
    with (
        mock.patch.object(set_shell_to_bash.os.path, "exists", return_value=True),
        mock.patch.object(set_shell_to_bash.os, "geteuid", return_value=1000),
        mock.patch.object(set_shell_to_bash.process_utils, "run") as run,
    ):
        assert set_shell_to_bash.main() is False

    run.assert_not_called()

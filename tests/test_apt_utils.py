import os
import subprocess
from unittest import mock

from prepare_debian.utils import apt_utils


def test_root_apt_command_does_not_use_sudo() -> None:
    with (
        mock.patch("shutil.which", return_value="/usr/bin/apt-get"),
        mock.patch.object(os, "geteuid", return_value=0),
    ):
        assert apt_utils.apt_command(["update"]) == ["apt-get", "update"]


def test_non_root_apt_command_uses_sudo() -> None:
    with (
        mock.patch("shutil.which", side_effect=lambda name: f"/usr/bin/{name}"),
        mock.patch.object(os, "geteuid", return_value=1000),
    ):
        assert apt_utils.apt_command(["update"]) == ["sudo", "apt-get", "update"]


def test_missing_apt_get_is_a_normal_failure() -> None:
    with mock.patch("shutil.which", return_value=None):
        assert apt_utils.apt_command(["update"]) is None


def test_update_propagates_nonzero_result() -> None:
    result = subprocess.CompletedProcess(["apt-get"], 1, "", "failed")
    with (
        mock.patch.object(apt_utils, "apt_command", return_value=["apt-get", "update"]),
        mock.patch.object(apt_utils.process_utils, "run", return_value=result),
    ):
        assert apt_utils.update_apt_cache() is False


def test_package_availability_uses_apt_cache() -> None:
    result = subprocess.CompletedProcess(["apt-cache"], 0, "Package: responder", "")
    with (
        mock.patch("shutil.which", return_value="/usr/bin/apt-cache"),
        mock.patch.object(apt_utils.process_utils, "run", return_value=result) as run,
    ):
        assert apt_utils.is_package_available("responder") is True

    run.assert_called_once_with(["apt-cache", "show", "responder"])


def test_installed_package_skips_install() -> None:
    with (
        mock.patch.object(apt_utils, "is_package_installed", return_value=True),
        mock.patch.object(apt_utils, "apt_command") as apt_command,
    ):
        assert apt_utils.ensure_apt_package("git") is True

    apt_command.assert_not_called()

import stat
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from prepare_debian.tasks import disable_virtualbox_drag_and_drop as disable_vbox

LAUNCHER = """#!/bin/sh
if test "$vbox_wl_check" = "WL"; then
    /usr/bin/VBoxClient --wayland || true
else
    /usr/bin/VBoxClient --clipboard || true
    /usr/bin/VBoxClient --checkhostversion || true
    /usr/bin/VBoxClient --seamless || true
    /usr/bin/VBoxClient --draganddrop || true
fi
"""


def result(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def test_launcher_disables_only_drag_and_drop_clients() -> None:
    rendered = disable_vbox.render_launcher(LAUNCHER)

    assert disable_vbox.DRAG_AND_DROP_COMMAND not in rendered
    assert disable_vbox.WAYLAND_COMMAND not in rendered
    assert "/usr/bin/VBoxClient --clipboard || true" in rendered
    assert "/usr/bin/VBoxClient --checkhostversion || true" in rendered
    assert "/usr/bin/VBoxClient --seamless || true" in rendered
    assert disable_vbox.DRAG_AND_DROP_COMMENT in rendered
    assert disable_vbox.WAYLAND_COMMENT in rendered
    assert disable_vbox.render_launcher(rendered) == rendered


def test_launcher_rejects_unknown_active_drag_and_drop_command() -> None:
    launcher = "/usr/bin/VBoxClient --draganddrop --verbose || true\n"

    with pytest.raises(ValueError, match="Unexpected active VBoxClient"):
        disable_vbox.render_launcher(launcher)


def test_configure_launcher_preserves_mode_and_verifies_shell(tmp_path: Path) -> None:
    launcher = tmp_path / "98vboxadd-xclient"
    launcher.write_text(LAUNCHER, encoding="utf-8")
    launcher.chmod(0o755)

    with mock.patch.object(
        disable_vbox.process_utils, "run", return_value=result()
    ) as run:
        assert disable_vbox.configure_launcher(launcher) is True

    run.assert_called_once()
    assert run.call_args.args[0][:2] == ["/bin/sh", "-n"]
    assert stat.S_IMODE(launcher.stat().st_mode) == 0o755
    installed = launcher.read_text(encoding="utf-8")
    assert disable_vbox.render_launcher(installed) == installed


def test_missing_launcher_is_a_successful_skip(tmp_path: Path) -> None:
    launcher = tmp_path / "missing-launcher"

    with mock.patch.object(disable_vbox.process_utils, "run") as run:
        assert disable_vbox.configure_launcher(launcher) is True

    run.assert_not_called()


def test_non_virtualbox_guest_is_a_successful_noop() -> None:
    with (
        mock.patch.object(disable_vbox, "detect_virtualbox", return_value=False),
        mock.patch.object(disable_vbox, "configure_launcher") as configure,
        mock.patch.object(disable_vbox, "stop_clients") as stop,
    ):
        assert disable_vbox.main() is True

    configure.assert_not_called()
    stop.assert_not_called()


def test_virtualbox_guest_is_configured_and_running_clients_are_stopped() -> None:
    with (
        mock.patch.object(disable_vbox, "detect_virtualbox", return_value=True),
        mock.patch.object(disable_vbox.os, "geteuid", return_value=0),
        mock.patch.object(
            disable_vbox, "configure_launcher", return_value=True
        ) as configure,
        mock.patch.object(disable_vbox, "stop_clients", return_value=True) as stop,
    ):
        assert disable_vbox.main() is True

    configure.assert_called_once_with()
    stop.assert_called_once_with()


def test_stop_clients_accepts_running_and_absent_processes() -> None:
    with mock.patch.object(
        disable_vbox.process_utils,
        "run",
        side_effect=(result(returncode=0), result(returncode=1)),
    ) as run:
        assert disable_vbox.stop_clients() is True

    assert run.call_count == 2


def test_stop_clients_propagates_command_failure() -> None:
    with mock.patch.object(
        disable_vbox.process_utils,
        "run",
        return_value=result(returncode=2, stderr="pkill failed"),
    ):
        assert disable_vbox.stop_clients() is False

import subprocess
from pathlib import Path
from unittest import mock

from prepare_debian.tasks import restart_virtualbox_guest as restart_vbox


def result(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def test_discovers_launcher_modes_without_drag_and_drop(tmp_path: Path) -> None:
    launcher = tmp_path / "98vboxadd-xclient"
    launcher.write_text(
        """#!/bin/sh
/usr/bin/VBoxClient --clipboard || true
/usr/bin/VBoxClient --seamless || true
/usr/bin/VBoxClient --draganddrop || true
/usr/bin/VBoxClient --checkhostversion || true
/usr/bin/VBoxClient --vmsvga-session || true
# /usr/bin/VBoxClient --wayland || true
""",
        encoding="utf-8",
    )

    assert restart_vbox.discover_client_modes(launcher) == (
        "clipboard",
        "seamless",
        "checkhostversion",
        "vmsvga-session",
    )


def test_restarts_only_installed_service_units_with_sudo() -> None:
    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command == ["systemctl", "cat", restart_vbox.SERVICE_UNITS[0]]:
            return result()
        if command == ["systemctl", "cat", restart_vbox.SERVICE_UNITS[1]]:
            return result(returncode=1)
        return result()

    with (
        mock.patch.object(restart_vbox.os, "geteuid", return_value=1000),
        mock.patch.object(
            restart_vbox.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"
        ),
        mock.patch.object(restart_vbox.process_utils, "run", side_effect=run) as runner,
    ):
        assert restart_vbox.restart_services() is True

    assert [
        "sudo",
        "systemctl",
        "restart",
        restart_vbox.SERVICE_UNITS[0],
    ] in [call.args[0] for call in runner.call_args_list]
    assert [
        "sudo",
        "systemctl",
        "restart",
        restart_vbox.SERVICE_UNITS[1],
    ] not in [call.args[0] for call in runner.call_args_list]


def test_restarts_desktop_clients_and_removes_stale_pid_files(
    tmp_path: Path,
) -> None:
    launcher = tmp_path / "launcher"
    launcher.write_text(
        "/usr/bin/VBoxClient --clipboard || true\n"
        "/usr/bin/VBoxClient --draganddrop || true\n"
        "/usr/bin/VBoxClient --seamless || true\n",
        encoding="utf-8",
    )
    stale_pid = tmp_path / ".vboxclient-clipboard.pid"
    stale_pid.write_text("123\n", encoding="utf-8")

    with (
        mock.patch.object(
            restart_vbox.shutil, "which", return_value="/usr/bin/VBoxClient"
        ),
        mock.patch.object(
            restart_vbox.process_utils, "run", return_value=result()
        ) as runner,
        mock.patch.object(restart_vbox.time, "sleep") as sleep,
    ):
        assert restart_vbox.restart_clients(tmp_path, 1000, launcher) is True

    assert stale_pid.exists() is False
    sleep.assert_called_once_with(1)
    commands = [call.args[0] for call in runner.call_args_list]
    assert commands == [
        ["pkill", "-u", "1000", "-x", "VBoxClient"],
        ["/usr/bin/VBoxClient", "--clipboard"],
        ["/usr/bin/VBoxClient", "--seamless"],
    ]
    assert all("--draganddrop" not in command for command in commands)


def test_non_virtualbox_guest_is_a_successful_noop() -> None:
    with (
        mock.patch.object(restart_vbox, "detect_virtualbox", return_value=False),
        mock.patch.object(restart_vbox, "restart_services") as services,
        mock.patch.object(restart_vbox, "restart_clients") as clients,
    ):
        assert restart_vbox.main() is True

    services.assert_not_called()
    clients.assert_not_called()


def test_virtualbox_x11_session_restarts_services_and_clients() -> None:
    with (
        mock.patch.object(restart_vbox, "detect_virtualbox", return_value=True),
        mock.patch.object(restart_vbox.os, "geteuid", return_value=1000),
        mock.patch.dict(
            restart_vbox.os.environ,
            {"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"},
            clear=True,
        ),
        mock.patch.object(
            restart_vbox, "restart_services", return_value=True
        ) as services,
        mock.patch.object(
            restart_vbox, "restart_clients", return_value=True
        ) as clients,
    ):
        assert restart_vbox.main() is True

    services.assert_called_once_with()
    clients.assert_called_once_with()


def test_wayland_session_is_rejected_before_changes() -> None:
    with (
        mock.patch.object(restart_vbox, "detect_virtualbox", return_value=True),
        mock.patch.object(restart_vbox.os, "geteuid", return_value=1000),
        mock.patch.dict(
            restart_vbox.os.environ,
            {"DISPLAY": ":0", "XDG_SESSION_TYPE": "wayland"},
            clear=True,
        ),
        mock.patch.object(restart_vbox, "restart_services") as services,
        mock.patch.object(restart_vbox, "restart_clients") as clients,
    ):
        assert restart_vbox.main() is False

    services.assert_not_called()
    clients.assert_not_called()


def test_wayland_display_is_rejected_when_session_type_is_missing() -> None:
    with (
        mock.patch.object(restart_vbox, "detect_virtualbox", return_value=True),
        mock.patch.object(restart_vbox.os, "geteuid", return_value=1000),
        mock.patch.dict(
            restart_vbox.os.environ,
            {"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0"},
            clear=True,
        ),
        mock.patch.object(restart_vbox, "restart_services") as services,
        mock.patch.object(restart_vbox, "restart_clients") as clients,
    ):
        assert restart_vbox.main() is False

    services.assert_not_called()
    clients.assert_not_called()

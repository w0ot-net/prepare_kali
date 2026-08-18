import subprocess
from unittest import mock

from prepare_debian.tasks import disable_screen_lock


def result(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["settings"], returncode, stdout, "")


def test_detects_gnome_and_xfce_sessions() -> None:
    assert (
        disable_screen_lock.detect_desktop({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"})
        == "gnome"
    )
    assert disable_screen_lock.detect_desktop({"XDG_CURRENT_DESKTOP": "XFCE"}) == "xfce"
    assert disable_screen_lock.detect_desktop({"DESKTOP_SESSION": "xfce"}) == "xfce"


def test_unknown_or_ambiguous_desktop_is_rejected() -> None:
    assert disable_screen_lock.detect_desktop({}) is None
    assert (
        disable_screen_lock.detect_desktop({"XDG_CURRENT_DESKTOP": "GNOME:XFCE"})
        is None
    )


def test_gnome_settings_are_written_and_verified() -> None:
    state = {
        (schema, key): "old" for schema, key, _ in disable_screen_lock.GNOME_SETTINGS
    }

    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        _, operation, schema, key, *value = command
        if operation == "set":
            state[(schema, key)] = value[0]
            return result()
        return result(state[(schema, key)])

    with mock.patch.object(disable_screen_lock.process_utils, "run", side_effect=run):
        assert disable_screen_lock.configure_gnome() is True

    assert state == {
        (schema, key): desired
        for schema, key, desired in disable_screen_lock.GNOME_SETTINGS
    }


def test_already_correct_gnome_settings_are_not_rewritten() -> None:
    responses = [
        result(desired) for _, _, desired in disable_screen_lock.GNOME_SETTINGS
    ]

    with mock.patch.object(
        disable_screen_lock.process_utils, "run", side_effect=responses
    ) as run:
        assert disable_screen_lock.configure_gnome() is True

    assert run.call_count == len(disable_screen_lock.GNOME_SETTINGS)


def test_xfce_settings_are_written_and_verified() -> None:
    state = {
        (channel, property_name): "true"
        for channel, property_name in disable_screen_lock.XFCE_SETTINGS
    }

    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command == ["xfce4-screensaver-command", "--deactivate", "--poke"]:
            return result()
        channel = command[command.index("--channel") + 1]
        property_name = command[command.index("--property") + 1]
        if "--set" in command:
            state[(channel, property_name)] = command[command.index("--set") + 1]
            return result()
        return result(state[(channel, property_name)])

    with mock.patch.object(
        disable_screen_lock.process_utils, "run", side_effect=run
    ) as run_mock:
        assert disable_screen_lock.configure_xfce() is True

    assert all(value == "false" for value in state.values())
    run_mock.assert_called_with(
        ["xfce4-screensaver-command", "--deactivate", "--poke"]
    )


def test_xfce_missing_property_is_created_as_boolean() -> None:
    calls: list[list[str]] = []
    responses = []
    for _ in disable_screen_lock.XFCE_SETTINGS:
        responses.extend([result(returncode=1), result(), result("false")])
    responses.append(result())

    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return responses.pop(0)

    with mock.patch.object(disable_screen_lock.process_utils, "run", side_effect=run):
        assert disable_screen_lock.configure_xfce() is True

    updates = [command for command in calls if "--set" in command]
    assert all("--create" in command for command in updates)
    assert all(command[command.index("--type") + 1] == "bool" for command in updates)


def test_xfce_process_reset_failure_is_propagated() -> None:
    responses = [
        result("false") for _ in disable_screen_lock.XFCE_SETTINGS
    ] + [result(returncode=1)]

    with mock.patch.object(
        disable_screen_lock.process_utils, "run", side_effect=responses
    ):
        assert disable_screen_lock.configure_xfce() is False


def test_failed_setting_write_is_propagated() -> None:
    with mock.patch.object(
        disable_screen_lock.process_utils,
        "run",
        side_effect=[result("true"), result(returncode=1)],
    ):
        assert disable_screen_lock.configure_gnome() is False


def test_read_back_mismatch_is_propagated() -> None:
    with mock.patch.object(
        disable_screen_lock.process_utils,
        "run",
        side_effect=[result("old"), result(), result("old")],
    ):
        assert disable_screen_lock.configure_gnome() is False


def test_unknown_desktop_main_does_not_run_a_backend() -> None:
    with (
        mock.patch.object(disable_screen_lock, "detect_desktop", return_value=None),
        mock.patch.object(disable_screen_lock, "configure_gnome") as gnome,
        mock.patch.object(disable_screen_lock, "configure_xfce") as xfce,
    ):
        assert disable_screen_lock.main() is False

    gnome.assert_not_called()
    xfce.assert_not_called()

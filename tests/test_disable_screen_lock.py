import subprocess
from pathlib import Path
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


def test_gnome_system_policy_is_written_updated_and_locked(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile" / "user"
    settings_path = tmp_path / "local.d" / "disable-screen-lock"
    locks_path = tmp_path / "local.d" / "locks" / "disable-screen-lock"
    responses = [result()]
    for _, _, desired in disable_screen_lock.GNOME_SETTINGS:
        responses.extend([result(desired), result("false")])

    with mock.patch.object(
        disable_screen_lock.process_utils, "run", side_effect=responses
    ) as run:
        assert (
            disable_screen_lock.configure_gnome_system(
                settings_path, locks_path, profile_path
            )
            is True
        )

    assert profile_path.read_text(encoding="utf-8") == (
        "user-db:user\nsystem-db:local\n"
    )
    assert settings_path.read_text(encoding="utf-8") == (
        disable_screen_lock.GNOME_SYSTEM_SETTINGS
    )
    assert locks_path.read_text(encoding="utf-8") == (
        disable_screen_lock.GNOME_SYSTEM_LOCKS
    )
    assert run.call_args_list[0] == mock.call(["dconf", "update"])


def test_gnome_system_policy_requires_locked_values(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile" / "user"
    settings_path = tmp_path / "local.d" / "disable-screen-lock"
    locks_path = tmp_path / "local.d" / "locks" / "disable-screen-lock"

    with mock.patch.object(
        disable_screen_lock.process_utils,
        "run",
        side_effect=[result(), result("uint32 0"), result("true")],
    ):
        assert (
            disable_screen_lock.configure_gnome_system(
                settings_path, locks_path, profile_path
            )
            is False
        )


def test_gnome_dconf_profile_preserves_existing_databases(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile" / "user"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(
        "user-db:user\nsystem-db:site\n",
        encoding="utf-8",
    )

    assert disable_screen_lock._ensure_dconf_profile(profile_path) is True
    assert profile_path.read_text(encoding="utf-8") == (
        "user-db:user\nsystem-db:site\nsystem-db:local\n"
    )


def test_root_gnome_main_uses_system_policy() -> None:
    with (
        mock.patch.object(
            disable_screen_lock,
            "detect_desktop",
            return_value="gnome",
        ),
        mock.patch.object(disable_screen_lock.os, "geteuid", return_value=0),
        mock.patch.object(
            disable_screen_lock, "configure_gnome_system", return_value=True
        ) as system,
        mock.patch.object(disable_screen_lock, "configure_gnome") as per_user,
    ):
        assert disable_screen_lock.main() is True

    system.assert_called_once_with()
    per_user.assert_not_called()


def test_non_root_gnome_main_uses_per_user_settings() -> None:
    with (
        mock.patch.object(
            disable_screen_lock,
            "detect_desktop",
            return_value="gnome",
        ),
        mock.patch.object(disable_screen_lock.os, "geteuid", return_value=1000),
        mock.patch.object(disable_screen_lock, "configure_gnome_system") as system,
        mock.patch.object(
            disable_screen_lock, "configure_gnome", return_value=True
        ) as per_user,
    ):
        assert disable_screen_lock.main() is True

    system.assert_not_called()
    per_user.assert_called_once_with()


def test_xfce_settings_are_written_and_verified() -> None:
    state = {
        (channel, property_name): "true"
        for channel, property_name in disable_screen_lock.XFCE_SETTINGS
    }

    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "xfce4-screensaver-command":
            return result()
        if command[0] == "xset":
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
    for command in disable_screen_lock.XFCE_X11_COMMANDS:
        run_mock.assert_any_call(command)
    run_mock.assert_any_call(["xfce4-screensaver-command", "--query"])
    run_mock.assert_called_with(["xfce4-screensaver-command", "--deactivate", "--poke"])


def test_xfce_missing_property_is_created_as_boolean() -> None:
    calls: list[list[str]] = []
    responses = []
    for _ in disable_screen_lock.XFCE_SETTINGS:
        responses.extend([result(returncode=1), result(), result("false")])
    responses.extend(result() for _ in disable_screen_lock.XFCE_X11_COMMANDS)
    responses.extend([result(), result()])

    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return responses.pop(0)

    with mock.patch.object(disable_screen_lock.process_utils, "run", side_effect=run):
        assert disable_screen_lock.configure_xfce() is True

    updates = [command for command in calls if "--set" in command]
    assert all("--create" in command for command in updates)
    assert all(command[command.index("--type") + 1] == "bool" for command in updates)


def test_xfce_process_reset_failure_is_propagated() -> None:
    responses = [result("false") for _ in disable_screen_lock.XFCE_SETTINGS]
    responses.extend(result() for _ in disable_screen_lock.XFCE_X11_COMMANDS)
    responses.extend([result(), result(returncode=1)])

    with mock.patch.object(
        disable_screen_lock.process_utils, "run", side_effect=responses
    ):
        assert disable_screen_lock.configure_xfce() is False


def test_xfce_without_running_screensaver_needs_no_reset() -> None:
    responses = [result("false") for _ in disable_screen_lock.XFCE_SETTINGS]
    responses.extend(result() for _ in disable_screen_lock.XFCE_X11_COMMANDS)
    responses.append(result(returncode=1))

    with mock.patch.object(
        disable_screen_lock.process_utils, "run", side_effect=responses
    ) as run:
        assert disable_screen_lock.configure_xfce() is True

    run.assert_called_with(["xfce4-screensaver-command", "--query"])


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

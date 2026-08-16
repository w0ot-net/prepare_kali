import runpy
import sys
from collections.abc import Callable
from unittest import mock

import pytest

from prepare_debian import cli

EXPECTED_TASKS = {
    "configure_agents",
    "install_packages",
    "prepare_impacket",
    "set_bash_config",
    "set_shell_to_bash",
    "set_tools",
}


def test_task_registry_exposes_expected_tasks() -> None:
    assert set(cli.TASKS) == EXPECTED_TASKS


def test_help_does_not_run_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    task = mock.Mock()
    monkeypatch.setattr(cli, "TASKS", {"safe": task})
    monkeypatch.setattr(sys, "argv", ["prepare-debian", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 0
    task.assert_not_called()


def test_no_arguments_runs_all_tasks_in_sorted_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def task(name: str) -> Callable[..., bool]:
        def run(*, force: bool = False) -> bool:
            assert force is False
            calls.append(name)
            return True

        return run

    monkeypatch.setattr(cli, "TASKS", {name: task(name) for name in ("zeta", "alpha")})
    monkeypatch.setattr(sys, "argv", ["prepare-debian"])

    assert cli.main() == 0
    assert calls == ["alpha", "zeta"]


def test_module_entrypoint_delegates_to_cli() -> None:
    with mock.patch("prepare_debian.cli.main", return_value=17) as main:
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("prepare_debian.__main__", run_name="__main__")

    assert exc_info.value.code == 17
    main.assert_called_once_with()

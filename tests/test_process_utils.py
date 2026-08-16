import subprocess
from unittest import mock

from prepare_debian.utils import process_utils


def test_run_captures_command_result() -> None:
    completed = subprocess.CompletedProcess(["tool"], 7, "out", "err")
    with mock.patch("subprocess.run", return_value=completed) as run:
        assert process_utils.run(["tool"]) is completed

    run.assert_called_once_with(
        ["tool"], check=False, text=True, capture_output=True, cwd=None
    )


def test_run_maps_command_start_error_to_none() -> None:
    with mock.patch("subprocess.run", side_effect=FileNotFoundError("missing")):
        assert process_utils.run(["missing-tool"]) is None

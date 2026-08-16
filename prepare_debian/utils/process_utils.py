import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from prepare_debian.utils import output_utils


def run(
    command: Sequence[str], cwd: Optional[Path] = None
) -> Optional[subprocess.CompletedProcess[str]]:
    try:
        return subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            cwd=cwd,
        )
    except OSError as exc:
        executable = command[0] if command else "command"
        output_utils.warn(f"Could not run {executable}: {exc}")
        return None

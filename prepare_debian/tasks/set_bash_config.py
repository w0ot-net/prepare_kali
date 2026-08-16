import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from prepare_debian.tasks import set_tools
from prepare_debian.utils import apt_utils, output_utils

BASH_CONFIG_URL = "https://github.com/w0ot-net/bash_config"


def run(
    cmd: Sequence[str], cwd: Optional[Path] = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=True,
        cwd=cwd,
    )


def ensure_bash_config_repo(force: bool = False) -> bool:
    return set_tools.ensure_repo(BASH_CONFIG_URL, force=force)


def run_install() -> bool:
    repo_dir = set_tools.repo_dir(BASH_CONFIG_URL)
    install_script = repo_dir / "install.py"
    if not install_script.exists():
        output_utils.warn(f"Missing {install_script}; cannot install bash_config.")
        return False

    result = run(["python3", str(install_script)])
    if result.returncode != 0:
        output_utils.warn(result.stderr.strip() or "bash_config install failed.")
        return False

    output_utils.ok("bash_config installed.")
    return True


def main(force: bool = False) -> None:
    apt_utils.update_apt_cache()
    apt_utils.ensure_apt_package("git", force=force)
    apt_utils.ensure_apt_package("xclip", force=force)
    if not set_tools.ensure_tools_dir():
        return
    if ensure_bash_config_repo(force=force):
        run_install()

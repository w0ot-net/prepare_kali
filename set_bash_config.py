#!/usr/bin/env python3
import subprocess
from pathlib import Path

import apt_utils
import output_utils
import set_tools


def run(cmd, cwd=None):
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)


def ensure_bash_config_repo(force=False):
    url = "https://github.com/w0ot-net/bash_config"
    return set_tools.ensure_repo(url, force=force)


def run_install():
    repo_dir = Path("/root/tools/bash_config")
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


def main(force=False):
    apt_utils.ensure_apt_package("git", force=force)
    apt_utils.ensure_apt_package("xclip", force=force)
    if not set_tools.ensure_tools_dir():
        return
    if ensure_bash_config_repo(force=force):
        run_install()


if __name__ == "__main__":
    main()

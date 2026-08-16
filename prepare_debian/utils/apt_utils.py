import shutil
import subprocess
import sys
from collections.abc import Sequence

from prepare_debian.utils import output_utils


def run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=True,
    )


def is_package_installed(package: str) -> bool:
    if shutil.which("dpkg") is None:
        output_utils.warn("dpkg not found; cannot verify package installation.")
        return False
    check = run(["dpkg", "-s", package])
    return check.returncode == 0


def update_apt_cache() -> bool:
    if shutil.which("sudo") is None or shutil.which("apt-get") is None:
        output_utils.warn("sudo or apt-get not found; cannot update package cache.")
        return False
    result = run(["sudo", "apt-get", "update"])
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return False
    return True


def ensure_apt_package(package: str, force: bool = False) -> bool:
    installed = is_package_installed(package)
    if installed and not force:
        output_utils.ok(f"{package} already installed; skipping.")
        return True

    if installed and force:
        output_utils.info(
            f"{package} already installed; reinstalling because --force was set."
        )
    else:
        output_utils.info(f"{package} not installed; attempting to install via apt.")

    if shutil.which("sudo") is None or shutil.which("apt-get") is None:
        output_utils.warn("sudo or apt-get not found; cannot install packages.")
        return False

    install = run(["sudo", "apt-get", "install", "-y", package])
    if install.returncode != 0:
        sys.stderr.write(install.stderr)
        return False

    output_utils.ok(f"{package} installed.")
    return True

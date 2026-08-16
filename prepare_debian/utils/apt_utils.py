import os
import shutil
import sys
from typing import Optional

from prepare_debian.utils import output_utils, process_utils


def is_package_installed(package: str) -> Optional[bool]:
    if shutil.which("dpkg") is None:
        output_utils.warn("dpkg not found; cannot verify package installation.")
        return None
    check = process_utils.run(["dpkg", "-s", package])
    if check is None:
        return None
    return check.returncode == 0


def apt_command(arguments: list[str]) -> Optional[list[str]]:
    if shutil.which("apt-get") is None:
        output_utils.warn("apt-get not found; cannot manage packages.")
        return None
    if os.geteuid() == 0:
        return ["apt-get", *arguments]
    if shutil.which("sudo") is None:
        output_utils.warn("sudo not found; cannot manage packages as a non-root user.")
        return None
    return ["sudo", "apt-get", *arguments]


def update_apt_cache() -> bool:
    command = apt_command(["update"])
    if command is None:
        return False
    result = process_utils.run(command)
    if result is None or result.returncode != 0:
        if result is None:
            return False
        sys.stderr.write(result.stderr)
        return False
    return True


def ensure_apt_package(package: str) -> bool:
    installed = is_package_installed(package)
    if installed is None:
        return False
    if installed:
        output_utils.ok(f"{package} already installed; skipping.")
        return True

    output_utils.info(f"{package} not installed; attempting to install via apt.")

    command = apt_command(["install", "-y", package])
    if command is None:
        return False

    install = process_utils.run(command)
    if install is None or install.returncode != 0:
        if install is None:
            return False
        sys.stderr.write(install.stderr)
        return False

    output_utils.ok(f"{package} installed.")
    return True

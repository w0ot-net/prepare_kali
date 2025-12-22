#!/usr/bin/env python3
import shutil
import subprocess
import sys


def run(cmd):
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def is_package_installed(package):
    if shutil.which("dpkg") is None:
        print("dpkg not found; cannot verify package installation.", file=sys.stderr)
        return False
    check = run(["dpkg", "-s", package])
    return check.returncode == 0


def ensure_apt_package(package, force=False):
    installed = is_package_installed(package)
    if installed and not force:
        print(f"{package} already installed; skipping.")
        return True

    if installed and force:
        print(f"{package} already installed; reinstalling because --force was set.")
    else:
        print(f"{package} not installed; attempting to install via apt.")

    if shutil.which("sudo") is None or shutil.which("apt-get") is None:
        print("sudo or apt-get not found; cannot install packages.", file=sys.stderr)
        return False

    update = run(["sudo", "apt-get", "update"])
    if update.returncode != 0:
        sys.stderr.write(update.stderr)
        return False

    install = run(["sudo", "apt-get", "install", "-y", package])
    if install.returncode != 0:
        sys.stderr.write(install.stderr)
        return False

    return True

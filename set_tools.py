#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

import apt_utils
import output_utils


TOOLS_DIR = Path("/root/tools")
REPOS = [
    "https://github.com/w0ot-net/share_sniffer",
    "https://github.com/w0ot-net/ad_spray",
    "https://github.com/w0ot-net/password_generator",
    "https://github.com/w0ot-net/url_grabber",
    "https://github.com/w0ot-net/tls_auditor",
    "https://github.com/w0ot-net/ssh_auditor",
    "https://github.com/w0ot-net/bash_config",
]


def run(cmd, cwd=None):
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)


def ensure_tools_dir():
    try:
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        output_utils.warn(f"Could not create {TOOLS_DIR}: {exc}")
        return False
    return True


def repo_dir(url):
    return TOOLS_DIR / url.rstrip("/").split("/")[-1]


def ensure_repo(url, force=False):
    path = repo_dir(url)
    if path.exists():
        git_dir = path / ".git"
        if git_dir.exists():
            if force:
                output_utils.info(f"Updating {path} (force).")
            else:
                output_utils.info(f"Updating {path}.")
            result = run(["git", "-C", str(path), "pull", "--ff-only"])
            if result.returncode != 0:
                output_utils.warn(result.stderr.strip() or f"Failed to update {path}.")
                return False
            output_utils.ok(f"Updated {path}.")
            return True

        output_utils.warn(f"{path} exists but is not a git repo; skipping.")
        return False

    output_utils.info(f"Cloning {url} into {path}.")
    result = run(["git", "clone", url, str(path)])
    if result.returncode != 0:
        output_utils.warn(result.stderr.strip() or f"Failed to clone {url}.")
        return False
    output_utils.ok(f"Cloned {url}.")
    return True


def main(force=False):
    apt_utils.ensure_apt_package("git", force=force)
    if not ensure_tools_dir():
        return
    for url in REPOS:
        ensure_repo(url, force=force)


if __name__ == "__main__":
    main()

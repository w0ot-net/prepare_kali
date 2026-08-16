from pathlib import Path

from prepare_debian.utils import output_utils, process_utils

TOOLS_DIR = Path.home() / "tools"
REPOS: list[str] = [
    "https://github.com/w0ot-net/share_sniffer",
    "https://github.com/w0ot-net/ad_spray",
    "https://github.com/w0ot-net/password_generator",
    "https://github.com/w0ot-net/tls_auditor",
    "https://github.com/w0ot-net/ssh_auditor",
    "https://github.com/w0ot-net/db_brute",
    "https://github.com/w0ot-net/service_organizer",
    "https://github.com/w0ot-net/ad_account_unlocker",
]


def ensure_tools_dir() -> bool:
    try:
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        output_utils.warn(f"Could not create {TOOLS_DIR}: {exc}")
        return False
    return True


def repo_dir(url: str) -> Path:
    return TOOLS_DIR / url.rstrip("/").split("/")[-1]


def ensure_repo(url: str) -> bool:
    path = repo_dir(url)
    if path.exists():
        git_dir = path / ".git"
        if git_dir.exists():
            output_utils.info(f"Updating {path}.")
            result = process_utils.run(["git", "-C", str(path), "pull", "--ff-only"])
            if result is None or result.returncode != 0:
                stderr = result.stderr.strip() if result is not None else ""
                output_utils.warn(stderr or f"Failed to update {path}.")
                return False
            output_utils.ok(f"Updated {path}.")
            return True

        output_utils.warn(f"{path} exists but is not a git repo; skipping.")
        return False

    output_utils.info(f"Cloning {url} into {path}.")
    result = process_utils.run(["git", "clone", url, str(path)])
    if result is None or result.returncode != 0:
        stderr = result.stderr.strip() if result is not None else ""
        output_utils.warn(stderr or f"Failed to clone {url}.")
        return False
    output_utils.ok(f"Cloned {url}.")
    return True


def main() -> bool:
    if not ensure_tools_dir():
        return False
    success = True
    for url in REPOS:
        if not ensure_repo(url):
            success = False
    return success

import subprocess
from pathlib import Path
from typing import Optional

from prepare_debian.repositories import TOOL_REPOSITORIES, RepositorySpec
from prepare_debian.utils import output_utils, process_utils

TOOLS_DIR = Path.home() / "tools"


def ensure_tools_dir(tools_dir: Path = TOOLS_DIR) -> bool:
    try:
        tools_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        output_utils.warn(f"Could not create {tools_dir}: {exc}")
        return False
    return True


def repository_path(spec: RepositorySpec, tools_dir: Path = TOOLS_DIR) -> Path:
    return tools_dir / spec.name


def _git(path: Path, *arguments: str) -> Optional[subprocess.CompletedProcess[str]]:
    return process_utils.run(["git", "-C", str(path), *arguments])


def _command_value(path: Path, *arguments: str) -> Optional[str]:
    result = _git(path, *arguments)
    if result is None or result.returncode != 0:
        stderr = result.stderr.strip() if result is not None else ""
        output_utils.warn(stderr or f"Git command failed for {path}.")
        return None
    return result.stdout.strip()


def synchronize_repository(spec: RepositorySpec, tools_dir: Path = TOOLS_DIR) -> bool:
    path = repository_path(spec, tools_dir)
    short_revision = spec.revision[:12]
    new_clone = not path.exists()

    if new_clone:
        output_utils.info(f"Cloning {spec.name} at {short_revision} into {path}.")
        clone = process_utils.run(
            ["git", "clone", "--no-checkout", spec.url, str(path)]
        )
        if clone is None or clone.returncode != 0:
            stderr = clone.stderr.strip() if clone is not None else ""
            output_utils.warn(stderr or f"Failed to clone {spec.url}.")
            return False

    worktree = _command_value(path, "rev-parse", "--is-inside-work-tree")
    if worktree != "true":
        output_utils.warn(f"{path} is not a Git worktree; refusing to modify it.")
        return False

    origin = _command_value(path, "remote", "get-url", "origin")
    if origin != spec.url:
        output_utils.warn(
            f"Origin mismatch for {path}: expected {spec.url!r}, found {origin!r}."
        )
        return False

    if not new_clone:
        status = _command_value(path, "status", "--porcelain")
        if status is None:
            return False
        if status:
            output_utils.warn(f"{path} has local changes; refusing to modify it.")
            return False

    current = _command_value(path, "rev-parse", "HEAD")
    if not new_clone and current == spec.revision:
        output_utils.ok(f"{spec.name} already pinned at {short_revision}.")
        return True

    output_utils.info(f"Synchronizing {spec.name} to {short_revision}.")
    fetch = _git(path, "fetch", "origin", spec.revision)
    if fetch is None or fetch.returncode != 0:
        stderr = fetch.stderr.strip() if fetch is not None else ""
        output_utils.warn(stderr or f"Failed to fetch {spec.name}.")
        return False

    commit = _command_value(
        path, "rev-parse", "--verify", f"{spec.revision}^{{commit}}"
    )
    if commit != spec.revision:
        output_utils.warn(
            f"Pinned commit is unavailable for {spec.name}: {spec.revision}"
        )
        return False

    checkout = _git(path, "checkout", "--detach", spec.revision)
    if checkout is None or checkout.returncode != 0:
        stderr = checkout.stderr.strip() if checkout is not None else ""
        output_utils.warn(stderr or f"Failed to check out {spec.name}.")
        return False

    final = _command_value(path, "rev-parse", "HEAD")
    if final != spec.revision:
        output_utils.warn(
            f"Revision mismatch for {spec.name}: expected {spec.revision}, "
            f"found {final}."
        )
        return False

    output_utils.ok(f"Pinned {spec.name} at {short_revision}.")
    return True


def main() -> bool:
    if not ensure_tools_dir():
        return False
    for spec in TOOL_REPOSITORIES:
        if not synchronize_repository(spec):
            return False
    return True

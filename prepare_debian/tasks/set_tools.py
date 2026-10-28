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
    new_clone = not path.exists()

    if new_clone:
        output_utils.info(f"Cloning {spec.name} into {path}.")
        clone = process_utils.run(["git", "clone", spec.url, str(path)])
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
            output_utils.warn(f"{path} has local changes; skipping its update.")
            return True

    previous = _command_value(path, "rev-parse", "HEAD")
    if previous is None:
        return False

    output_utils.info(f"Updating {spec.name} from its remote default branch.")
    fetch = _git(path, "fetch", "--prune", "origin")
    if fetch is None or fetch.returncode != 0:
        stderr = fetch.stderr.strip() if fetch is not None else ""
        output_utils.warn(stderr or f"Failed to fetch {spec.name}.")
        return False

    set_head = _git(path, "remote", "set-head", "origin", "--auto")
    if set_head is None or set_head.returncode != 0:
        stderr = set_head.stderr.strip() if set_head is not None else ""
        output_utils.warn(
            stderr or f"Could not determine the default branch for {spec.name}."
        )
        return False

    remote_ref = _command_value(
        path, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"
    )
    prefix = "origin/"
    if remote_ref is None or not remote_ref.startswith(prefix):
        output_utils.warn(f"Could not determine the default branch for {spec.name}.")
        return False
    branch = remote_ref.removeprefix(prefix)

    local_branch = _git(path, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
    if local_branch is not None and local_branch.returncode == 0:
        checkout = _git(path, "checkout", branch)
    else:
        checkout = _git(path, "checkout", "--track", "-b", branch, remote_ref)
    if checkout is None or checkout.returncode != 0:
        stderr = checkout.stderr.strip() if checkout is not None else ""
        output_utils.warn(stderr or f"Failed to check out {spec.name} branch {branch}.")
        return False

    upstream = _git(path, "branch", f"--set-upstream-to={remote_ref}", branch)
    if upstream is None or upstream.returncode != 0:
        stderr = upstream.stderr.strip() if upstream is not None else ""
        output_utils.warn(
            stderr or f"Failed to configure the upstream branch for {spec.name}."
        )
        return False

    merged = _git(path, "merge", "--ff-only", remote_ref)
    if merged is None or merged.returncode != 0:
        stderr = merged.stderr.strip() if merged is not None else ""
        output_utils.warn(
            stderr or f"Could not fast-forward {spec.name} from {remote_ref}."
        )
        return False

    final = _command_value(path, "rev-parse", "HEAD")
    remote = _command_value(path, "rev-parse", "--verify", f"{remote_ref}^{{commit}}")
    if final is None or final != remote:
        output_utils.warn(
            f"Revision mismatch for {spec.name}: expected {remote_ref}, found {final}."
        )
        return False

    if final == previous:
        output_utils.ok(f"{spec.name} already current on {branch}.")
    else:
        output_utils.ok(f"Updated {spec.name} on {branch}.")
    return True


def main() -> bool:
    if not ensure_tools_dir():
        return False
    for spec in TOOL_REPOSITORIES:
        if not synchronize_repository(spec):
            return False
    return True

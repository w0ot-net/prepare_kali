import subprocess
from pathlib import Path

from prepare_debian.repositories import RepositorySpec
from prepare_debian.tasks import set_tools


def git(*arguments: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def make_remote(tmp_path: Path) -> tuple[Path, Path, str]:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    remote.mkdir()
    seed.mkdir()
    git("init", "--bare", cwd=remote)
    git("init", cwd=seed)
    git("config", "user.name", "Test User", cwd=seed)
    git("config", "user.email", "test@example.com", cwd=seed)
    (seed / "value.txt").write_text("one\n", encoding="utf-8")
    git("add", "value.txt", cwd=seed)
    git("commit", "-m", "one", cwd=seed)
    first = git("rev-parse", "HEAD", cwd=seed)
    git("remote", "add", "origin", str(remote), cwd=seed)
    git("push", "origin", "HEAD:main", cwd=seed)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=remote)
    return remote, seed, first


def advance_remote(seed: Path, value: str) -> str:
    (seed / "value.txt").write_text(f"{value}\n", encoding="utf-8")
    git("commit", "-am", value, cwd=seed)
    revision = git("rev-parse", "HEAD", cwd=seed)
    git("push", "origin", "HEAD:main", cwd=seed)
    return revision


def spec(remote: Path) -> RepositorySpec:
    return RepositorySpec("managed", str(remote))


def head(path: Path) -> str:
    return git("rev-parse", "HEAD", cwd=path)


def test_fresh_clone_tracks_default_branch_and_is_idempotent(tmp_path: Path) -> None:
    remote, _, first = make_remote(tmp_path)
    tools = tmp_path / "tools"

    assert set_tools.synchronize_repository(spec(remote), tools) is True
    checkout = tools / "managed"
    assert head(checkout) == first
    assert git("branch", "--show-current", cwd=checkout) == "main"
    assert git("rev-parse", "--abbrev-ref", "@{upstream}", cwd=checkout) == (
        "origin/main"
    )
    assert (checkout / "value.txt").read_text(encoding="utf-8") == "one\n"
    assert set_tools.synchronize_repository(spec(remote), tools) is True


def test_existing_checkout_fast_forwards_and_supports_git_pull(tmp_path: Path) -> None:
    remote, seed, _ = make_remote(tmp_path)
    tools = tmp_path / "tools"
    assert set_tools.synchronize_repository(spec(remote), tools) is True
    checkout = tools / "managed"

    second = advance_remote(seed, "two")
    assert set_tools.synchronize_repository(spec(remote), tools) is True
    assert head(checkout) == second

    third = advance_remote(seed, "three")
    git("pull", "--ff-only", cwd=checkout)
    assert head(checkout) == third


def test_detached_checkout_is_reattached_to_default_branch(tmp_path: Path) -> None:
    remote, seed, first = make_remote(tmp_path)
    tools = tmp_path / "tools"
    assert set_tools.synchronize_repository(spec(remote), tools) is True
    checkout = tools / "managed"
    git("checkout", "--detach", first, cwd=checkout)
    second = advance_remote(seed, "two")

    assert set_tools.synchronize_repository(spec(remote), tools) is True
    assert git("branch", "--show-current", cwd=checkout) == "main"
    assert head(checkout) == second


def test_dirty_checkout_is_preserved(tmp_path: Path) -> None:
    remote, seed, first = make_remote(tmp_path)
    tools = tmp_path / "tools"
    assert set_tools.synchronize_repository(spec(remote), tools) is True
    checkout = tools / "managed"
    (checkout / "local.txt").write_text("keep\n", encoding="utf-8")
    advance_remote(seed, "two")

    assert set_tools.synchronize_repository(spec(remote), tools) is False
    assert head(checkout) == first
    assert (checkout / "local.txt").read_text(encoding="utf-8") == "keep\n"


def test_wrong_origin_leaves_head_unchanged(tmp_path: Path) -> None:
    remote, _, first = make_remote(tmp_path)
    tools = tmp_path / "tools"
    assert set_tools.synchronize_repository(spec(remote), tools) is True
    checkout = tools / "managed"

    git("remote", "set-url", "origin", str(tmp_path / "wrong.git"), cwd=checkout)
    assert set_tools.synchronize_repository(spec(remote), tools) is False
    assert head(checkout) == first


def test_diverged_branch_is_not_overwritten(tmp_path: Path) -> None:
    remote, seed, _ = make_remote(tmp_path)
    tools = tmp_path / "tools"
    assert set_tools.synchronize_repository(spec(remote), tools) is True
    checkout = tools / "managed"
    git("config", "user.name", "Test User", cwd=checkout)
    git("config", "user.email", "test@example.com", cwd=checkout)
    (checkout / "local.txt").write_text("local\n", encoding="utf-8")
    git("add", "local.txt", cwd=checkout)
    git("commit", "-m", "local", cwd=checkout)
    local = head(checkout)
    advance_remote(seed, "two")

    assert set_tools.synchronize_repository(spec(remote), tools) is False
    assert head(checkout) == local
    assert (checkout / "local.txt").read_text(encoding="utf-8") == "local\n"

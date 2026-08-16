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


def make_remote(tmp_path: Path) -> tuple[Path, str, str]:
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

    (seed / "value.txt").write_text("two\n", encoding="utf-8")
    git("commit", "-am", "two", cwd=seed)
    second = git("rev-parse", "HEAD", cwd=seed)
    git("push", "origin", "HEAD:main", cwd=seed)
    return remote, first, second


def spec(remote: Path, revision: str) -> RepositorySpec:
    return RepositorySpec("managed", str(remote), revision)


def head(path: Path) -> str:
    return git("rev-parse", "HEAD", cwd=path)


def test_fresh_clone_and_second_run_are_exact_and_idempotent(tmp_path: Path) -> None:
    remote, first, _ = make_remote(tmp_path)
    tools = tmp_path / "tools"

    assert set_tools.synchronize_repository(spec(remote, first), tools) is True
    checkout = tools / "managed"
    assert head(checkout) == first
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=checkout) == "HEAD"
    assert (checkout / "value.txt").read_text(encoding="utf-8") == "one\n"
    assert set_tools.synchronize_repository(spec(remote, first), tools) is True


def test_pin_can_advance_and_roll_back_without_reset(tmp_path: Path) -> None:
    remote, first, second = make_remote(tmp_path)
    tools = tmp_path / "tools"

    assert set_tools.synchronize_repository(spec(remote, first), tools) is True
    assert set_tools.synchronize_repository(spec(remote, second), tools) is True
    assert head(tools / "managed") == second
    assert set_tools.synchronize_repository(spec(remote, first), tools) is True
    assert head(tools / "managed") == first


def test_dirty_checkout_is_preserved(tmp_path: Path) -> None:
    remote, first, second = make_remote(tmp_path)
    tools = tmp_path / "tools"
    assert set_tools.synchronize_repository(spec(remote, first), tools) is True
    checkout = tools / "managed"
    (checkout / "local.txt").write_text("keep\n", encoding="utf-8")

    assert set_tools.synchronize_repository(spec(remote, second), tools) is False
    assert head(checkout) == first
    assert (checkout / "local.txt").read_text(encoding="utf-8") == "keep\n"


def test_wrong_origin_and_missing_revision_leave_head_unchanged(
    tmp_path: Path,
) -> None:
    remote, first, _ = make_remote(tmp_path)
    tools = tmp_path / "tools"
    assert set_tools.synchronize_repository(spec(remote, first), tools) is True
    checkout = tools / "managed"

    git("remote", "set-url", "origin", str(tmp_path / "wrong.git"), cwd=checkout)
    assert set_tools.synchronize_repository(spec(remote, first), tools) is False
    assert head(checkout) == first

    git("remote", "set-url", "origin", str(remote), cwd=checkout)
    assert set_tools.synchronize_repository(spec(remote, "0" * 40), tools) is False
    assert head(checkout) == first

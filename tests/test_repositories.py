import re

from prepare_debian.repositories import (
    BASH_CONFIG_REPOSITORY,
    TOOL_REPOSITORIES,
)


def test_production_repository_specs_are_unique_and_immutable() -> None:
    repositories = (*TOOL_REPOSITORIES, BASH_CONFIG_REPOSITORY)

    assert len(TOOL_REPOSITORIES) == 8
    assert len({repository.name for repository in repositories}) == len(repositories)
    assert len({repository.url for repository in repositories}) == len(repositories)
    assert all(
        re.fullmatch(r"[0-9a-f]{40}", repository.revision)
        for repository in repositories
    )

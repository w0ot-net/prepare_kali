from prepare_debian.repositories import (
    BASH_CONFIG_REPOSITORY,
    CODING_AGENT_HELPERS_REPOSITORY,
    TOOL_REPOSITORIES,
)


def test_production_repository_specs_are_unique() -> None:
    repositories = (
        *TOOL_REPOSITORIES,
        BASH_CONFIG_REPOSITORY,
        CODING_AGENT_HELPERS_REPOSITORY,
    )

    assert len(TOOL_REPOSITORIES) == 9
    assert any(repository.name == "nwrapper" for repository in TOOL_REPOSITORIES)
    assert len({repository.name for repository in repositories}) == len(repositories)
    assert len({repository.url for repository in repositories}) == len(repositories)

from dataclasses import dataclass


@dataclass(frozen=True)
class RepositorySpec:
    name: str
    url: str


TOOL_REPOSITORIES = (
    RepositorySpec(
        "nwrapper",
        "https://github.com/w0ot-net/nwrapper",
    ),
    RepositorySpec(
        "share_sniffer",
        "https://github.com/w0ot-net/share_sniffer",
    ),
    RepositorySpec(
        "ad_spray",
        "https://github.com/w0ot-net/ad_spray",
    ),
    RepositorySpec(
        "password_generator",
        "https://github.com/w0ot-net/password_generator",
    ),
    RepositorySpec(
        "tls_auditor",
        "https://github.com/w0ot-net/tls_auditor",
    ),
    RepositorySpec(
        "ssh_auditor",
        "https://github.com/w0ot-net/ssh_auditor",
    ),
    RepositorySpec(
        "db_brute",
        "https://github.com/w0ot-net/db_brute",
    ),
    RepositorySpec(
        "service_organizer",
        "https://github.com/w0ot-net/service_organizer",
    ),
    RepositorySpec(
        "ad_account_unlocker",
        "https://github.com/w0ot-net/ad_account_unlocker",
    ),
)

BASH_CONFIG_REPOSITORY = RepositorySpec(
    "bash_config",
    "https://github.com/w0ot-net/bash_config",
)

CODING_AGENT_HELPERS_REPOSITORY = RepositorySpec(
    "coding_agent_helpers",
    "https://github.com/w0ot-net/coding_agent_helpers",
)

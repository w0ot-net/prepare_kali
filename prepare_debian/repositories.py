from dataclasses import dataclass


@dataclass(frozen=True)
class RepositorySpec:
    name: str
    url: str
    revision: str


TOOL_REPOSITORIES = (
    RepositorySpec(
        "share_sniffer",
        "https://github.com/w0ot-net/share_sniffer",
        "9f1572ab93dd9becd6039a5fc022b0a46ac0b7d9",
    ),
    RepositorySpec(
        "ad_spray",
        "https://github.com/w0ot-net/ad_spray",
        "188cf4da512a16749505503225d6b35497dbabd5",
    ),
    RepositorySpec(
        "password_generator",
        "https://github.com/w0ot-net/password_generator",
        "654aa025ab387e11edea62627715786d06a94214",
    ),
    RepositorySpec(
        "tls_auditor",
        "https://github.com/w0ot-net/tls_auditor",
        "ae3c31e4b90250325f76259819dc3ed96c9e7373",
    ),
    RepositorySpec(
        "ssh_auditor",
        "https://github.com/w0ot-net/ssh_auditor",
        "7f9a27b05d1f5aed373c41e505321f5bb2d6dbaa",
    ),
    RepositorySpec(
        "db_brute",
        "https://github.com/w0ot-net/db_brute",
        "4746b3b8effc50b71f811dffc36e5dd8bcea49e5",
    ),
    RepositorySpec(
        "service_organizer",
        "https://github.com/w0ot-net/service_organizer",
        "984eb08faada5cdba3a0f9a0d8718f4b1473b1e3",
    ),
    RepositorySpec(
        "ad_account_unlocker",
        "https://github.com/w0ot-net/ad_account_unlocker",
        "d404360e3b7c030e49944d21d8db01a3cfae1c0e",
    ),
)

BASH_CONFIG_REPOSITORY = RepositorySpec(
    "bash_config",
    "https://github.com/w0ot-net/bash_config",
    "bb3eb930c26dea2a0c1db5b68e7e9fbf7c7e9f38",
)

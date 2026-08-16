from prepare_debian.utils import apt_utils

PACKAGES: list[str] = [
    "git",
    "python3-impacket",
    "python3-paramiko",
    "python3-psycopg2",
    "python3-pymssql",
    "python3-pymysql",
]


def main() -> bool:
    if not apt_utils.update_apt_cache():
        return False
    for package in PACKAGES:
        if not apt_utils.ensure_apt_package(package):
            return False
    return True

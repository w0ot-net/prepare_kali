#!/usr/bin/env python3
from utils import apt_utils


PACKAGES = [
    "python3-paramiko",
    "python3-psycopg2",
    "python3-pymssql",
    "python3-pymysql",
]


def main(force=False):
    for package in PACKAGES:
        if not apt_utils.ensure_apt_package(package, force=force):
            return False
    return True


if __name__ == "__main__":
    main()

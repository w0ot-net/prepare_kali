from prepare_debian.utils import apt_utils

PACKAGES: list[str] = [
    "accountsservice",
    "git",
    "impacket-scripts",
    "kali-root-login",
    "masscan",
    "open-vm-tools",
    "open-vm-tools-desktop",
    "proxychains4",
    "python3-impacket",
    "python3-paramiko",
    "python3-psycopg2",
    "python3-pymssql",
    "python3-pymysql",
    "snmp",
    "ssh",
    "tailscale",
    "virtualbox-guest-x11",
    "vim",
]


def main() -> bool:
    if not apt_utils.update_apt_cache():
        return False
    for package in PACKAGES:
        if not apt_utils.ensure_apt_package(package):
            return False
    return True

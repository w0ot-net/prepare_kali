import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Optional

from prepare_debian.utils import apt_utils, output_utils

ROOT_LOGIN_PACKAGES = ("accountsservice", "kali-root-login")
ACCOUNTS_SERVICE_PATH = Path("/var/lib/AccountsService/users/root")
LIGHTDM_CONFIG_PATH = Path(
    "/etc/lightdm/lightdm.conf.d/99-prepare-debian-root-login.conf"
)
LIGHTDM_CONFIG = """[Seat:*]
greeter-hide-users=false
greeter-show-manual-login=true
"""


def render_accounts_service_user(content: str) -> str:
    lines = content.splitlines(keepends=True)
    section_pattern = re.compile(r"^\s*\[([^]]+)]\s*(?:[;#].*)?$")
    user_sections = [
        index
        for index, line in enumerate(lines)
        if (match := section_pattern.match(line.rstrip("\r\n")))
        and match.group(1).strip().casefold() == "user"
    ]
    if len(user_sections) > 1:
        raise ValueError(
            "AccountsService root file contains duplicate [User] sections."
        )

    if not user_sections:
        separator = ""
        if content:
            separator = "\n" if content.endswith(("\n", "\r")) else "\n\n"
        return f"{content}{separator}[User]\nSystemAccount=false\n"

    section_start = user_sections[0]
    section_end = next(
        (
            index
            for index in range(section_start + 1, len(lines))
            if section_pattern.match(lines[index].rstrip("\r\n"))
        ),
        len(lines),
    )
    setting_pattern = re.compile(r"^\s*SystemAccount\s*=", re.IGNORECASE)
    settings = [
        index
        for index in range(section_start + 1, section_end)
        if setting_pattern.match(lines[index])
    ]
    if len(settings) > 1:
        raise ValueError(
            "AccountsService root file contains duplicate SystemAccount values."
        )

    if settings:
        index = settings[0]
        ending = "\r\n" if lines[index].endswith("\r\n") else "\n"
        if not lines[index].endswith(("\n", "\r")):
            ending = ""
        indentation = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
        lines[index] = f"{indentation}SystemAccount=false{ending}"
        return "".join(lines)

    if section_end > 0 and not lines[section_end - 1].endswith(("\n", "\r")):
        lines[section_end - 1] += "\n"
    lines.insert(section_end, "SystemAccount=false\n")
    return "".join(lines)


def _write_config(path: Path, content: str, default_mode: int) -> bool:
    temporary_path: Optional[Path] = None
    try:
        if path.exists():
            current = path.read_text(encoding="utf-8")
            if current == content:
                return True
            mode = stat.S_IMODE(path.stat().st_mode)
        else:
            mode = default_mode

        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        temporary_path.chmod(mode)
        os.replace(temporary_path, path)
        temporary_path = None
        return path.read_text(encoding="utf-8") == content
    except OSError as exc:
        output_utils.warn(f"Could not configure root on the login screen: {exc}")
        return False
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def configure_login_screen(
    accounts_path: Path = ACCOUNTS_SERVICE_PATH,
    lightdm_path: Path = LIGHTDM_CONFIG_PATH,
) -> bool:
    try:
        accounts_content = (
            accounts_path.read_text(encoding="utf-8") if accounts_path.exists() else ""
        )
        rendered_accounts = render_accounts_service_user(accounts_content)
    except (OSError, ValueError) as exc:
        output_utils.warn(f"Could not configure root on the login screen: {exc}")
        return False

    if not _write_config(accounts_path, rendered_accounts, 0o600):
        return False
    if not _write_config(lightdm_path, LIGHTDM_CONFIG, 0o644):
        return False

    output_utils.ok("Configured root as a selectable LightDM login user.")
    return True


def main() -> bool:
    if os.geteuid() != 0:
        output_utils.warn(
            "Configuring graphical root login requires effective root privileges."
        )
        return False

    missing_packages: list[str] = []
    for package in ROOT_LOGIN_PACKAGES:
        installed = apt_utils.is_package_installed(package)
        if installed is None:
            return False
        if not installed:
            missing_packages.append(package)

    if missing_packages:
        if not apt_utils.update_apt_cache():
            return False
        for package in missing_packages:
            if not apt_utils.ensure_apt_package(package):
                return False

    return configure_login_screen()

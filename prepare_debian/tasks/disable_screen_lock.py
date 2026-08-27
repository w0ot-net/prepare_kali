import os
import stat
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Optional

from prepare_debian.utils import output_utils, process_utils

GNOME_SETTINGS = (
    ("org.gnome.desktop.session", "idle-delay", "uint32 0"),
    ("org.gnome.desktop.screensaver", "lock-enabled", "false"),
)

GNOME_SYSTEM_SETTINGS_PATH = Path(
    "/etc/dconf/db/local.d/99-prepare-debian-disable-screen-lock"
)
GNOME_SYSTEM_LOCKS_PATH = Path(
    "/etc/dconf/db/local.d/locks/99-prepare-debian-disable-screen-lock"
)
GNOME_DCONF_PROFILE_PATH = Path("/etc/dconf/profile/user")
GNOME_DCONF_PROFILE_ENTRIES = ("user-db:user", "system-db:local")
GNOME_SYSTEM_SETTINGS = """[org/gnome/desktop/session]
idle-delay=uint32 0

[org/gnome/desktop/screensaver]
lock-enabled=false
"""
GNOME_SYSTEM_LOCKS = """/org/gnome/desktop/session/idle-delay
/org/gnome/desktop/screensaver/lock-enabled
"""

XFCE_SETTINGS = (
    ("xfce4-screensaver", "/saver/enabled"),
    ("xfce4-screensaver", "/saver/idle-activation/enabled"),
    ("xfce4-screensaver", "/lock/enabled"),
    ("xfce4-screensaver", "/lock/saver-activation/enabled"),
    ("xfce4-screensaver", "/lock/sleep-activation"),
    ("xfce4-power-manager", "/xfce4-power-manager/dpms-enabled"),
    (
        "xfce4-power-manager",
        "/xfce4-power-manager/lock-screen-suspend-hibernate",
    ),
    ("xfce4-session", "/shutdown/LockScreen"),
)

XFCE_X11_COMMANDS = (
    ("xset", "s", "off"),
    ("xset", "s", "noblank"),
    ("xset", "-dpms"),
)


def detect_desktop(environ: Mapping[str, str]) -> Optional[str]:
    desktop = environ.get("XDG_CURRENT_DESKTOP")
    if not desktop:
        desktop = environ.get("DESKTOP_SESSION", "")
    tokens = {token.casefold() for token in desktop.split(":") if token}
    matches = set()
    if any("gnome" in token for token in tokens):
        matches.add("gnome")
    if any("xfce" in token for token in tokens):
        matches.add("xfce")
    if len(matches) != 1:
        return None
    return matches.pop()


def _successful(result: Optional[subprocess.CompletedProcess[str]]) -> bool:
    return result is not None and result.returncode == 0


def configure_gnome() -> bool:
    for schema, key, desired in GNOME_SETTINGS:
        current = process_utils.run(["gsettings", "get", schema, key])
        if _successful(current) and current is not None:
            if current.stdout.strip() == desired:
                output_utils.ok(f"GNOME setting already configured: {schema} {key}")
                continue

        updated = process_utils.run(["gsettings", "set", schema, key, desired])
        if not _successful(updated):
            stderr = updated.stderr.strip() if updated is not None else ""
            output_utils.warn(stderr or f"Could not set GNOME setting {schema} {key}.")
            return False

        verified = process_utils.run(["gsettings", "get", schema, key])
        if not _successful(verified) or verified is None:
            output_utils.warn(f"Could not verify GNOME setting {schema} {key}.")
            return False
        if verified.stdout.strip() != desired:
            output_utils.warn(f"GNOME setting did not persist: {schema} {key}.")
            return False
        output_utils.ok(f"Disabled GNOME idle behavior: {schema} {key}")
    return True


def _write_policy_file(path: Path, content: str) -> bool:
    try:
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return True

        path.parent.mkdir(parents=True, exist_ok=True)
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
        temporary_path: Optional[Path] = None
        try:
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
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return path.read_text(encoding="utf-8") == content
    except OSError as exc:
        output_utils.warn(f"Could not write GNOME system policy {path}: {exc}")
        return False


def _ensure_dconf_profile(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        output_utils.warn(f"Could not read GNOME dconf profile {path}: {exc}")
        return False

    existing = {line.strip() for line in content.splitlines()}
    missing = [entry for entry in GNOME_DCONF_PROFILE_ENTRIES if entry not in existing]
    if not missing:
        return True

    separator = "" if not content or content.endswith("\n") else "\n"
    additions = "\n".join(missing)
    return _write_policy_file(path, f"{content}{separator}{additions}\n")


def configure_gnome_system(
    settings_path: Path = GNOME_SYSTEM_SETTINGS_PATH,
    locks_path: Path = GNOME_SYSTEM_LOCKS_PATH,
    profile_path: Path = GNOME_DCONF_PROFILE_PATH,
) -> bool:
    if not _ensure_dconf_profile(profile_path):
        return False
    if not _write_policy_file(settings_path, GNOME_SYSTEM_SETTINGS):
        return False
    if not _write_policy_file(locks_path, GNOME_SYSTEM_LOCKS):
        return False

    updated = process_utils.run(["dconf", "update"])
    if not _successful(updated):
        stderr = updated.stderr.strip() if updated is not None else ""
        output_utils.warn(stderr or "Could not update the GNOME system dconf database.")
        return False

    for schema, key, desired in GNOME_SETTINGS:
        value = process_utils.run(["gsettings", "get", schema, key])
        writable = process_utils.run(["gsettings", "writable", schema, key])
        if not _successful(value) or value is None:
            output_utils.warn(f"Could not verify GNOME system setting {schema} {key}.")
            return False
        if value.stdout.strip() != desired:
            output_utils.warn(f"GNOME system setting did not persist: {schema} {key}.")
            return False
        if not _successful(writable) or writable is None:
            output_utils.warn(f"Could not verify GNOME system lock {schema} {key}.")
            return False
        if writable.stdout.strip().casefold() != "false":
            output_utils.warn(f"GNOME system setting is not locked: {schema} {key}.")
            return False

    output_utils.ok(
        "Disabled GNOME idle locking and blanking for all users with a locked "
        "system policy."
    )
    return True


def configure_xfce() -> bool:
    for channel, property_name in XFCE_SETTINGS:
        query = [
            "xfconf-query",
            "--channel",
            channel,
            "--property",
            property_name,
        ]
        current = process_utils.run(query)
        if _successful(current) and current is not None:
            if current.stdout.strip().casefold() == "false":
                output_utils.ok(
                    f"XFCE setting already configured: {channel} {property_name}"
                )
                continue
            update = [*query, "--set", "false"]
        else:
            update = [*query, "--create", "--type", "bool", "--set", "false"]

        updated = process_utils.run(update)
        if not _successful(updated):
            stderr = updated.stderr.strip() if updated is not None else ""
            output_utils.warn(
                stderr or f"Could not set XFCE setting {channel} {property_name}."
            )
            return False

        verified = process_utils.run(query)
        if not _successful(verified) or verified is None:
            output_utils.warn(
                f"Could not verify XFCE setting {channel} {property_name}."
            )
            return False
        if verified.stdout.strip().casefold() != "false":
            output_utils.warn(
                f"XFCE setting did not persist: {channel} {property_name}."
            )
            return False
        output_utils.ok(f"Disabled XFCE idle behavior: {channel} {property_name}")

    for command in XFCE_X11_COMMANDS:
        updated = process_utils.run(command)
        if not _successful(updated):
            stderr = updated.stderr.strip() if updated is not None else ""
            output_utils.warn(stderr or f"Could not run {' '.join(command)}.")
            return False
    output_utils.ok("Disabled the active X11 screensaver and DPMS timers.")

    status = process_utils.run(["xfce4-screensaver-command", "--query"])
    if not _successful(status):
        output_utils.ok("XFCE screensaver is not running; no reset needed.")
        return True

    reset = process_utils.run(["xfce4-screensaver-command", "--deactivate", "--poke"])
    if not _successful(reset):
        stderr = reset.stderr.strip() if reset is not None else ""
        output_utils.warn(stderr or "Could not reset the XFCE screensaver state.")
        return False
    output_utils.ok("Deactivated and reset the XFCE screensaver state.")
    return True


def main() -> bool:
    desktop = detect_desktop(os.environ)
    if desktop == "gnome":
        if os.geteuid() == 0:
            return configure_gnome_system()
        return configure_gnome()
    if desktop == "xfce":
        return configure_xfce()
    output_utils.warn(
        "Could not identify GNOME or XFCE. Run this task as the intended user "
        "from a terminal inside the graphical session."
    )
    return False

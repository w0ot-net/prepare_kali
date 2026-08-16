import os
import subprocess
from collections.abc import Mapping
from typing import Optional

from prepare_debian.utils import output_utils, process_utils

GNOME_SETTINGS = (
    ("org.gnome.desktop.session", "idle-delay", "uint32 0"),
    ("org.gnome.desktop.screensaver", "lock-enabled", "false"),
)

XFCE_SETTINGS = (
    ("xfce4-screensaver", "/saver/idle-activation/enabled"),
    ("xfce4-screensaver", "/lock/saver-activation/enabled"),
    ("xfce4-power-manager", "/xfce4-power-manager/dpms-enabled"),
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
    return True


def main() -> bool:
    desktop = detect_desktop(os.environ)
    if desktop == "gnome":
        return configure_gnome()
    if desktop == "xfce":
        return configure_xfce()
    output_utils.warn(
        "Could not identify GNOME or XFCE. Run this task as the intended user "
        "from a terminal inside the graphical session."
    )
    return False

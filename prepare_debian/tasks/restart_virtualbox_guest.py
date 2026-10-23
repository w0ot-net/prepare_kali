import os
import re
import shutil
import time
from pathlib import Path
from typing import Optional

from prepare_debian.tasks.disable_virtualbox_drag_and_drop import (
    VBOX_XSESSION_PATH,
    detect_virtualbox,
)
from prepare_debian.utils import output_utils, process_utils

SERVICE_UNITS = (
    "virtualbox-guest-utils.service",
    "vboxadd-service.service",
)
EXCLUDED_CLIENT_MODES = {"draganddrop", "wayland"}
VBOX_CLIENT_PATTERN = re.compile(
    r"(?:^|\s)(?:/usr/bin/)?VBoxClient\s+--([A-Za-z0-9-]+)"
)


def discover_client_modes(path: Path = VBOX_XSESSION_PATH) -> Optional[tuple[str, ...]]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        output_utils.warn(f"Could not read VirtualBox session launcher {path}: {exc}")
        return None

    modes: list[str] = []
    for line in content.splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = VBOX_CLIENT_PATTERN.search(line)
        if match is None:
            continue
        mode = match.group(1)
        if mode in EXCLUDED_CLIENT_MODES or mode in modes:
            continue
        modes.append(mode)

    if not modes:
        output_utils.warn(f"No non-drag-and-drop VBoxClient modes found in {path}.")
        return None
    return tuple(modes)


def restart_services() -> bool:
    if shutil.which("systemctl") is None:
        output_utils.warn("systemctl not found; cannot restart VirtualBox services.")
        return False

    if os.geteuid() == 0:
        prefix: list[str] = []
    else:
        if shutil.which("sudo") is None:
            output_utils.warn(
                "sudo not found; cannot restart VirtualBox services as a non-root user."
            )
            return False
        prefix = ["sudo"]

    restarted: list[str] = []
    for unit in SERVICE_UNITS:
        exists = process_utils.run(["systemctl", "cat", unit])
        if exists is None:
            return False
        if exists.returncode != 0:
            continue

        result = process_utils.run([*prefix, "systemctl", "restart", unit])
        if result is None or result.returncode != 0:
            stderr = result.stderr.strip() if result is not None else ""
            output_utils.warn(stderr or f"Could not restart {unit}.")
            return False
        restarted.append(unit)

    if restarted:
        output_utils.ok(f"Restarted VirtualBox services: {', '.join(restarted)}.")
    else:
        output_utils.warn(
            "No supported VirtualBox guest service unit was found; continuing with "
            "the desktop clients."
        )
    return True


def restart_clients(
    home: Optional[Path] = None,
    uid: Optional[int] = None,
    launcher_path: Path = VBOX_XSESSION_PATH,
) -> bool:
    modes = discover_client_modes(launcher_path)
    if modes is None:
        return False

    executable = shutil.which("VBoxClient")
    if executable is None:
        output_utils.warn("VBoxClient not found; cannot restart desktop services.")
        return False

    if home is None:
        home = Path.home()
    if uid is None:
        uid = os.getuid()

    stopped = process_utils.run(["pkill", "-u", str(uid), "-x", "VBoxClient"])
    if stopped is None or stopped.returncode not in (0, 1):
        stderr = stopped.stderr.strip() if stopped is not None else ""
        output_utils.warn(stderr or "Could not stop the current VBoxClient processes.")
        return False

    time.sleep(1)
    try:
        for pid_file in home.glob(".vboxclient-*.pid"):
            pid_file.unlink()
    except OSError as exc:
        output_utils.warn(f"Could not remove a stale VBoxClient PID file: {exc}")
        return False

    for mode in modes:
        result = process_utils.run([executable, f"--{mode}"])
        if result is None or result.returncode != 0:
            stderr = result.stderr.strip() if result is not None else ""
            output_utils.warn(stderr or f"Could not start VBoxClient --{mode}.")
            return False

    output_utils.ok(
        "Restarted VirtualBox desktop clients without drag and drop: "
        f"{', '.join(modes)}."
    )
    return True


def main() -> bool:
    virtualbox = detect_virtualbox()
    if virtualbox is None:
        return False
    if not virtualbox:
        output_utils.ok("This system is not a VirtualBox guest; skipping.")
        return True

    if os.geteuid() == 0 and os.environ.get("SUDO_UID") not in (None, "0"):
        output_utils.warn(
            "Run this task as the logged-in desktop user, without sudo; it will use "
            "sudo only for the system service restart."
        )
        return False

    if os.environ.get("XDG_SESSION_TYPE", "").casefold() == "wayland" or os.environ.get(
        "WAYLAND_DISPLAY"
    ):
        output_utils.warn(
            "VirtualBox combines clipboard and drag-and-drop in its Wayland client, "
            "so this no-drag-and-drop restart helper supports X11 sessions only."
        )
        return False
    if not os.environ.get("DISPLAY"):
        output_utils.warn(
            "No X11 desktop session detected; run this task from a terminal inside "
            "the graphical session."
        )
        return False

    if not restart_services():
        return False
    return restart_clients()

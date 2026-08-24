import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from prepare_debian.utils import output_utils, process_utils

VBOX_XSESSION_PATH = Path("/etc/X11/Xsession.d/98vboxadd-xclient")
DRAG_AND_DROP_COMMAND = "/usr/bin/VBoxClient --draganddrop || true"
WAYLAND_COMMAND = "/usr/bin/VBoxClient --wayland || true"
DRAG_AND_DROP_COMMENT = "# prepare_debian: VirtualBox drag and drop disabled."
WAYLAND_COMMENT = (
    "# prepare_debian: VirtualBox Wayland client disabled because it includes "
    "drag and drop."
)
CLIENT_PATTERNS = (
    ("drag-and-drop", r"^/usr/bin/VBoxClient --draganddrop$"),
    ("Wayland", r"^/usr/bin/VBoxClient --wayland$"),
)


def _successful(result: Optional[subprocess.CompletedProcess[str]]) -> bool:
    return result is not None and result.returncode == 0


def detect_virtualbox() -> Optional[bool]:
    result = process_utils.run(["systemd-detect-virt", "--vm"])
    if result is None:
        return None
    if result.returncode != 0:
        return False
    return result.stdout.strip().casefold() == "oracle"


def render_launcher(content: str) -> str:
    lines = content.splitlines(keepends=True)
    rendered: list[str] = []

    for line in lines:
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        stripped = body.strip()
        indentation = body[: len(body) - len(body.lstrip())]

        if stripped == DRAG_AND_DROP_COMMAND:
            rendered.append(f"{indentation}{DRAG_AND_DROP_COMMENT}{ending}")
            continue
        if stripped == WAYLAND_COMMAND:
            separator = ending or "\n"
            rendered.append(f"{indentation}{WAYLAND_COMMENT}{separator}")
            rendered.append(f"{indentation}true{ending}")
            continue
        if not stripped.startswith("#") and "VBoxClient" in stripped:
            if "--draganddrop" in stripped or "--wayland" in stripped:
                raise ValueError(
                    "Unexpected active VBoxClient drag-and-drop command in launcher."
                )
        rendered.append(line)

    return "".join(rendered)


def configure_launcher(path: Path = VBOX_XSESSION_PATH) -> bool:
    if not path.exists():
        output_utils.ok(
            "VirtualBox Guest Additions session launcher is not installed; skipping."
        )
        return True

    temporary_path: Optional[Path] = None
    try:
        content = path.read_text(encoding="utf-8")
        rendered = render_launcher(content)
        if rendered == content:
            output_utils.ok("VirtualBox drag and drop is already disabled at login.")
            return True

        mode = stat.S_IMODE(path.stat().st_mode)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary.write(rendered)
            temporary_path = Path(temporary.name)
        temporary_path.chmod(mode)

        checked = process_utils.run(["/bin/sh", "-n", str(temporary_path)])
        if not _successful(checked):
            stderr = checked.stderr.strip() if checked is not None else ""
            output_utils.warn(
                stderr or "Updated VirtualBox session launcher did not pass sh -n."
            )
            return False

        os.replace(temporary_path, path)
        temporary_path = None
        installed = path.read_text(encoding="utf-8")
        if installed != rendered or render_launcher(installed) != installed:
            output_utils.warn("Could not verify the VirtualBox session launcher.")
            return False
        output_utils.ok("Disabled VirtualBox drag and drop at login.")
        return True
    except (OSError, ValueError) as exc:
        output_utils.warn(f"Could not disable VirtualBox drag and drop: {exc}")
        return False
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def stop_clients() -> bool:
    stopped: list[str] = []
    for name, pattern in CLIENT_PATTERNS:
        result = process_utils.run(["pkill", "-f", pattern])
        if result is None or result.returncode not in (0, 1):
            stderr = result.stderr.strip() if result is not None else ""
            output_utils.warn(stderr or f"Could not stop the VirtualBox {name} client.")
            return False
        if result.returncode == 0:
            stopped.append(name)

    if stopped:
        output_utils.ok(f"Stopped active VirtualBox clients: {', '.join(stopped)}.")
    else:
        output_utils.ok("No VirtualBox drag-and-drop clients are running.")
    return True


def main() -> bool:
    virtualbox = detect_virtualbox()
    if virtualbox is None:
        return False
    if not virtualbox:
        output_utils.ok("This system is not a VirtualBox guest; skipping.")
        return True
    if os.geteuid() != 0:
        output_utils.warn(
            "Disabling VirtualBox drag and drop requires effective root privileges."
        )
        return False
    if not configure_launcher():
        return False
    return stop_clients()

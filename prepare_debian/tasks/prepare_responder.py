import re
import stat
from pathlib import Path

from prepare_debian.utils import apt_utils, output_utils

RESPONDER_PACKAGE = "responder"
RESPONDER_CONFIG = Path("/etc/responder/Responder.conf")
SERVER_BLOCK_MARKER = "servers to start"
SERVER_SETTING = re.compile(
    r"^(\s*[A-Za-z0-9_-]+\s*=\s*)(?:On|Off)(\s*)$",
    re.IGNORECASE,
)


def render_server_profile(config: str, enabled: bool) -> str:
    lines = config.splitlines(keepends=True)
    in_server_block = False
    changed = 0
    value = "On" if enabled else "Off"

    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        stripped = body.strip()

        if not in_server_block:
            marker = stripped.lstrip(";#").strip().casefold()
            if marker == SERVER_BLOCK_MARKER:
                in_server_block = True
            continue

        match = SERVER_SETTING.fullmatch(body)
        if match is not None:
            lines[index] = f"{match.group(1)}{value}{match.group(2)}{ending}"
            changed += 1
            continue

        if changed and (not stripped or stripped.startswith((";", "#", "["))):
            break

    if not in_server_block or changed == 0:
        raise ValueError("Responder server settings block was not found.")
    return "".join(lines)


def profile_path(config_path: Path, enabled: bool) -> Path:
    state = "on" if enabled else "off"
    return config_path.with_name(f"{config_path.name}.servers-{state}")


def create_profiles(config_path: Path = RESPONDER_CONFIG) -> bool:
    try:
        config = config_path.read_text(encoding="utf-8")
        mode = stat.S_IMODE(config_path.stat().st_mode)
        for enabled in (True, False):
            destination = profile_path(config_path, enabled)
            rendered = render_server_profile(config, enabled)
            if destination.exists():
                existing = destination.read_text(encoding="utf-8")
                if existing == rendered:
                    output_utils.ok(
                        f"Responder profile already configured: {destination}"
                    )
                    continue
            destination.write_text(rendered, encoding="utf-8")
            destination.chmod(mode)
            output_utils.ok(f"Created Responder profile: {destination}")
    except (OSError, ValueError) as exc:
        output_utils.warn(f"Could not create Responder profiles: {exc}")
        return False
    return True


def main() -> bool:
    installed = apt_utils.is_package_installed(RESPONDER_PACKAGE)
    if installed is None:
        return False
    if not installed:
        available = apt_utils.is_package_available(RESPONDER_PACKAGE)
        if available is None:
            return False
        if not available:
            output_utils.ok("responder is not available from apt; skipping.")
            return True
        if not apt_utils.ensure_apt_package(RESPONDER_PACKAGE):
            return False

    return create_profiles()

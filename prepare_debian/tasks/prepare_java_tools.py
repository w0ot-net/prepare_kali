import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from prepare_debian.utils import apt_utils, output_utils

DOWNLOAD_USER_AGENT = "prepare-debian"
MANAGED_LAUNCHER_MARKER = "# Managed by prepare_debian."


@dataclass(frozen=True)
class JavaToolSpec:
    name: str
    repository: str
    asset_pattern: str
    jar_path: Path
    launcher_path: Path


@dataclass(frozen=True)
class Release:
    tag: str
    download_url: str


JAVA_TOOLS = (
    JavaToolSpec(
        name="beanshooter",
        repository="qtc-de/beanshooter",
        asset_pattern=r"beanshooter-.+-jar-with-dependencies\.jar",
        jar_path=Path("/opt/beanshooter.jar"),
        launcher_path=Path("/usr/local/bin/beanshooter"),
    ),
    JavaToolSpec(
        name="ysoserial",
        repository="frohoff/ysoserial",
        asset_pattern=r"ysoserial-all\.jar",
        jar_path=Path("/opt/yso.jar"),
        launcher_path=Path("/usr/local/bin/ysoserial"),
    ),
)


def latest_release(spec: JavaToolSpec) -> Optional[Release]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{spec.repository}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": DOWNLOAD_USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload: Any = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        output_utils.warn(f"Could not query the latest {spec.name} release: {exc}")
        return None

    if not isinstance(payload, dict) or not isinstance(payload.get("tag_name"), str):
        output_utils.warn(f"GitHub returned invalid release data for {spec.name}.")
        return None

    assets = payload.get("assets")
    if not isinstance(assets, list):
        output_utils.warn(f"GitHub returned no release assets for {spec.name}.")
        return None

    matches = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if (
            isinstance(name, str)
            and isinstance(url, str)
            and re.fullmatch(spec.asset_pattern, name)
        ):
            matches.append(url)

    if len(matches) != 1:
        output_utils.warn(
            f"Expected one {spec.name} release JAR, found {len(matches)}."
        )
        return None
    return Release(payload["tag_name"], matches[0])


def _version_path(jar_path: Path) -> Path:
    return jar_path.with_suffix(f"{jar_path.suffix}.version")


def _installed_version(jar_path: Path) -> Optional[str]:
    version_path = _version_path(jar_path)
    try:
        if not jar_path.is_file() or not version_path.is_file():
            return None
        return version_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def install_release(spec: JavaToolSpec, release: Release) -> bool:
    if _installed_version(spec.jar_path) == release.tag:
        output_utils.ok(f"{spec.name} {release.tag} already installed; skipping.")
        return True

    output_utils.info(f"Downloading {spec.name} {release.tag}.")
    request = urllib.request.Request(
        release.download_url,
        headers={"User-Agent": DOWNLOAD_USER_AGENT},
    )
    temporary_path: Optional[Path] = None
    try:
        spec.jar_path.parent.mkdir(parents=True, exist_ok=True)
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            tempfile.NamedTemporaryFile(
                "wb",
                dir=spec.jar_path.parent,
                prefix=f".{spec.jar_path.name}.",
                delete=False,
            ) as temporary_file,
        ):
            shutil.copyfileobj(response, temporary_file)
            temporary_path = Path(temporary_file.name)

        if not zipfile.is_zipfile(temporary_path):
            output_utils.warn(f"Downloaded {spec.name} release is not a valid JAR.")
            temporary_path.unlink(missing_ok=True)
            return False

        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, spec.jar_path)
        _version_path(spec.jar_path).write_text(f"{release.tag}\n", encoding="utf-8")
    except (OSError, urllib.error.URLError) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        output_utils.warn(f"Could not install {spec.name}: {exc}")
        return False

    output_utils.ok(f"Installed {spec.name} {release.tag} at {spec.jar_path}.")
    return True


def ensure_launcher(spec: JavaToolSpec) -> bool:
    content = (
        f'#!/bin/sh\n{MANAGED_LAUNCHER_MARKER}\nexec java -jar "{spec.jar_path}" "$@"\n'
    )
    try:
        if spec.launcher_path.exists():
            current = spec.launcher_path.read_text(encoding="utf-8")
            if current != content and MANAGED_LAUNCHER_MARKER not in current:
                output_utils.warn(
                    f"Preserving unmanaged launcher: {spec.launcher_path}"
                )
                return False
            if current == content and os.access(spec.launcher_path, os.X_OK):
                output_utils.ok(
                    f"{spec.name} launcher already installed at {spec.launcher_path}."
                )
                return True

        spec.launcher_path.parent.mkdir(parents=True, exist_ok=True)
        spec.launcher_path.write_text(content, encoding="utf-8")
        spec.launcher_path.chmod(0o755)
    except OSError as exc:
        output_utils.warn(f"Could not install {spec.name} launcher: {exc}")
        return False

    output_utils.ok(f"Installed {spec.name} launcher at {spec.launcher_path}.")
    return True


def main() -> bool:
    if os.geteuid() != 0:
        output_utils.warn("Installing Java tools under /opt requires root privileges.")
        return False
    if not apt_utils.ensure_apt_package("default-jre-headless"):
        return False
    if shutil.which("java") is None:
        output_utils.warn(
            "Java is not available after installing default-jre-headless."
        )
        return False

    for spec in JAVA_TOOLS:
        release = latest_release(spec)
        if release is None or not install_release(spec, release):
            return False
        if not ensure_launcher(spec):
            return False
    return True

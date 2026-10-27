import json
import os
import re
import shlex
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from prepare_debian.tasks import configure_agents, set_tools
from prepare_debian.utils import apt_utils, output_utils

JAVA_PACKAGE = "default-jre-headless"
DOWNLOAD_USER_AGENT = "prepare-debian"
MANAGED_LAUNCHER_MARKER = "# Managed by prepare_debian prepare_java_tools."
YSOSERIAL_COMPATIBILITY_LINK = Path("/opt/yso.jar")


@dataclass(frozen=True)
class JavaToolSpec:
    name: str
    repository: str
    asset_pattern: str
    directory_name: str
    jar_name: str


@dataclass(frozen=True)
class Release:
    tag: str
    download_url: str


JAVA_TOOLS = (
    JavaToolSpec(
        name="beanshooter",
        repository="qtc-de/beanshooter",
        asset_pattern=r"beanshooter-.+-jar-with-dependencies\.jar",
        directory_name="beanshooter",
        jar_name="beanshooter.jar",
    ),
    JavaToolSpec(
        name="ysoserial",
        repository="frohoff/ysoserial",
        asset_pattern=r"ysoserial-all\.jar",
        directory_name="ysoserial",
        jar_name="ysoserial.jar",
    ),
)


def jar_path(spec: JavaToolSpec, tools_dir: Path = set_tools.TOOLS_DIR) -> Path:
    return tools_dir / spec.directory_name / spec.jar_name


def release_path(spec: JavaToolSpec, tools_dir: Path = set_tools.TOOLS_DIR) -> Path:
    return tools_dir / spec.directory_name / ".prepare-debian-release"


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

    if not isinstance(payload, dict):
        output_utils.warn(f"GitHub returned invalid release data for {spec.name}.")
        return None
    tag = payload.get("tag_name")
    assets = payload.get("assets")
    if not isinstance(tag, str) or not tag or not isinstance(assets, list):
        output_utils.warn(f"GitHub returned invalid release data for {spec.name}.")
        return None

    expected_url_prefix = f"https://github.com/{spec.repository}/releases/download/"
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
            and url.startswith(expected_url_prefix)
        ):
            matches.append(url)

    if len(matches) != 1:
        output_utils.warn(
            f"Expected one {spec.name} release JAR, found {len(matches)}."
        )
        return None
    return Release(tag, matches[0])


def is_runnable_jar(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = archive.read("META-INF/MANIFEST.MF").decode(
                "utf-8", errors="replace"
            )
    except (OSError, KeyError, zipfile.BadZipFile):
        return False
    return any(
        line.partition(":")[2].strip()
        for line in manifest.splitlines()
        if line.partition(":")[0].casefold() == "main-class"
    )


def _path_exists(path: Path) -> bool:
    return os.path.lexists(path)


def _installed_tag(path: Path) -> Optional[str]:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _temporary_text(path: Path, content: str, mode: int) -> Path:
    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)
        os.chmod(temporary_path, mode)
        return temporary_path
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def _download_jar(
    spec: JavaToolSpec, release: Release, directory: Path
) -> Optional[Path]:
    request = urllib.request.Request(
        release.download_url,
        headers={"User-Agent": DOWNLOAD_USER_AGENT},
    )
    temporary_path: Optional[Path] = None
    try:
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            tempfile.NamedTemporaryFile(
                "wb",
                dir=directory,
                prefix=f".{spec.jar_name}.",
                delete=False,
            ) as temporary_file,
        ):
            shutil.copyfileobj(response, temporary_file)
            temporary_path = Path(temporary_file.name)
        os.chmod(temporary_path, 0o644)
    except (OSError, urllib.error.URLError) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        output_utils.warn(f"Could not download {spec.name}: {exc}")
        return None

    if not is_runnable_jar(temporary_path):
        temporary_path.unlink(missing_ok=True)
        output_utils.warn(f"Downloaded {spec.name} release is not a runnable JAR.")
        return None
    return temporary_path


def install_release(
    spec: JavaToolSpec,
    release: Release,
    tools_dir: Path = set_tools.TOOLS_DIR,
) -> bool:
    destination = jar_path(spec, tools_dir)
    version_file = release_path(spec, tools_dir)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        output_utils.warn(f"Could not create {destination.parent}: {exc}")
        return False

    if _path_exists(version_file) and (
        version_file.is_symlink() or not version_file.is_file()
    ):
        output_utils.warn(f"Preserving unmanaged release marker: {version_file}")
        return False
    if _path_exists(destination) and (
        destination.is_symlink()
        or not destination.is_file()
        or not version_file.is_file()
    ):
        output_utils.warn(f"Preserving unmanaged JAR destination: {destination}")
        return False

    if _installed_tag(version_file) == release.tag and is_runnable_jar(destination):
        output_utils.ok(f"{spec.name} {release.tag} already installed; skipping.")
        return True

    output_utils.info(f"Downloading {spec.name} {release.tag}.")
    downloaded = _download_jar(spec, release, destination.parent)
    if downloaded is None:
        return False

    tag_temporary: Optional[Path] = None
    backup: Optional[Path] = None
    replaced = False
    try:
        tag_temporary = _temporary_text(version_file, f"{release.tag}\n", 0o644)
        if destination.is_file():
            with tempfile.NamedTemporaryFile(
                "wb",
                dir=destination.parent,
                prefix=f".{destination.name}.backup.",
                delete=False,
            ) as backup_file:
                backup = Path(backup_file.name)
            shutil.copy2(destination, backup)

        os.replace(downloaded, destination)
        replaced = True
        os.replace(tag_temporary, version_file)
        tag_temporary = None
    except OSError as exc:
        if replaced:
            try:
                if backup is None:
                    destination.unlink(missing_ok=True)
                else:
                    os.replace(backup, destination)
                    backup = None
            except OSError as rollback_exc:
                output_utils.warn(
                    f"Could not restore the previous {spec.name} JAR: {rollback_exc}"
                )
        output_utils.warn(f"Could not install {spec.name}: {exc}")
        return False
    finally:
        downloaded.unlink(missing_ok=True)
        if tag_temporary is not None:
            tag_temporary.unlink(missing_ok=True)
        if backup is not None:
            backup.unlink(missing_ok=True)

    output_utils.ok(f"Installed {spec.name} {release.tag} at {destination}.")
    return True


def ensure_launcher(spec: JavaToolSpec, destination: Path, home: Path) -> bool:
    launcher = home / ".local" / "bin" / spec.name
    content = (
        f"#!/bin/sh\n{MANAGED_LAUNCHER_MARKER}\n"
        f'exec java -jar {shlex.quote(str(destination.absolute()))} "$@"\n'
    )
    temporary: Optional[Path] = None
    try:
        launcher.parent.mkdir(parents=True, exist_ok=True)
        if _path_exists(launcher):
            if launcher.is_symlink() or not launcher.is_file():
                output_utils.warn(f"Preserving unmanaged launcher: {launcher}")
                return False
            current = launcher.read_text(encoding="utf-8")
            if MANAGED_LAUNCHER_MARKER not in current.splitlines():
                output_utils.warn(f"Preserving unmanaged launcher: {launcher}")
                return False
            if current == content and os.access(launcher, os.X_OK):
                output_utils.ok(
                    f"{spec.name} launcher already installed at {launcher}."
                )
                return True

        temporary = _temporary_text(launcher, content, 0o755)
        os.replace(temporary, launcher)
        temporary = None
    except OSError as exc:
        output_utils.warn(f"Could not install {spec.name} launcher: {exc}")
        return False
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    output_utils.ok(f"Installed {spec.name} launcher at {launcher}.")
    return True


def ensure_ysoserial_link(
    target: Path,
    link: Path = YSOSERIAL_COMPATIBILITY_LINK,
) -> bool:
    try:
        absolute_target = target.resolve(strict=True)
    except OSError as exc:
        output_utils.warn(f"Could not resolve the ysoserial JAR: {exc}")
        return False
    if not is_runnable_jar(absolute_target):
        output_utils.warn(f"ysoserial target is not a runnable JAR: {absolute_target}")
        return False

    try:
        if _path_exists(link):
            if link.is_symlink() and os.readlink(link) == str(absolute_target):
                if link.resolve(strict=True) == absolute_target:
                    output_utils.ok(f"ysoserial compatibility link already set: {link}")
                    return True
            output_utils.warn(f"Preserving existing compatibility path: {link}")
            return False

        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(absolute_target)
        if os.readlink(link) != str(absolute_target):
            output_utils.warn(f"Could not verify ysoserial compatibility link: {link}")
            return False
    except OSError as exc:
        output_utils.warn(f"Could not install ysoserial compatibility link: {exc}")
        return False

    output_utils.ok(f"Installed ysoserial compatibility link: {link}")
    return True


def main() -> bool:
    if os.geteuid() != 0:
        output_utils.warn("Preparing Java tools requires root privileges.")
        return False
    if not apt_utils.ensure_apt_package(JAVA_PACKAGE):
        return False
    if shutil.which("java") is None:
        output_utils.warn(f"Java is not available after installing {JAVA_PACKAGE}.")
        return False
    if not set_tools.ensure_tools_dir():
        return False

    home = Path.home()
    if not configure_agents.ensure_local_bin_on_path(home):
        return False

    installed: dict[str, Path] = {}
    for spec in JAVA_TOOLS:
        release = latest_release(spec)
        if release is None or not install_release(spec, release):
            return False
        destination = jar_path(spec)
        if not ensure_launcher(spec, destination, home):
            return False
        installed[spec.name] = destination

    return ensure_ysoserial_link(installed["ysoserial"])

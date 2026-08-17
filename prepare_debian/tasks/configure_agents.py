import os
import shutil
import tempfile
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from prepare_debian.repositories import CODING_AGENT_HELPERS_REPOSITORY
from prepare_debian.tasks import set_tools
from prepare_debian.utils import config_utils, output_utils, process_utils

CODEX_VALUES: Mapping[str, Any] = {
    "commit_attribution": "",
}

CLAUDE_VALUES: Mapping[str, Any] = {
    "attribution": {
        "commit": "",
        "pr": "",
        "sessionUrl": False,
    },
    "includeCoAuthoredBy": False,
}

DOWNLOAD_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
PROFILE_FILES = (".profile", ".bashrc", ".zshrc")
LOCAL_BIN_EXPORT = 'export PATH="$HOME/.local/bin:$PATH"\n'


@dataclass(frozen=True)
class CliSpec:
    name: str
    command: str
    installer_url: str
    interpreter: str
    installer_environment: str


CLI_SPECS = (
    CliSpec(
        "Codex",
        "codex",
        "https://chatgpt.com/codex/install.sh",
        "sh",
        "CODEX_NON_INTERACTIVE=1",
    ),
    CliSpec(
        "Claude",
        "claude",
        "https://claude.ai/install.sh",
        "bash",
        "CLAUDE_INSTALL_ALLOW_SUDO=1",
    ),
)


def apply_agent_config(home: Path, codex_home: Optional[Path] = None) -> None:
    if codex_home is None:
        configured_codex_home = os.environ.get("CODEX_HOME")
        codex_home = (
            Path(configured_codex_home) if configured_codex_home else home / ".codex"
        )

    codex_path = codex_home / "config.toml"
    claude_path = home / ".claude" / "settings.json"

    codex_changed = config_utils.update_toml_values(codex_path, CODEX_VALUES)
    claude_changed = config_utils.update_json_values(claude_path, CLAUDE_VALUES)

    for name, path, changed in (
        ("Codex", codex_path, codex_changed),
        ("Claude", claude_path, claude_changed),
    ):
        action = "Updated" if changed else "Already configured"
        output_utils.ok(f"{action}: {name} attribution disabled in {path}")


def locate_cli(command: str, home: Path) -> Optional[Path]:
    discovered = shutil.which(command)
    if discovered is not None:
        return Path(discovered)
    local_command = home / ".local" / "bin" / command
    if local_command.is_file() and os.access(local_command, os.X_OK):
        return local_command
    return None


def ensure_local_bin_on_path(home: Path) -> bool:
    updated = False
    for filename in PROFILE_FILES:
        path = home / filename
        try:
            content = path.read_text(encoding="utf-8") if path.exists() else ""
            if LOCAL_BIN_EXPORT.strip() in content:
                continue
            with path.open("a", encoding="utf-8") as profile:
                if content and not content.endswith("\n"):
                    profile.write("\n")
                profile.write(LOCAL_BIN_EXPORT)
            updated = True
        except OSError as exc:
            output_utils.warn(f"Could not update {path}: {exc}")
            return False

    if updated:
        output_utils.ok("Added ~/.local/bin to shell PATH configuration.")
    else:
        output_utils.ok("~/.local/bin already configured in shell PATH.")
    return True


def run_installer(spec: CliSpec) -> bool:
    output_utils.info(f"Downloading the official {spec.name} installer.")
    request = urllib.request.Request(
        spec.installer_url,
        headers={"User-Agent": DOWNLOAD_USER_AGENT},
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=30) as response,
            tempfile.NamedTemporaryFile("wb") as installer,
        ):
            shutil.copyfileobj(response, installer)
            installer.flush()
            result = process_utils.run(
                ["env", spec.installer_environment, spec.interpreter, installer.name]
            )
    except (OSError, urllib.error.URLError) as exc:
        output_utils.warn(f"Could not download the {spec.name} installer: {exc}")
        return False

    if result is None or result.returncode != 0:
        stderr = result.stderr.strip() if result is not None else ""
        output_utils.warn(stderr or f"{spec.name} installer failed.")
        return False
    return True


def ensure_cli(spec: CliSpec, home: Path) -> bool:
    executable = locate_cli(spec.command, home)
    if executable is None:
        if not run_installer(spec):
            return False
        executable = locate_cli(spec.command, home)
        if executable is None:
            output_utils.warn(
                f"{spec.name} installer completed but {spec.command} was not found."
            )
            return False
    else:
        output_utils.ok(f"{spec.name} CLI already installed at {executable}.")

    version = process_utils.run([str(executable), "--version"])
    if version is None or version.returncode != 0:
        stderr = version.stderr.strip() if version is not None else ""
        output_utils.warn(stderr or f"Could not verify the {spec.name} CLI.")
        return False
    output_utils.ok(f"Verified {spec.name} CLI: {version.stdout.strip()}.")
    return True


def _symlink_target(path: Path) -> Path:
    target = Path(os.readlink(path))
    if not target.is_absolute():
        target = path.parent / target
    return target.resolve(strict=False)


def install_skills(checkout: Path, home: Path) -> bool:
    source_root = checkout / "skills"
    if not source_root.is_dir():
        output_utils.warn(f"Missing skills directory: {source_root}")
        return False

    skills = {
        child.name: child
        for child in source_root.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    }
    if not skills:
        output_utils.warn(f"No valid skills found in {source_root}.")
        return False
    if any(name.casefold() == "synced" for name in skills):
        output_utils.warn(
            "The reserved Claude skill name 'synced' cannot be installed."
        )
        return False

    managed_root = source_root.resolve()
    skill_roots = (home / ".claude" / "skills", home / ".agents" / "skills")
    try:
        for skill_root in skill_roots:
            skill_root.mkdir(parents=True, exist_ok=True)
            for existing in skill_root.iterdir():
                if not existing.is_symlink():
                    continue
                target = _symlink_target(existing)
                if target.parent == managed_root and target.name not in skills:
                    existing.unlink()
                    output_utils.info(f"Removed stale managed skill link: {existing}")

            for name in sorted(skills):
                source = skills[name].resolve()
                destination = skill_root / name
                if destination.is_symlink():
                    if _symlink_target(destination) == source:
                        continue
                    output_utils.warn(
                        f"Skill destination points elsewhere; preserving {destination}."
                    )
                    return False
                if destination.exists():
                    output_utils.warn(
                        f"Skill destination already exists; preserving {destination}."
                    )
                    return False
                destination.symlink_to(source, target_is_directory=True)
                output_utils.ok(f"Installed skill link: {destination}")
    except OSError as exc:
        output_utils.warn(f"Could not install agent skills: {exc}")
        return False
    return True


def main() -> bool:
    home = Path.home()
    try:
        apply_agent_config(home)
    except (config_utils.ConfigUpdateError, OSError) as exc:
        output_utils.warn(str(exc))
        return False

    if not ensure_local_bin_on_path(home):
        return False

    for spec in CLI_SPECS:
        if not ensure_cli(spec, home):
            return False

    if not set_tools.ensure_tools_dir():
        return False
    if not set_tools.synchronize_repository(CODING_AGENT_HELPERS_REPOSITORY):
        return False
    checkout = set_tools.repository_path(CODING_AGENT_HELPERS_REPOSITORY)
    return install_skills(checkout, home)

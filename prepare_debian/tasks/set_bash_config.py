import sys

from prepare_debian.repositories import BASH_CONFIG_REPOSITORY
from prepare_debian.tasks import set_tools
from prepare_debian.utils import apt_utils, output_utils, process_utils


def ensure_bash_config_repo() -> bool:
    return set_tools.synchronize_repository(BASH_CONFIG_REPOSITORY)


def run_install() -> bool:
    repo_dir = set_tools.repository_path(BASH_CONFIG_REPOSITORY)
    install_script = repo_dir / "install.py"
    if not install_script.exists():
        output_utils.warn(f"Missing {install_script}; cannot install bash_config.")
        return False

    result = process_utils.run([sys.executable, str(install_script)])
    if result is None or result.returncode != 0:
        stderr = result.stderr.strip() if result is not None else ""
        output_utils.warn(stderr or "bash_config install failed.")
        return False

    output_utils.ok("bash_config installed.")
    return True


def main() -> bool:
    if not apt_utils.update_apt_cache():
        return False
    if not apt_utils.ensure_apt_package("git"):
        return False
    if not apt_utils.ensure_apt_package("xclip"):
        return False
    if not set_tools.ensure_tools_dir():
        return False
    if not ensure_bash_config_repo():
        return False
    output_utils.info(
        "Executing bash_config installer from pin "
        f"{BASH_CONFIG_REPOSITORY.revision[:12]}."
    )
    return run_install()

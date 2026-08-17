import argparse
from collections.abc import Callable

from prepare_debian.tasks import (
    configure_agents,
    disable_screen_lock,
    install_packages,
    prepare_impacket,
    set_bash_config,
    set_shell_to_bash,
    set_tools,
)
from prepare_debian.utils import output_utils

TASKS: dict[str, Callable[[], bool]] = {
    "configure_agents": configure_agents.main,
    "disable_screen_lock": disable_screen_lock.main,
    "prepare_impacket": prepare_impacket.main,
    "set_bash_config": set_bash_config.main,
    "install_packages": install_packages.main,
    "set_shell_to_bash": set_shell_to_bash.main,
    "set_tools": set_tools.main,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Debian-based tasks runner.")
    parser.add_argument(
        "--task",
        action="append",
        choices=sorted(TASKS.keys()),
        help="Run a specific task by name. Repeat to run several; omit to run all.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_tasks = args.task or sorted(TASKS)
    for name in selected_tasks:
        output_utils.banner(f"== prepare_debian :: {name} ==")
        if not TASKS[name]():
            output_utils.warn(f"Task failed: {name}")
            return 1
    return 0

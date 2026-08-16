import argparse
from collections.abc import Callable

from prepare_debian.tasks import (
    configure_agents,
    install_packages,
    prepare_impacket,
    set_bash_config,
    set_shell_to_bash,
    set_tools,
)
from prepare_debian.utils import output_utils

TASKS: dict[str, Callable[..., object]] = {
    "configure_agents": configure_agents.main,
    "prepare_impacket": prepare_impacket.main,
    "set_bash_config": set_bash_config.main,
    "install_packages": install_packages.main,
    "set_shell_to_bash": set_shell_to_bash.main,
    "set_tools": set_tools.main,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Debian-based tasks runner.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tasks.",
    )
    parser.add_argument(
        "--task",
        action="append",
        default=[],
        choices=sorted(TASKS.keys()),
        help="Run a specific task by name. Can be provided multiple times.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force tasks to re-apply changes even if already configured.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.all and not args.task:
        args.all = True

    if args.all:
        output_utils.banner("== prepare_debian :: run all ==")
        for name in sorted(TASKS.keys()):
            output_utils.info(f"Running task: {name}")
            result = TASKS[name](force=args.force)
            if result is False:
                output_utils.warn(f"Task failed: {name}")
                return 1
        output_utils.info("Run: source ~/.bashrc")
        return 0

    for name in args.task:
        output_utils.banner(f"== prepare_debian :: {name} ==")
        result = TASKS[name](force=args.force)
        if result is False:
            output_utils.warn(f"Task failed: {name}")
            return 1
    output_utils.info("Run: source ~/.bashrc")
    return 0

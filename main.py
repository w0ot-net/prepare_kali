#!/usr/bin/env python3
import argparse
import sys

import prepare_impacket
import set_shell_to_bash


TASKS = {
    "prepare_impacket": prepare_impacket.main,
    "set_shell_to_bash": set_shell_to_bash.main,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare Kali tasks runner.")
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


def main():
    args = parse_args()
    if not args.all and not args.task:
        print("No tasks selected. Use --all or --task.", file=sys.stderr)
        return 2

    if args.all:
        for name in sorted(TASKS.keys()):
            TASKS[name](force=args.force)
        return 0

    for name in args.task:
        TASKS[name](force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

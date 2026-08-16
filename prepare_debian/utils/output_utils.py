import sys


def banner(title: str) -> None:
    line = "=" * max(10, len(title))
    print(line)
    print(title)
    print(line)


def info(message: str) -> None:
    print(f"[*] {message}")


def ok(message: str) -> None:
    print(f"[+] {message}")


def warn(message: str) -> None:
    print(f"[!] {message}", file=sys.stderr)

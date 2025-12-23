#!/usr/bin/env python3
import sys


def banner(title):
    line = "=" * max(10, len(title))
    print(line)
    print(title)
    print(line)


def info(message):
    print(f"[*] {message}")


def ok(message):
    print(f"[+] {message}")


def warn(message):
    print(f"[!] {message}", file=sys.stderr)

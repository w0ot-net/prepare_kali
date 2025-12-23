#!/usr/bin/env python3
from pathlib import Path

import output_utils


FUNCTIONS_FILE = Path.home() / ".bash_functions"
BASHRC_FILE = Path.home() / ".bashrc"
FUNCTION_BLOCK = [
    "nl2space() {",
    "    tr '\\n' ' '",
    "}",
]
SOURCE_BLOCK = [
    "# Added by prepare_kali",
    'if [ -f "$HOME/.bash_functions" ]; then',
    '    . "$HOME/.bash_functions"',
    "fi",
]


def ensure_functions_file(force=False):
    existing = ""
    if FUNCTIONS_FILE.exists():
        try:
            existing = FUNCTIONS_FILE.read_text()
        except OSError as exc:
            output_utils.warn(f"Could not read {FUNCTIONS_FILE}: {exc}")
            return False

    block_text = "\n".join(FUNCTION_BLOCK)
    if block_text in existing and not force:
        output_utils.ok(f"Functions already present in {FUNCTIONS_FILE}.")
        return True

    try:
        content = existing
        if content and not content.endswith("\n"):
            content += "\n"
        content += block_text + "\n"
        FUNCTIONS_FILE.write_text(content)
    except OSError as exc:
        output_utils.warn(f"Could not write {FUNCTIONS_FILE}: {exc}")
        return False

    output_utils.ok(f"Updated {FUNCTIONS_FILE}.")
    return True


def ensure_bashrc_sources_functions(force=False):
    existing = ""
    if BASHRC_FILE.exists():
        try:
            existing = BASHRC_FILE.read_text()
        except OSError as exc:
            output_utils.warn(f"Could not read {BASHRC_FILE}: {exc}")
            return False

    block_text = "\n".join(SOURCE_BLOCK)
    if block_text in existing and not force:
        output_utils.ok(f"{BASHRC_FILE} already sources {FUNCTIONS_FILE}.")
        return True

    try:
        content = existing
        if content and not content.endswith("\n"):
            content += "\n"
        content += block_text + "\n"
        BASHRC_FILE.write_text(content)
    except OSError as exc:
        output_utils.warn(f"Could not write {BASHRC_FILE}: {exc}")
        return False

    output_utils.ok(f"Updated {BASHRC_FILE} to source {FUNCTIONS_FILE}.")
    return True


def main(force=False):
    ensure_functions_file(force=force)
    ensure_bashrc_sources_functions(force=force)


if __name__ == "__main__":
    main()

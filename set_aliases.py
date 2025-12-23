#!/usr/bin/env python3
from pathlib import Path

import output_utils


ALIASES_FILE = Path.home() / ".aliases"
BASHRC_FILE = Path.home() / ".bashrc"
ALIAS_LINE = "alias ls='ls -alh --color'"
SOURCE_BLOCK = [
    "# Added by prepare_kali",
    'if [ -f "$HOME/.aliases" ]; then',
    '    . "$HOME/.aliases"',
    "fi",
]


def ensure_aliases_file(force=False):
    existing = ""
    if ALIASES_FILE.exists():
        try:
            existing = ALIASES_FILE.read_text()
        except OSError as exc:
            output_utils.warn(f"Could not read {ALIASES_FILE}: {exc}")
            return False

    if ALIAS_LINE in existing and not force:
        output_utils.ok(f"Alias already present in {ALIASES_FILE}.")
        return True

    try:
        lines = existing.splitlines() if existing else []
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(ALIAS_LINE)
        ALIASES_FILE.write_text("\n".join(lines) + "\n")
    except OSError as exc:
        output_utils.warn(f"Could not write {ALIASES_FILE}: {exc}")
        return False

    output_utils.ok(f"Updated {ALIASES_FILE}.")
    return True


def ensure_bashrc_sources_aliases(force=False):
    existing = ""
    if BASHRC_FILE.exists():
        try:
            existing = BASHRC_FILE.read_text()
        except OSError as exc:
            output_utils.warn(f"Could not read {BASHRC_FILE}: {exc}")
            return False

    block_text = "\n".join(SOURCE_BLOCK)
    if block_text in existing and not force:
        output_utils.ok(f"{BASHRC_FILE} already sources {ALIASES_FILE}.")
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

    output_utils.ok(f"Updated {BASHRC_FILE} to source {ALIASES_FILE}.")
    return True


def main(force=False):
    ensure_aliases_file(force=force)
    ensure_bashrc_sources_aliases(force=force)


if __name__ == "__main__":
    main()

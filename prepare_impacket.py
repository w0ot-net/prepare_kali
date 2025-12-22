#!/usr/bin/env python3
import sys
from pathlib import Path

import apt_utils

IMPACKET_EXAMPLES = "/usr/lib/python3/dist-packages/impacket/examples/"
PROFILE_FILES = [".profile", ".bashrc", ".zshrc"]


def path_export_line():
    return f'export PATH="$PATH:{IMPACKET_EXAMPLES}"\n'


def ensure_path_in_profile(force=False):
    home = Path.home()
    line = path_export_line()
    comment = "# Added by prepare_impacket.py\n"
    updated_any = False

    for filename in PROFILE_FILES:
        path = home / filename
        try:
            existing = path.read_text() if path.exists() else ""
        except OSError as exc:
            print(f"Could not read {path}: {exc}", file=sys.stderr)
            continue

        if IMPACKET_EXAMPLES in existing:
            if force:
                print(f"PATH already includes impacket examples in {path}.")
            continue

        try:
            with path.open("a", encoding="utf-8") as f:
                if not existing.endswith("\n") and existing != "":
                    f.write("\n")
                f.write(comment)
                f.write(line)
            updated_any = True
        except OSError as exc:
            print(f"Could not write {path}: {exc}", file=sys.stderr)

    if not updated_any:
        print("PATH already updated or no writable profile files found.")
    else:
        print("Updated shell profile(s). Restart your shell to pick up PATH changes.")


def main(force=False):
    if not apt_utils.ensure_apt_package("python3-impacket", force=force):
        print("python3-impacket installation not confirmed.", file=sys.stderr)
    ensure_path_in_profile(force=force)


if __name__ == "__main__":
    main()

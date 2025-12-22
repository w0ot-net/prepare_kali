#!/usr/bin/env python3
import shutil
import subprocess
import sys
from pathlib import Path


IMPACKET_EXAMPLES = "/usr/lib/python3/dist-packages/impacket/examples/"
PROFILE_FILES = [".profile", ".bashrc", ".zshrc"]


def run(cmd):
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ensure_impacket_installed(force=False):
    if shutil.which("dpkg") is None:
        print("dpkg not found; cannot verify python3-impacket installation.", file=sys.stderr)
        return False

    check = run(["dpkg", "-s", "python3-impacket"])
    if check.returncode == 0 and not force:
        return True

    if check.returncode == 0 and force:
        print("python3-impacket already installed; reinstalling because --force was set.")
    else:
        print("python3-impacket not installed; attempting to install via apt.")
    if shutil.which("sudo") is None or shutil.which("apt-get") is None:
        print("sudo or apt-get not found; cannot install python3-impacket.", file=sys.stderr)
        return False

    update = run(["sudo", "apt-get", "update"])
    if update.returncode != 0:
        sys.stderr.write(update.stderr)
        return False

    install = run(["sudo", "apt-get", "install", "-y", "python3-impacket"])
    if install.returncode != 0:
        sys.stderr.write(install.stderr)
        return False

    return True


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
    if not ensure_impacket_installed(force=force):
        print("python3-impacket installation not confirmed.", file=sys.stderr)
    ensure_path_in_profile(force=force)


if __name__ == "__main__":
    main()

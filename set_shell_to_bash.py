#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path
import pwd


def run(cmd):
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ensure_default_shell_bash(force=False):
    bash_path = "/bin/bash"
    if not os.path.exists(bash_path):
        print(f"{bash_path} not found; cannot set default shell.", file=sys.stderr)
        return

    if os.geteuid() != 0:
        print("Root privileges required to change default shells for all users.", file=sys.stderr)
        return

    changed_any = False
    for user in pwd.getpwall():
        if user.pw_shell in ("/usr/sbin/nologin", "/bin/false", ""):
            continue
        if user.pw_uid != 0 and user.pw_uid < 1000:
            continue
        if user.pw_shell == bash_path and not force:
            continue
        result = run(["chsh", "-s", bash_path, user.pw_name])
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
        else:
            changed_any = True

    useradd_path = Path("/etc/default/useradd")
    if useradd_path.exists():
        try:
            content = useradd_path.read_text()
            lines = []
            updated = False
            for line in content.splitlines():
                if line.startswith("SHELL="):
                    if line != f"SHELL={bash_path}" or force:
                        lines.append(f"SHELL={bash_path}")
                        updated = True
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
            if not updated:
                lines.append(f"SHELL={bash_path}")
            useradd_path.write_text("\n".join(lines) + "\n")
            changed_any = changed_any or updated
        except OSError as exc:
            print(f"Could not update {useradd_path}: {exc}", file=sys.stderr)

    adduser_path = Path("/etc/adduser.conf")
    if adduser_path.exists():
        try:
            content = adduser_path.read_text()
            lines = []
            updated = False
            for line in content.splitlines():
                if line.startswith("DSHELL="):
                    desired = f'DSHELL="{bash_path}"'
                    if line != desired or force:
                        lines.append(desired)
                        updated = True
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
            if not updated:
                lines.append(f'DSHELL="{bash_path}"')
            adduser_path.write_text("\n".join(lines) + "\n")
            changed_any = changed_any or updated
        except OSError as exc:
            print(f"Could not update {adduser_path}: {exc}", file=sys.stderr)

    if not changed_any:
        print("Default shell already set to bash; no changes needed.")

def main(force=False):
    ensure_default_shell_bash(force=force)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
import pwd

from utils import output_utils


def run(cmd):
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ensure_default_shell_bash(force=False):
    bash_path = "/bin/bash"
    if not os.path.exists(bash_path):
        output_utils.warn(f"{bash_path} not found; cannot set default shell.")
        return

    if os.geteuid() != 0:
        output_utils.warn("Root privileges required to change default shells for all users.")
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
            output_utils.warn(result.stderr.strip())
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
            output_utils.warn(f"Could not update {useradd_path}: {exc}")

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
            output_utils.warn(f"Could not update {adduser_path}: {exc}")

    if not changed_any:
        output_utils.ok("Default shell already set to bash; no changes needed.")

def main(force=False):
    ensure_default_shell_bash(force=force)


if __name__ == "__main__":
    main()

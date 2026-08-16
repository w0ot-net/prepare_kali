import os
import pwd
from pathlib import Path

from prepare_debian.utils import output_utils, process_utils


def ensure_default_shell_bash() -> bool:
    bash_path = "/bin/bash"
    if not os.path.exists(bash_path):
        output_utils.warn(f"{bash_path} not found; cannot set default shell.")
        return False

    if os.geteuid() != 0:
        output_utils.warn(
            "Root privileges required to change default shells for all users."
        )
        return False

    changed_any = False
    success = True
    for user in pwd.getpwall():
        if user.pw_shell in ("/usr/sbin/nologin", "/bin/false", ""):
            continue
        if user.pw_uid != 0 and user.pw_uid < 1000:
            continue
        if user.pw_shell == bash_path:
            continue
        result = process_utils.run(["chsh", "-s", bash_path, user.pw_name])
        if result is None or result.returncode != 0:
            stderr = result.stderr.strip() if result is not None else ""
            output_utils.warn(stderr or f"Could not update shell for {user.pw_name}.")
            success = False
        else:
            changed_any = True

    useradd_path = Path("/etc/default/useradd")
    if useradd_path.exists():
        try:
            content = useradd_path.read_text()
            lines = []
            found = False
            updated = False
            for line in content.splitlines():
                if line.startswith("SHELL="):
                    found = True
                    if line != f"SHELL={bash_path}":
                        lines.append(f"SHELL={bash_path}")
                        updated = True
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
            if not found:
                lines.append(f"SHELL={bash_path}")
                updated = True
            useradd_path.write_text("\n".join(lines) + "\n")
            changed_any = changed_any or updated
        except OSError as exc:
            output_utils.warn(f"Could not update {useradd_path}: {exc}")
            success = False

    adduser_path = Path("/etc/adduser.conf")
    if adduser_path.exists():
        try:
            content = adduser_path.read_text()
            lines = []
            found = False
            updated = False
            for line in content.splitlines():
                if line.startswith("DSHELL="):
                    found = True
                    desired = f'DSHELL="{bash_path}"'
                    if line != desired:
                        lines.append(desired)
                        updated = True
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
            if not found:
                lines.append(f'DSHELL="{bash_path}"')
                updated = True
            adduser_path.write_text("\n".join(lines) + "\n")
            changed_any = changed_any or updated
        except OSError as exc:
            output_utils.warn(f"Could not update {adduser_path}: {exc}")
            success = False

    if success and not changed_any:
        output_utils.ok("Default shell already set to bash; no changes needed.")
    return success


def main() -> bool:
    return ensure_default_shell_bash()

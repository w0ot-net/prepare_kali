# prepare_debian

`prepare_debian` sets up a Debian-based workstation with common packages, shell
configuration, and tools used by this project. It supports Python 3.9 or newer on
Debian-derived systems such as Kali Linux, Ubuntu, and Debian.

## Requirements

- Python 3.9 or newer.
- A Debian-based system with `apt-get` and `dpkg`.
- `sudo` for package operations, including when the command itself runs as root.
- Network access for apt and Git operations.
- Effective root privileges for the `set_shell_to_bash` task.

## Installation

From the repository root, install the project into the active Python environment:

```sh
python3 -m pip install .
```

This installs the `prepare-debian` command. The same CLI is also available through
module execution:

```sh
python3 -m prepare_debian --help
```

Task modules are internal and are not supported as standalone scripts.

## Usage

```sh
prepare-debian --help
prepare-debian --all
prepare-debian --task install_packages
prepare-debian --task install_packages --task set_tools
prepare-debian --all --force
```

Important: running `prepare-debian` without arguments currently runs every task, the
same as `--all`. An all-task run performs package installation, network operations,
home-directory changes, remote installer execution, and system-wide shell changes.
Review the task list and prefer explicit `--task` selections when you do not want all
of those effects.

`--force` reinstalls already installed apt packages and reapplies some shell settings.
Repository checkouts are updated whenever their task runs, regardless of `--force`.

## Tasks

Tasks run in alphabetical order during `--all`:

| Task | Effect | Main requirements |
| --- | --- | --- |
| `install_packages` | Updates apt metadata and installs the packages listed in `prepare_debian/tasks/install_packages.py`. | `sudo`, apt, network access |
| `prepare_impacket` | Ensures `python3-impacket` is installed and appends its examples directory to `.profile`, `.bashrc`, and `.zshrc` under the current home directory, creating missing files. | `sudo` if installation is needed |
| `set_bash_config` | Ensures Git and `xclip`, clones or updates `w0ot-net/bash_config`, and executes its `install.py`. | `sudo`, Git, network access; executes remote code |
| `set_shell_to_bash` | Changes Bash to the login shell for root and login-capable users with UID 1000 or greater, then updates `/etc/default/useradd` and `/etc/adduser.conf` when present. | Effective root privileges, `chsh` |
| `set_tools` | Creates `~/tools` and clones or updates the configured `w0ot-net` repositories. | Git and network access |

Tools and `bash_config` are stored under `~/tools` for the user whose home directory
Python resolves at runtime. Running the whole command through `sudo` may therefore
target root's home rather than the invoking user's home. Run home-directory tasks as
the intended user and the system-wide shell task separately when appropriate.

Existing Git checkouts follow their remote branch with `git pull --ff-only`, and the
`bash_config` installer is executed from that mutable checkout. Inspect the configured
sources before running tasks that fetch or execute them.

## Exit status

The command returns nonzero when the runner receives an explicit `False` result from
a task. Some tasks currently warn about internal failures without returning `False`,
so a zero exit status does not yet guarantee that every requested operation succeeded.
Review the command output for warnings.

## Project structure

- `prepare_debian/cli.py`: CLI and task registry.
- `prepare_debian/tasks/`: task implementations.
- `prepare_debian/utils/`: shared helpers.

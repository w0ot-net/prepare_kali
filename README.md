# prepare_debian

`prepare_debian` sets up a Debian-based workstation with common packages, shell
configuration, and tools used by this project. It supports Python 3.9 or newer on
Debian-derived systems such as Kali Linux, Ubuntu, and Debian.

## Requirements

- Python 3.9 or newer.
- A Debian-based system with `apt-get` and `dpkg`.
- `sudo` for package operations when the command is not already running as root.
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
prepare-debian --task configure_agents
prepare-debian --task install_packages
prepare-debian --task install_packages --task set_tools
prepare-debian --all
```

An explicit `--all` or at least one `--task` selection is required. Running without a
selection, or combining `--all` with `--task`, exits with argparse status 2 before any
task runs. An all-task run performs package installation, network operations,
home-directory changes, remote installer execution, and system-wide shell changes, so
review the task list before selecting it.

Tasks use their existing state checks for idempotence. The runner stops at the first
failed selected task and returns status 1; it does not roll back earlier successful
changes.

## Tasks

Tasks run in alphabetical order during `--all`:

| Task | Effect | Main requirements |
| --- | --- | --- |
| `configure_agents` | Updates the user Codex and Claude config files while preserving unrelated values. It disables commit/PR attribution and Claude session links. | Write access to `~/.codex` and `~/.claude` |
| `install_packages` | Updates apt metadata and installs the packages listed in `prepare_debian/tasks/install_packages.py`. | `sudo`, apt, network access |
| `prepare_impacket` | Ensures `python3-impacket` is installed and appends its examples directory to `.profile`, `.bashrc`, and `.zshrc` under the current home directory, creating missing files. | `sudo` if installation is needed |
| `set_bash_config` | Ensures Git and `xclip`, synchronizes `w0ot-net/bash_config` to its reviewed commit pin, and executes that revision's `install.py`. | Package-management privileges, Git, network access; executes externally maintained code |
| `set_shell_to_bash` | Changes Bash to the login shell for root and login-capable users with UID 1000 or greater, then updates `/etc/default/useradd` and `/etc/adduser.conf` when present. | Effective root privileges, `chsh` |
| `set_tools` | Creates `~/tools` and synchronizes configured `w0ot-net` repositories to reviewed commit pins. | Git and network access |

Tools and `bash_config` are stored under `~/tools` for the user whose home directory
Python resolves at runtime. Running the whole command through `sudo` may therefore
target root's home rather than the invoking user's home. Run home-directory tasks as
the intended user and the system-wide shell task separately when appropriate.

### Agent configuration

`configure_agents` manages explicit values in `~/.codex/config.toml` and
`~/.claude/settings.json`. The desired values live in `CODEX_VALUES` and
`CLAUDE_VALUES` in `prepare_debian/tasks/configure_agents.py`, so another supported
setting can be added without replacing either config file. The initial policy disables
Codex commit attribution and all Claude commit, pull-request, and session-link
attribution. Invalid existing Claude JSON fails without overwriting that file.

### Managed repository pins

External repository identities and full commit pins are defined in
`prepare_debian/repositories.py`. Managed checkouts live under `~/tools`, use detached
HEADs, and are accepted only when their `origin` URL matches, the worktree is clean,
and the final HEAD equals the configured pin. The tasks never merge a branch, reset,
clean, stash, or overwrite local changes; a dirty checkout or unexpected origin fails
with a diagnostic for manual resolution.

To update a pin, inspect and review the upstream change, replace the full SHA in
`prepare_debian/repositories.py`, and run the focused repository tests before applying
the task. Pinning selects exact source but does not audit or sandbox it. In particular,
`set_bash_config` executes the pinned external `install.py` after Git verification, so
review that revision before intentionally changing its pin.

## Exit status

The command returns 0 only when every selected task succeeds, 1 when a task fails, and
2 for invalid or missing arguments. Missing external commands and expected operating
system or filesystem failures are reported as concise task failures rather than
uncaught subprocess errors.

## Project structure

- `prepare_debian/cli.py`: CLI and task registry.
- `prepare_debian/tasks/`: task implementations.
- `prepare_debian/utils/`: shared helpers.

## Development

Install the development tools into the active environment:

```sh
python -m pip install -e '.[dev]'
```

Run the same quality checks used by CI:

```sh
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy prepare_debian tests
```

Tests isolate task calls and do not perform apt, Git, shell, profile, or remote
installer operations.

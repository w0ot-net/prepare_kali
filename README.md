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
python3 main.py
./main.py
prepare-debian --help
prepare-debian --task disable_screen_lock
prepare-debian --task configure_agents
prepare-debian --task install_packages
prepare-debian --task install_packages --task set_tools
```

Running `python3 main.py`, `./main.py`, `python3 -m prepare_debian`, or the installed
`prepare-debian` command without options runs every task in alphabetical order. Use
`--task` to run only a specific task; repeat it to run several tasks in the supplied
order. Tasks use their existing state checks for idempotence. The runner stops at the
first failed task and returns status 1; it does not roll back earlier successful
changes.

## Tasks

Available tasks:

| Task | Effect | Main requirements |
| --- | --- | --- |
| `configure_agents` | Disables Codex/Claude attribution, installs either CLI when missing, synchronizes the pinned coding-agent helpers, and links their skills for both CLIs. | Network access, Git, `sh`, `bash`, and write access to the user's config, `~/.local`, `~/.agents`, `~/.claude`, and `~/tools` paths |
| `disable_screen_lock` | Disables idle screen locking and display blanking for the invoking user's active GNOME or XFCE session. | Run as the intended user inside a GNOME or XFCE graphical session; `gsettings`, or `xfconf-query` and `xset` |
| `install_packages` | Updates apt metadata and installs the packages listed in `prepare_debian/tasks/install_packages.py`. | Package-management privileges, apt, network access |
| `prepare_impacket` | Ensures `python3-impacket` is installed and appends its examples directory to `.profile`, `.bashrc`, and `.zshrc` under the current home directory, creating missing files. | Package-management privileges if installation is needed |
| `set_bash_config` | Ensures Git and `xclip`, synchronizes `w0ot-net/bash_config` to its reviewed commit pin, and executes that revision's `install.py`. | Package-management privileges, Git, network access; executes externally maintained code |
| `set_shell_to_bash` | Changes Bash to the login shell for root and login-capable users with UID 1000 or greater, then updates `/etc/default/useradd` and `/etc/adduser.conf` when present. | Effective root privileges, `chsh` |
| `set_tools` | Creates `~/tools` and synchronizes configured `w0ot-net` repositories to reviewed commit pins. | Git and network access |

Tools and `bash_config` are stored under `~/tools` for the user whose home directory
Python resolves at runtime. Running the whole command through `sudo` may therefore
target root's home rather than the invoking user's home. Run home-directory tasks as
the intended user and the system-wide shell task separately when appropriate.

### Desktop idle locking and blanking

`disable_screen_lock` detects the active desktop from `XDG_CURRENT_DESKTOP`, falling
back to `DESKTOP_SESSION`. On GNOME it disables the session idle timeout and automatic
lock-on-screensaver setting. On XFCE it disables idle screensaver activation,
the screensaver and locker master switches, lock-on-screensaver activation,
lock-on-sleep across the screensaver, power-manager, and session channels, and
power-manager DPMS for both AC and battery use. It also disables the active X11
screensaver and DPMS timers. Every persistent value is read back. If the XFCE
screensaver is running, its current state is deactivated and reset; no screensaver
process is started or stopped.

Run this task as the intended desktop user from a terminal within the graphical
session. It intentionally weakens a physical-access security control: the desktop will
remain visible while idle. GNOME manual locking remains available; XFCE's master locker
is disabled, so its manual lock command is unavailable too. The task does not alter
automatic suspend/hibernate, lid actions, brightness dimming, low-battery policy,
display-manager login screens, or third-party lockers such as `xscreensaver` and
`light-locker`.

### Agent configuration

`configure_agents` manages explicit values in `~/.codex/config.toml` and
`~/.claude/settings.json`. The desired values live in `CODEX_VALUES` and
`CLAUDE_VALUES` in `prepare_debian/tasks/configure_agents.py`, so another supported
setting can be added without replacing either config file. The initial policy disables
Codex commit attribution and all Claude commit, pull-request, and session-link
attribution. Invalid existing Claude JSON fails without overwriting that file.

The same task checks for the `codex` and `claude` commands and, when either is
missing, downloads and executes that vendor's current official standalone installer:

- Codex: `https://chatgpt.com/codex/install.sh` with `sh`.
- Claude: `https://claude.ai/install.sh` with `bash`.

These installer URLs execute current external code and are not version-pinned by this
project. After installation the task locates the command on `PATH` or under
`~/.local/bin` and verifies `--version`. The task adds `~/.local/bin` to `.profile`,
`.bashrc`, and `.zshrc`; start a new shell after the first run. Installers run without
prompts, and a root invocation explicitly permits Claude's root-scoped installation.
Signing in, choosing an account, and configuring API credentials remain manual steps.

The `coding_agent_helpers` repository is synchronized under
`~/tools/coding_agent_helpers` at the reviewed commit in
`prepare_debian/repositories.py`. Each immediate child of its `skills/` directory that
contains `SKILL.md` is symlinked into both `~/.claude/skills` and
`~/.agents/skills`. Correct links are left unchanged and stale links owned by that
checkout are removed. A real file, directory, or link pointing elsewhere is preserved
and causes the task to fail rather than overwrite a user-owned skill.

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

Run the project quality checks:

```sh
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy prepare_debian tests
```

Tests isolate task calls and do not perform apt, Git, shell, profile, or remote
installer operations.

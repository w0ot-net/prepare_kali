# Plan: Make Task Execution Safe and Truthful

*Distilled: 2026-08-15*

## Summary

Require an explicit task selection, make every task return a truthful boolean result,
and propagate failures to the CLI exit status. Centralize the repeated subprocess
boundary so missing executables become normal failures rather than tracebacks. This
plan depends on the package and quality baselines from plans 01 and 02.

## Problem

Calling the runner with no arguments performs every mutation, including package
installation, remote cloning and installer execution, home-directory edits, and shell
changes for multiple accounts. The runner treats only literal `False` as failure,
while most task entrypoints return `None` and ignore failed helpers, so automation can
receive exit code 0 after failed work. Four modules duplicate thin `subprocess.run`
wrappers that raise when an executable is absent, apt incorrectly requires `sudo`
when already root, and `--force` has inconsistent or unused behavior.

## Scope

In scope:

- Make `--all` and repeatable `--task` arguments mutually exclusive and require one,
  so no-argument invocation exits with argparse usage and performs no work.
- Remove `--force` and its parameters; retain current idempotent state checks instead
  of adding task-specific compatibility meanings.
- Define each registered task as a no-argument callable that returns `True` only when
  its requested operations succeed and `False` when a prerequisite or operation fails.
- Propagate apt, Git, installer, profile, account-shell, and system-config failures
  through task results to a nonzero CLI exit code.
- Replace duplicated subprocess wrappers with one utility that captures output,
  catches command-start `OSError`, reports it, and lets callers return `False`.
- Let apt run directly as root and require `sudo` only for non-root callers; fail
  clearly when a command required by the selected path is unavailable.
- Add focused tests for argument selection, existing task order, fail-fast exit codes,
  missing executables, apt privilege selection, and task/helper result propagation.
- Update README safety, privilege, idempotence, side-effect, and exit-status contracts.

Out of scope:

- Changing the current sorted `--all` task order or which accounts
  `set_shell_to_bash` targets.
- Changing which profile files `prepare_impacket` creates, how it detects the export,
  or whether the configured examples directory exists.
- Re-rendering/deduplicating shell-default assignments, atomic replacement, backups,
  or automated rollback for `/etc` and profile files.
- Batching apt operations, relocating `xclip` package ownership, or otherwise
  redesigning package installation beyond correct privilege and failure handling.
- Pinning repositories or changing Git synchronization; plan 04 owns that outcome.
- Continuing after a failed selected task or adding structured result/telemetry types.

## Design

Keep the task registry and current sorted execution order. Put `--all` and `--task`
in a required argparse mutually exclusive group; argparse returns exit code 2 before
any banner or task call for missing/conflicting selection. Type registered tasks as
no-argument boolean callables, stop on the first false task, return 1, and print the
success/reload message only after every selected task succeeds.

Delete `--force` across the CLI, task functions, and helpers. Existing package,
profile, shell-setting, and repository checks remain the desired-state mechanisms;
reinstallation or destructive recovery stays an explicit manual operation.

Add `prepare_debian/utils/process_utils.py` with one `run` function used by apt, Git,
`chsh`, and installer callers. Return a captured `CompletedProcess` when the command
starts and `None` after warning on `OSError`. The owning caller retains its
operation-specific nonzero-exit diagnostic and maps either failure form to `False`.
Do not add a custom exception or result class.

Keep the current apt helper ownership and per-task operation shape. Add one internal
apt command-prefix decision: effective UID 0 invokes `apt-get` directly; a non-root
caller requires and prepends `sudo`. `update_apt_cache` and `ensure_apt_package`
return `False` for missing tools, command-start errors, or nonzero results. Existing
callers must consume the cache-update and each package result rather than continuing.

Convert current task paths without redesigning their state changes:

- `install_packages` returns false if cache update or any package install fails.
- `prepare_impacket` stops after an impacket package failure, makes its existing
  profile helper return false on any read/write failure, and returns that result.
- `set_tools` returns false if directory creation or any existing repository operation
  fails; it may continue attempting remaining configured repositories but must retain
  the aggregate failure.
- `set_bash_config` consumes cache, package, directory, repository, and installer
  results in order and runs the installer with the current Python interpreter.
- `set_shell_to_bash` returns false for missing Bash/root privilege, any failed `chsh`,
  or either caught config-file error while preserving its existing target and write
  algorithms. It may report all account failures before returning the aggregate result,
  but it prints the current “already set” success message only when no failure occurred.

Tests replace commands, identity/account data, home paths, and config paths with fakes
or temporary locations. They assert existing mutation logic only where needed to prove
that success and failure results reach the CLI; they do not specify deferred config
redesign.

## Affected Components

- `prepare_debian/cli.py`: require explicit selection, remove `--force`, establish the
  boolean task contract, and return truthful exit codes without changing task order.
- `prepare_debian/utils/process_utils.py`: own captured subprocess execution and
  command-start failure handling.
- `prepare_debian/utils/apt_utils.py`: use the shared runner, select root/sudo apt
  invocation, and return reliable results.
- `prepare_debian/tasks/*.py`: remove force parameters, consume owned helper results,
  and return aggregate boolean success without redesigning state mutations.
- `tests/test_cli.py`: extend coverage for selection, current order, fail-fast behavior,
  success output, and exit codes.
- `tests/test_process_utils.py`: cover successful, nonzero, and missing-executable
  command boundaries.
- `tests/test_apt_utils.py`: cover root, sudo, missing-command, update, and install paths.
- `tests/test_tasks.py`: cover each task's helper/result propagation with mocks and
  temporary paths.
- `README.md`: document explicit invocation, current execution order, privilege/effect
  scope, removal of force, failure semantics, and lack of automatic rollback.

## Implementation Sequence

1. Add the shared process utility and migrate every subprocess caller while preserving
   operation-specific output and command arguments.
2. Correct apt privilege selection and make every current update/install caller consume
   its result.
3. Remove `--force` and convert every task/helper boundary to explicit aggregate boolean
   success without changing its state-selection or rendering logic.
4. Require CLI selection and propagate false task results to fail-fast exit code 1.
5. Add isolated process, apt, task-propagation, and CLI contract tests.
6. Update README operational and safety contracts to match tested behavior.

## Validation

- `python -m pytest -q` passes with commands, accounts, home paths, and `/etc` paths
  isolated or mocked.
- Targeted tests prove missing or conflicting selection invokes no task and exits 2;
  any false task exits 1; an all-success run exits 0.
- Targeted tests prove `--all` preserves the current sorted order and the runner stops
  after the first false task.
- Targeted tests prove missing executables return normal task/CLI failure without a
  traceback and root apt commands do not require `sudo`.
- Task tests inject each helper/command/file failure and prove the owning task returns
  false without contradictory success output, while existing already-configured and
  successful paths return true.
- `python -m ruff check .`, `python -m ruff format --check .`, and
  `python -m mypy prepare_debian tests` pass.
- `prepare-debian --help` shows required explicit selection and no `--force` option.

## Success Criteria

- No invocation without an explicit task selection can mutate the machine.
- Every registered task returns `bool`; every selected operation's failure reaches a
  nonzero CLI exit status, and success is printed only after all selected work succeeds.
- Missing commands and expected OS/filesystem failures produce concise diagnostics,
  not uncaught subprocess exceptions or false success.
- Root and non-root apt paths use the correct privilege mechanism.
- Existing task order and mutation algorithms remain unchanged except for removed
  force-triggered repetition and failure short-circuit/aggregation.
- There is no remaining `--force` argument or duplicated task-level subprocess wrapper.

## Execution Notes

- Added the shared process runner, corrected root/non-root apt invocation, removed
  `--force`, required explicit task selection, and propagated boolean failures through
  all existing tasks and the CLI in commit `6d94e99`.
- Added focused CLI, process, apt, and task propagation tests without invoking real
  system commands or filesystem targets.
- Validated 22 passing tests, Ruff lint/format, mypy, CLI help output, `git diff --check`,
  and confirmed the shared utility owns the only production `subprocess.run` call.
- No repository synchronization behavior changed; mutable Git updates remained for
  Plan 04 as required by the scope boundary.

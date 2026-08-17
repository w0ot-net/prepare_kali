# Plan: Simplify CLI Task Selection and Messaging

*Distilled: 2026-08-16*

## Summary

Remove the misleading `--all` execution path and require users to select one or more
tasks explicitly with the existing repeatable `--task` option. Delete the unconditional
post-run Bash reload advice and update the focused CLI tests and README to describe the
simpler contract. This is a deletion-oriented cleanup and introduces no new execution
abstraction, task metadata, or privilege handling.

## Problem

The current `--all` option combines tasks that require incompatible execution contexts:
desktop and home-directory tasks must run as the intended graphical user, while
`set_shell_to_bash` requires effective root privileges. The README already advises
running those tasks separately, so presenting a universal run mode is misleading and
can make partial changes before it reaches a task that cannot succeed in that context.

The CLI also prints `Run: source ~/.bashrc` after every successful selection even when
the selected tasks did not modify Bash configuration. The README usage block contains
the `--all` example twice, adding a small but visible polish defect.

## Scope

In scope:

- Remove the `--all` argument and its dedicated execution branch.
- Make the existing repeatable `--task` argument required, preserving explicit task
  order and stop-on-first-failure behavior.
- Remove the unconditional `source ~/.bashrc` completion message without replacing it
  with global task-state tracking; tasks that need a follow-up message remain
  responsible for their own output.
- Update CLI tests for the explicit-selection-only contract, including rejection of
  missing selections and the removed `--all` option.
- Update the README usage, selection rules, task-order wording, and execution-context
  guidance; remove the duplicate example.

Out of scope:

- Adding privilege-aware task groups, automatic `sudo`/re-execution, task dependency
  metadata, callbacks, or per-task completion-message infrastructure.
- Retaining a deprecated `--all` compatibility alias; the project is version `0.1.0`
  and the option is the behavior being deliberately removed.
- Refactoring task implementations, utilities, CI, repository pins, or completed plan
  records.

## Design

Keep `TASKS` as the sole registry and `--task` as the sole execution interface. Define
the argument directly on the parser with `action="append"`, `required=True`, and the
existing sorted choices. `main` then has one loop over the names supplied by the user,
preserving their order, returning `1` on the first task failure, and returning `0` after
all selected tasks succeed.

Delete both global Bash reload messages. Do not add task result objects or metadata to
decide whether a reload hint is relevant: `prepare_impacket` already reports its own
shell follow-up, and any other task-specific advice belongs in that task.

Treat removal of `--all` as an intentional CLI contract change. Argparse will reject it
with status `2`, just as it rejects a missing required selection or an unknown task.
The README will demonstrate repeated `--task` arguments for intentional multi-task
runs and retain the warning that earlier successful tasks are not rolled back when a
later selected task fails.

## Affected Components

- `prepare_debian/cli.py`: remove the universal run mode and global Bash advice, leaving
  one explicit task execution path.
- `tests/test_cli.py`: replace `--all`-specific tests with focused coverage of required
  selection, removed-option rejection, explicit ordering, and failure propagation.
- `README.md`: document only supported explicit invocations and remove misleading or
  duplicated `--all` language.

## Implementation Sequence

1. Reduce the parser and runner to the required repeatable `--task` path and remove the
   global completion advice.
2. Update the existing CLI tests to assert the reduced interface and its unchanged
   success/failure behavior.
3. Align the README examples and execution-context guidance with explicit task
   selection.

## Validation

- `python -m pytest -q tests/test_cli.py` passes.
- Tests prove that no arguments and the removed `--all` option exit with argparse status
  `2` without running a task.
- Tests prove repeated `--task` selections run in the supplied order and stop at the
  first failure.
- `python -m pytest -q` passes.
- `python -m ruff check .`, `python -m ruff format --check .`, and
  `python -m mypy prepare_debian tests` pass.
- `prepare-debian --help` exposes `--task` but not `--all`, and a repository search finds
  no active-code or README references to `--all` or the global `source ~/.bashrc`
  message.

## Success Criteria

- Every invocation requires at least one explicit `--task`, with repeatable selections
  available for deliberate multi-task runs.
- The CLI no longer offers a mode that implicitly mixes root, desktop-session, and
  user-home task contexts.
- Successful unrelated tasks no longer emit Bash reload advice.
- Help text, README examples, and focused tests describe the same reduced contract.
- The change adds no new abstraction or execution state and leaves task behavior
  otherwise unchanged.

## Execution Notes

- Implemented in commit `d5103aa` by removing `--all`, requiring the existing
  repeatable `--task` argument, and reducing `main` to one explicit execution loop.
- Removed the unconditional Bash reload message. Task-specific follow-up output remains
  owned by the task that needs it.
- Updated only `prepare_debian/cli.py`, `tests/test_cli.py`, and `README.md`; no new
  abstraction, compatibility path, or privilege handling was added.
- Focused validation passed with 7 CLI tests, and the full suite passed with 47 tests.
  Ruff lint and formatting checks, mypy, help-output inspection, active-reference
  searches, and `git diff --check` also passed.
- There were no material deviations from the distilled plan and no unresolved items
  within its scope.

# Plan: Add Automated Quality Gates

*Distilled: 2026-08-15*

## Summary

Add one reproducible local and CI quality workflow for the packaged project from
plan 01. Introduce focused smoke tests, lint/format checks, and static type checks
without changing runtime behavior or adding abstractions solely for tooling.

## Problem

The repository has no test suite, declared development dependencies, formatter or
linter configuration, type-checking baseline, or CI. Contributors therefore have
no shared command set that proves imports, entrypoints, basic CLI wiring, style, or
annotations remain valid.

## Scope

In scope:

- Add bounded pytest, Ruff, and mypy development dependencies and their focused
  configuration to `pyproject.toml`.
- Add accurate annotations to existing functions and collections without changing
  runtime behavior or creating domain result types before plan 03 defines the task
  contract.
- Add smoke tests for import safety, task registration, argument parsing/help, and
  console/module entrypoint delegation, with every task call mocked.
- Add CI that installs the development extra and runs pytest, Ruff lint/format
  checks, and mypy on Python 3.9 and Python 3.12.
- Document the exact local quality commands.

Out of scope:

- Tests for truthful task results, system-command failures, or filesystem mutation;
  plan 03 adds those alongside the behavior they validate.
- Git synchronization and pinned-installer tests; plan 04 owns those.
- Refactoring production behavior to improve testability, enforcing a coverage
  threshold, or adding pre-commit/release automation.
- Packaging changes from plan 01 or selection of a software license.

## Design

Keep all tool configuration and the `dev` optional dependency in `pyproject.toml`
so installation and commands have one documented owner. Use Ruff for both linting
and formatting, pytest as the sole test runner, and a practical mypy configuration
that checks every project function while allowing return types to describe current
behavior until plan 03 tightens them.

Annotations are a bounded mechanical migration across `prepare_debian`; they must
describe existing values and must not introduce generic interfaces, result classes,
or compatibility branches for the checker. Smoke tests import the package and
exercise CLI parsing/delegation with the registry replaced by fakes so they cannot
run apt, Git, shell changes, profile writes, or remote installers.

Pin CI actions to full commit SHAs, grant read-only repository permissions, and run
the same commands documented for local use. The Python matrix checks the declared
minimum plus one newer interpreter without adding an unsupported-platform promise.

## Affected Components

- `pyproject.toml`: add the development extra and pytest/Ruff/mypy configuration.
- `prepare_debian/*.py`, `prepare_debian/tasks/*.py`, `prepare_debian/utils/*.py`:
  add accurate annotations and apply the configured formatter without behavior changes.
- `tests/test_cli.py`: cover imports, registry wiring, help/parsing, and both supported
  entrypoint delegates without invoking real tasks.
- `.github/workflows/ci.yml`: run the documented checks on the Python matrix with
  pinned actions and least privilege.
- `README.md`: document development installation and exact test/lint/format/type-check
  commands.

## Implementation Sequence

1. Add bounded development dependencies and focused tool configuration to
   `pyproject.toml`.
2. Annotate and format the package mechanically, resolving checker findings without
   altering task behavior.
3. Add isolated CLI/import smoke tests.
4. Document the local commands.
5. Add the pinned, read-only CI workflow using the same commands.

## Validation

- In a clean temporary environment, `python -m pip install -e '.[dev]'` succeeds.
- `python -m pytest -q` passes without touching real commands, home paths, or system
  files.
- `python -m ruff check .` and `python -m ruff format --check .` pass.
- `python -m mypy prepare_debian tests` passes.
- CI runs the same checks successfully on Python 3.9 and Python 3.12.
- `git diff --check` and inspection confirm annotation/format changes did not alter
  task constants, subprocess arguments, control flow, or return behavior.

## Success Criteria

- One documented development installation provides every test/lint/format/type tool.
- The package has accurate annotations and passes pytest, Ruff, and mypy locally and
  in least-privilege CI on both configured interpreters.
- Smoke tests prove imports and CLI discovery/delegation are side-effect-free.
- No runtime behavior or production abstraction changed solely to satisfy tooling.

## Execution Notes

- Added the `dev` extra, focused pytest/Ruff/mypy configuration, pinned read-only CI,
  annotations, CLI smoke coverage, and local development commands in commit `eaa3295`.
- Preserved the existing agent configuration tests discovered after the plan was
  written; this was a bounded current-code correction with no scope change.
- Validated in a dedicated Python 3.12 virtual environment: 7 tests passed, Ruff lint
  and format checks passed, mypy reported no issues, and `git diff --check` passed.
- The host system Python correctly refused direct editable installation under PEP 668;
  validation used the clean virtual environment required by the plan instead.

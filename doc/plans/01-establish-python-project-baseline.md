# Plan: Establish the Python Project Baseline

## Summary

Turn the loose scripts into one installable `prepare_debian` package with a single
supported CLI and standard project metadata. Preserve task and runner semantics so
this structural migration can be implemented and validated independently; later
plans own quality automation and behavior changes.

## Problem

The repository has no package/build metadata or supported Python version. Its
generic top-level `tasks` and `utils` packages and several executable module
entrypoints leave the supported interface unclear, and users cannot install a
normal `prepare-debian` command.

## Scope

In scope:

- Add `pyproject.toml` with setuptools build metadata, a declared Python range,
  project metadata, package discovery, and a `prepare-debian` console entrypoint.
- Move `main.py`, `tasks/`, and `utils/` under one `prepare_debian` package and
  support both `prepare-debian` and `python -m prepare_debian` through the same CLI.
- Remove per-task shebangs and `if __name__ == "__main__"` blocks so task modules
  are internal implementation, not partially supported CLIs.
- Update the README with installation, supported entrypoints/Python, current task
  effects, and privilege/network prerequisites.

Out of scope:

- Test/lint/format/type-check configuration and CI; plan 02 owns that independent
  quality-gate outcome.
- Unsafe defaults, task failure propagation, command robustness, and `--force`;
  plan 03 owns those behavior changes.
- External repository pinning and installer trust behavior; plan 04 owns that.
- Choosing a software license, which requires an explicit repository-owner/legal
  decision before a `LICENSE` file or package license metadata is added.
- Publishing distributions, release automation, or preserving undocumented imports
  such as `from tasks import ...`.

## Design

Use a flat `prepare_debian/` package rather than a `src/` layer for this small
application. Move the runner to `prepare_debian/cli.py`, add a minimal
`prepare_debian/__main__.py` that delegates to `cli.main`, and point the console
script at the same function. Move current modules mechanically to
`prepare_debian/tasks/` and `prepare_debian/utils/` and update imports to absolute
`prepare_debian.*` imports.

Declare Python 3.9 as the minimum supported interpreter and keep runtime
dependencies empty. Use setuptools package discovery and a fixed initial project
version; do not add development-tool dependencies or configuration in this plan.
Do not leave a top-level `main.py` wrapper because no published API, documented
caller, or compatibility policy requires it.

## Affected Components

- `pyproject.toml`: define the build backend, project metadata, supported Python,
  package discovery, and console entrypoint.
- `prepare_debian/__init__.py`: establish the package without exposing a speculative
  library API.
- `prepare_debian/__main__.py`: support module execution through the CLI owner.
- `prepare_debian/cli.py`: receive the mechanically moved runner.
- `prepare_debian/tasks/*.py`: receive task modules, absolute imports, and removal
  of standalone-script entrypoints.
- `prepare_debian/utils/*.py`: receive utility modules and absolute imports.
- `README.md`: document installation, supported invocation, Python support, task
  effects, prerequisites, and the current no-argument safety caveat.
- `main.py`, `tasks/`, `utils/`: remove after their contents move into the package.

## Implementation Sequence

1. Add minimal `pyproject.toml` project/build metadata and the console entrypoint.
2. Create `prepare_debian`, move the runner/tasks/utilities, update all imports, and
   remove obsolete standalone paths and task entrypoints.
3. Update the README for the installable package and describe current runtime
   behavior accurately without anticipating later behavior plans.

## Validation

- Create a temporary Python 3.9 virtual environment and run
  `python -m pip install .` successfully.
- `prepare-debian --help` and `python -m prepare_debian --help` produce equivalent
  successful help output without invoking a task.
- `python -m pip wheel --no-deps --wheel-dir <temporary-directory> .` builds a wheel;
  inspect its contents to confirm it contains `prepare_debian` and no caches, tests,
  or planning documents.
- `python -m compileall -q prepare_debian` succeeds.
- `rg -n "from (tasks|utils)|import (tasks|utils)" prepare_debian` finds no stale
  top-level imports, and tracked files contain no obsolete top-level package copies.

## Success Criteria

- A clean Python 3.9+ environment can install the repository and invoke one CLI by
  console command or module execution.
- Project modules live under `prepare_debian`; obsolete top-level execution/import
  paths are gone and no compatibility shim remains.
- The README accurately states installation, supported Python/invocation, task side
  effects and prerequisites, including the still-current no-argument behavior.
- Task ordering, failure handling, repository updates, and all other production
  semantics remain unchanged for subsequent plans.

# Plan: Fix Bugs and Design Issues

## Summary

Fix two runtime bugs (missing import, duplicate config lines) and three design issues (redundant apt updates, redundant repo clone, hardcoded root path) that affect correctness and performance.

## Problem

1. `apt_utils.py` uses `sys.stderr.write()` but never imports `sys` — crashes with `NameError` when `apt-get update` or `apt-get install` fails.
2. `set_shell_to_bash.py` appends duplicate `SHELL=` / `DSHELL=` lines to `/etc/default/useradd` and `/etc/adduser.conf` on every run when values already match, because the "not updated" fallback can't distinguish "key not found" from "key found and already correct".
3. `apt_utils.py` runs `apt-get update` once per package. With 6+ packages in `install_packages.py`, this is needlessly slow.
4. `bash_config` repo appears in both `set_tools.REPOS` and is explicitly cloned again by `set_bash_config.ensure_bash_config_repo`, causing redundant git operations when `--all` runs.
5. `set_tools.py` and `set_bash_config.py` hardcode `/root/tools` instead of using `Path.home()`, breaking for non-root users.

## Goal

- `apt_utils.py` handles errors without crashing.
- Config files are never corrupted with duplicate lines.
- `apt-get update` runs at most once per invocation.
- `bash_config` repo is cloned/updated exactly once during `--all`.
- Tools directory resolves from the current user's home.

## Design

### Phase 1 — Bug fixes (critical)

**1a. Add missing `import sys` to `apt_utils.py`.**

Add `import sys` to the imports.

**1b. Fix duplicate-line bug in `set_shell_to_bash.py`.**

Track whether the key was *found* in the file (separate from whether it was *updated*). Only append a new line when the key was never found.

For `/etc/default/useradd` (lines 43-55): introduce a `found` boolean set to `True` when `line.startswith("SHELL=")`. Only append when `not found` instead of `not updated`.

Same pattern for `/etc/adduser.conf` (lines 63-78): track `found` for `DSHELL=`.

### Phase 2 — Design improvements

**2a. Run `apt-get update` once, not per-package.**

Add an `update_apt_cache()` function to `apt_utils.py` that runs `apt-get update` once. Remove the update call from `ensure_apt_package`. Have `install_packages.main()` call `update_apt_cache()` before the package loop, and have `set_bash_config.main()` call it before its `ensure_apt_package` calls.

**2b. Remove `bash_config` from `set_tools.REPOS`.**

`set_bash_config` already handles cloning, updating, and installing `bash_config`. Remove the duplicate entry from `set_tools.REPOS` so it's managed in one place.

**2c. Replace hardcoded `/root/tools` with `Path.home() / "tools"`.**

Change `set_tools.TOOLS_DIR` to use `Path.home()`. Update `set_bash_config.run_install()` to derive the path from `set_tools.TOOLS_DIR` instead of its own hardcoded `/root/tools/bash_config`.

## Affected Components

- `utils/apt_utils.py`: Add missing `sys` import; extract `update_apt_cache()`; remove `apt-get update` from `ensure_apt_package`.
- `tasks/set_shell_to_bash.py`: Fix duplicate-line logic for both `/etc/default/useradd` and `/etc/adduser.conf` blocks.
- `tasks/install_packages.py`: Call `update_apt_cache()` before the package loop.
- `tasks/set_bash_config.py`: Call `update_apt_cache()` before package installs; derive repo path from `set_tools.TOOLS_DIR`.
- `tasks/set_tools.py`: Change `TOOLS_DIR` to `Path.home() / "tools"`; remove `bash_config` from `REPOS`.

## Execution Notes

Executed on 2026-03-07.

### Deviations from plan

- **1a skipped**: `import sys` was already present in the current `apt_utils.py` (fixed in a prior commit on remote).
- **2c partially done**: `set_bash_config.py` already used `set_tools.repo_dir()` instead of hardcoded path. `set_tools.py` had been changed to use `os.path.expanduser("~")` but was missing `import os` — fixed by switching to `Path.home()` which needs no extra import.

### Items implemented

- 1b: Added `found` boolean to both useradd and adduser.conf blocks in `set_shell_to_bash.py`
- 2a: Extracted `update_apt_cache()` in `apt_utils.py`; callers (`install_packages`, `set_bash_config`) call it before package installs
- 2b: Removed `bash_config` from `set_tools.REPOS`
- 2c: Changed `TOOLS_DIR` to `Path.home() / "tools"`

### Commits

- `6f234db`: Fix bugs and design issues across tasks and utils

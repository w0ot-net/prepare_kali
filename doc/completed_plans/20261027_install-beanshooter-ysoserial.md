# Plan: Install Beanshooter and ysoserial Under the Existing Tools Directory

## Summary

Add one root-run task that installs the latest official Beanshooter and
ysoserial release JARs under the existing `~/tools` directory, which resolves
to `/root/tools` for the expected root invocation. Expose both tools through
managed launchers in `~/.local/bin` and create `/opt/yso.jar` only as a
compatibility symlink to the real ysoserial JAR. Use upstream release artifacts
directly so the workstation does not need source clones or Maven builds.

## Problem

The project installs apt packages and synchronizes source-based tools under
`~/tools`, but it does not install Beanshooter or ysoserial. Neither tool is an
ordinary executable after a source clone: both are Java applications, and the
upstreams provide runnable release JARs. Beanshooter also defaults to looking
for ysoserial at `/opt/yso.jar`, while this project's established ownership
model keeps tools under the invoking account's `~/tools` directory.

## Scope

In scope:

- Ensure `default-jre-headless` is part of the apt package set and is available
  when the Java-tools task is selected directly.
- Add a dedicated `prepare_java_tools` task registered with the existing CLI.
- Discover the latest official GitHub release for `qtc-de/beanshooter` and
  `frohoff/ysoserial`, selecting only the expected executable JAR asset for
  each repository.
- Install the JARs under `~/tools/beanshooter/beanshooter.jar` and
  `~/tools/ysoserial/ysoserial.jar` using the existing `~/tools` owner.
- Record the installed release tags so an unchanged rerun avoids downloading
  the approximately 60 MB ysoserial artifact again.
- Install managed `beanshooter` and `ysoserial` shell launchers in
  `~/.local/bin` and reuse the existing shell-profile PATH setup.
- Create `/opt/yso.jar` as an absolute symlink to the installed ysoserial JAR,
  satisfying Beanshooter's default configuration without relocating the tool.
- Make downloads and managed-file replacements atomic, validate downloaded
  JARs, preserve conflicting unmanaged paths, and propagate failures.
- Add focused tests and update the nearest README task contract.

Out of scope:

- Moving existing repositories or other tools from `~/tools` to `/opt`.
- Cloning either Java project, installing Maven, compiling source, or using the
  Beanshooter container image.
- Pinning release versions or maintaining project-owned artifact checksums;
  the task follows current upstream releases like the existing unpinned tool
  checkouts.
- Overwriting a pre-existing unmanaged launcher, JAR destination, or
  `/opt/yso.jar` entry.
- Adding uninstall, rollback, offline-cache, or non-root installation modes.
- Refactoring the general repository synchronizer or unrelated download code.

## Design

Keep Git repository synchronization unchanged. Add
`prepare_debian/tasks/prepare_java_tools.py` as the single owner of the two
release-artifact installations. The task must require effective root
privileges before changing anything because the agreed compatibility symlink
is under `/opt`. It should reuse `set_tools.ensure_tools_dir()` and
`set_tools.TOOLS_DIR`, preserving the current `Path.home() / "tools"`
invariant rather than hard-coding `/root/tools`; in the normal root-run workflow
this resolves to `/root/tools`.

Represent the two tools with a small immutable specification containing the
display name, GitHub repository, expected asset-name pattern, destination JAR,
and launcher name. This single abstraction has two real consumers and keeps
release lookup and installation behavior identical. Query GitHub's latest
release API using the standard library, require exactly one matching asset
(`beanshooter-*-jar-with-dependencies.jar` or `ysoserial-all.jar`), and reject
missing, duplicate, or malformed release data. Releases remain intentionally
unpinned.

Store a managed release-tag file beside each stable JAR name. A matching tag is
only considered current when the destination is also a valid ZIP/JAR containing
a manifest with a main class; otherwise redownload it. Stream a new asset to a
temporary file in the destination directory, validate it before installation,
set ordinary read permissions, and atomically replace the stable JAR. Write the
tag only after the JAR replacement succeeds. A lookup, download, or validation
failure must leave the previously installed JAR usable and return task failure.

Use small managed POSIX-shell launchers under `~/.local/bin`:

```sh
exec java -jar "/absolute/path/to/tool.jar" "$@"
```

Reuse `configure_agents.ensure_local_bin_on_path()` rather than introducing a
second profile-management abstraction. A launcher carrying the task's managed
marker may be updated atomically; any unmarked file or symlink at the same path
must be preserved and reported as a failure.

After ysoserial is valid, create `/opt/yso.jar` as an absolute symlink to
`~/tools/ysoserial/ysoserial.jar`. An existing symlink to that exact target is
already correct. Any regular file, directory, dangling symlink, or symlink to a
different target is user-owned state: preserve it and fail with a clear
diagnostic. Read the link back after creation so success means the compatibility
path actually resolves to the managed JAR.

Add `default-jre-headless` to the central apt package list. The Java-tools task
also calls the existing `apt_utils.ensure_apt_package()` check so direct
`--task prepare_java_tools` execution is self-contained, following the existing
`prepare_impacket` pattern. Verify `java` is discoverable before any release
download. During a full run, alphabetical task ordering keeps
`install_packages` before `prepare_java_tools`, avoiding a redundant package
installation.

No new general downloader, repository type, package manager, or configuration
format is needed. The release-tag files are the minimum state needed to avoid
large repeated downloads; actual JAR and symlink validation remains the source
of truth.

## Affected Components

- `prepare_debian/tasks/prepare_java_tools.py`: own release discovery, atomic
  JAR installation, launchers, compatibility symlink, root/package checks, and
  idempotent update behavior.
- `prepare_debian/tasks/install_packages.py`: include
  `default-jre-headless` in the normal apt package set.
- `prepare_debian/cli.py`: register `prepare_java_tools` so full and selected
  runs can execute it.
- `tests/test_prepare_java_tools.py`: cover release selection, valid and
  invalid artifacts, unchanged and updated releases, atomic failure behavior,
  launcher conflict preservation, symlink verification/conflicts, and root and
  Java prerequisites.
- `tests/test_tasks.py`: retain package-list coverage for the Java runtime.
- `tests/test_cli.py`: include the new task in the public task registry
  contract.
- `README.md`: document the task, root/network requirements, `~/tools` paths,
  launchers, latest-release policy, and the single `/opt/yso.jar` symlink.

## Implementation Sequence

1. Add the Java runtime to the apt package contract and register the empty task
   boundary so its ordering and root requirement are explicit.
2. Implement and unit-test latest-release selection plus atomic, validated,
   tag-aware JAR installation under `set_tools.TOOLS_DIR`.
3. Implement and test managed launchers, PATH reuse, and the conflict-safe
   `/opt/yso.jar` symlink.
4. Compose prerequisite checks and both tool specifications in the task entry
   point, ensuring every failure stops the task without replacing unrelated
   state.
5. Update the README and run focused and complete validation.

## Validation

- `python -m pytest -q tests/test_prepare_java_tools.py tests/test_tasks.py tests/test_cli.py`
  proves the focused task, package, and CLI contracts without changing the host.
- Tests use local in-memory JAR fixtures and mocked release responses to verify
  exact asset selection, main-class validation, tag-based idempotence, atomic
  replacement, preserved prior installs on failure, and unmanaged-path safety.
- `python -m pytest -q`, `python -m ruff check .`,
  `python -m ruff format --check .`, `python -m mypy prepare_debian tests`, and
  `git diff --check` pass.
- In a disposable Kali VM, run
  `python3 main.py --task prepare_java_tools` as root and verify:
  - the two JARs exist below `/root/tools` and contain runnable main classes;
  - `beanshooter -h` and `ysoserial` invoke the expected applications;
  - `/opt/yso.jar` is an absolute symlink to the installed ysoserial JAR;
  - a second run reports both current without downloading them again; and
  - replacing a launcher or `/opt/yso.jar` with unmanaged content causes a
    clear failure without overwriting it.

## Success Criteria

- A normal root execution installs a Java runtime plus current official
  Beanshooter and ysoserial release JARs under `/root/tools`.
- Both commands are available through `~/.local/bin` and pass arguments and
  binary output through without modification.
- Beanshooter finds ysoserial through `/opt/yso.jar`, whose only role is an
  exact symlink back to the managed JAR under `~/tools`.
- Reruns are idempotent, newer release tags update the corresponding JAR, and a
  failed update leaves the prior installation intact.
- Existing tools remain under `~/tools`; no other files are moved into `/opt`.
- Conflicting unmanaged paths are preserved and reported rather than silently
  replaced.

## Execution Notes (2026-10-27)

### Implemented

- Added the root-only `prepare_java_tools` task and registered it for selected
  and default runs.
- Added `default-jre-headless` to the apt package contract and retained a
  direct package check for standalone task execution.
- Added latest-release discovery and atomic, tag-aware installation of the
  official Beanshooter and ysoserial JARs below the existing `~/tools` owner.
- Added managed launchers under `~/.local/bin` and reused the existing profile
  PATH configuration.
- Added the exact `/opt/yso.jar` compatibility symlink while preserving any
  conflicting unmanaged path.
- Documented the paths, update behavior, root requirement, and `/opt` boundary.

### Changed Files and Ownership Boundaries

- Added `prepare_debian/tasks/prepare_java_tools.py` as the sole owner of Java
  release discovery, JAR state, launchers, and the compatibility symlink.
- Updated `prepare_debian/tasks/install_packages.py` and
  `prepare_debian/cli.py` for the package and public task contracts.
- Added `tests/test_prepare_java_tools.py` and updated the existing package and
  CLI registry tests.
- Updated `README.md`; repository synchronization and all existing managed tool
  locations remain unchanged.

### Deviations

- No material implementation deviation was required. The disposable acceptance
  check used real upstream releases in temporary `tools`, home, and `opt`
  directories on the development host rather than mutating this host's
  `/root/tools` and `/opt` paths. Unit tests cover the root/package orchestration
  and the same path behavior.

### Validation

- `python3 -m pytest -q tests/test_prepare_java_tools.py tests/test_tasks.py tests/test_cli.py`:
  25 passed.
- `python3 -m pytest -q`: 91 passed.
- `ruff check .`: passed.
- `ruff format --check .`: 48 files already formatted.
- `mypy prepare_debian tests`: no issues in 34 source files.
- `git diff --check`: passed.
- A live temporary install downloaded Beanshooter `v4.1.0` and ysoserial
  `v0.0.6`, verified their real launchers and absolute compatibility symlink,
  and proved unchanged reruns do not redownload either JAR. Beanshooter's help
  invocation exits `1` and ysoserial's usage invocation exits `64` upstream;
  both emitted their expected application output through the managed launchers.

### Implementation Commit

- `b96a469` — Install Beanshooter and ysoserial under tools.

### Open Items

- No implementation blocker remains. The documented root invocation on a
  target Kali workstation remains the environment-specific acceptance check
  after pulling.

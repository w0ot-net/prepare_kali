# Plan: Install Coding Agent CLIs and Skills

## Summary

Extend the existing `configure_agents` task into the single user-level setup path for
Codex and Claude. It will keep attribution disabled first, install either official CLI
when missing, synchronize a pinned `w0ot-net/coding_agent_helpers` checkout, and expose
every valid helper skill to both agents through supported per-skill symlinks. This plan
depends on plans 03 and 04 for truthful task failures, shared process execution, and
pinned external repositories.

## Problem

The project can update Codex and Claude configuration values, but it assumes both CLI
programs and their skills have already been installed by hand. There is no managed
checkout for `coding_agent_helpers`, no discovery of the skills it contains, and no
safe installation path that keeps both agents on the same skill source. As a result, a
new workstation is not ready for either coding agent after the setup task succeeds.

## Scope

In scope:

- Keep the existing attribution settings as the first action in `configure_agents`.
- Install Codex and Claude only when their executables are absent, using the current
  official macOS/Linux standalone installer URLs.
- Download each installer over HTTPS to a temporary file, execute it with its documented
  shell without a shell pipeline, and verify the resulting CLI with `--version`.
- Add `https://github.com/w0ot-net/coding_agent_helpers` as a dedicated pinned repository
  specification and synchronize it under `~/tools/coding_agent_helpers` with the shared
  repository helper from plan 04.
- Discover immediate child directories of `skills/` that contain `SKILL.md` and create
  relative or absolute directory symlinks at `~/.claude/skills/<name>` and
  `~/.agents/skills/<name>`.
- Treat an existing correct managed symlink as success; preserve and report a conflict
  for any destination that is a real file/directory or points somewhere else.
- Remove only stale symlinks whose recorded target is inside the managed helper
  repository's `skills/` directory; never remove unrelated user skills.
- Return failure when configuration, download, installer execution, CLI verification,
  repository synchronization, skill discovery, or link installation fails.
- Add focused unit tests using temporary homes and mocked network/process/repository
  boundaries, plus concise README documentation.

Out of scope:

- Signing either CLI in, storing credentials, selecting accounts, or configuring API
  keys.
- Automatically updating a CLI that is already installed, selecting a CLI version, or
  implementing a general-purpose software updater.
- Copying skills into the repository, installing them through `gh`, creating a plugin or
  marketplace, or syncing local skills to either vendor's cloud products.
- Installing project-local skills, changing skill contents, or overwriting a user-owned
  skill with the same name.
- Reworking task ordering, adding another CLI task, or introducing a manifest/database
  solely to track managed links.

## Design

Keep `configure_agents` as the only public task because configuration, CLI availability,
and personal skills together form one agent-readiness outcome. Do not add a second task
or registry entry. `main` applies `CODEX_VALUES` and `CLAUDE_VALUES` before any network
or executable work, then ensures the two CLIs, synchronizes the helper checkout, and
installs its skills. It returns `False` immediately on a failed prerequisite so the
truthful CLI contract from plan 03 reports a nonzero exit status.

Represent each CLI with a small immutable specification containing its display name,
command name, official HTTPS installer URL, and interpreter (`sh` for Codex, `bash` for
Claude). A local helper first searches `PATH`, then `~/.local/bin`, so a just-installed
binary can be verified even before the user's shell reloads. If no executable is found,
download the installer with the Python standard library into a temporary file, run it
through the shared process utility, locate the command again, and call `--version`.
Never invoke a remote script through `shell=True` or interpolate downloaded content into
a command string. The installer source remains an explicit trust boundary documented in
the README; reproducible CLI version pinning is not part of this plan.

Add one dedicated `CODING_AGENT_HELPERS_REPOSITORY` specification beside the repository
policy introduced by plan 04. It is not part of the ordinary `set_tools` collection:
`configure_agents` synchronizes it directly so the result does not depend on the
alphabetical task order. Record and review a full commit SHA during implementation, and
use the existing origin, cleanliness, fetch, and exact-HEAD checks rather than creating
another Git wrapper.

After synchronization, enumerate only direct child directories under the checkout's
`skills/` directory and accept a child only when `SKILL.md` is a regular file. Sort names
for stable output. Ensure the two personal skill roots exist, then create one symlink per
skill. Both consumers point to the same checkout, so an intentional pin change updates
both without copied trees. Codex uses `$HOME/.agents/skills`; Claude uses
`$HOME/.claude/skills`. A reserved or conflicting destination fails clearly and remains
untouched. Cleanup is deliberately ownership-based: remove a missing/broken entry only
when the symlink text targets a child of this checkout's managed `skills/` directory.

Keep download, executable discovery, skill discovery, and symlink reconciliation as
small functions in `configure_agents.py`; they have one owner and do not justify new
framework modules. Tests replace the network download, shared process call, and Git
synchronizer. Filesystem behavior uses temporary directories so tests never install a
real CLI, contact GitHub, or write to the developer's home.

## Affected Components

- `prepare_debian/repositories.py`: add the dedicated, reviewed
  `coding_agent_helpers` repository specification after plan 04 establishes this module.
- `prepare_debian/tasks/configure_agents.py`: retain attribution policy and add CLI
  installation, pinned repository synchronization, skill discovery, safe symlink
  reconciliation, and truthful orchestration.
- `tests/test_agent_config.py`: retain config-preservation coverage and add focused
  tests for installed/missing CLI paths, failed installation, valid skill discovery,
  idempotent links, stale managed links, and user-owned conflicts.
- `README.md`: document the expanded task effects, official installer trust boundary,
  managed checkout, personal skill locations, collision policy, authentication exclusion,
  and the need to reload the shell if `~/.local/bin` was newly added to `PATH`.

## Implementation Sequence

1. Add and pin the dedicated helper repository specification, then route it through the
   repository synchronizer delivered by plan 04.
2. Add the two CLI specifications and the download/install/locate/version checks to
   `configure_agents`, preserving attribution configuration as the first operation.
3. Add deterministic skill discovery and ownership-safe symlink reconciliation for the
   Claude and Codex personal skill roots.
4. Compose those operations in the existing task with immediate, truthful failure
   propagation and concise status messages.
5. Add focused isolated tests and update the README to match the implemented behavior
   and trust boundaries.

## Validation

- `python -m pytest -q tests/test_agent_config.py` passes without network access or
  writes outside temporary directories.
- The focused tests prove an existing CLI skips its installer, a missing CLI is verified
  after installation, and every download/process/version failure returns `False`.
- Temporary-directory tests prove valid skills are linked into both personal roots, a
  second run is unchanged, stale managed links are removed, and unrelated conflicts are
  preserved and reported.
- Repository tests prove the helper checkout uses the reviewed full SHA and that sync
  failure prevents skill installation.
- `python -m pytest -q` passes after the targeted tests.
- A code review confirms there is no `shell=True`, no `gh`/npm dependency, no copied
  skill tree, and no path that replaces a non-managed destination.

## Success Criteria

- A successful `configure_agents` run leaves attribution disabled, both `codex` and
  `claude` locally executable, and every valid skill from the pinned helper checkout
  discoverable by both CLIs.
- Re-running the task is idempotent: installed CLIs are not reinstalled, the repository
  remains at its configured pin, and correct skill links are unchanged.
- Both agents consume the same reviewed skill source through their documented personal
  skill locations without duplicating files.
- Existing user-owned skills and unrelated links are never overwritten or removed, and
  any conflict or partial setup produces a nonzero task result with an actionable message.
- Authentication remains an explicit post-install user action, and the README clearly
  identifies the remote installer and external repository trust boundaries.

## Execution Notes

- Extended `configure_agents` to preserve attribution policy first, install/verify
  missing Codex and Claude CLIs, synchronize the pinned helper checkout, and reconcile
  per-skill links for both agents in commit `777e4d8`.
- Pinned `coding_agent_helpers` at
  `d064d8edd1750054b6531865f2b260a77909bf00`, resolved from upstream HEAD on
  2026-08-16.
- Added focused coverage for installed/missing/failed CLIs, download and version
  failures, idempotent/stale/conflicting skill links, and repository gating.
- Validated 38 passing tests, Ruff lint/format, mypy, `git diff --check`, and confirmed
  there is no `shell=True`, `gh`, npm, or copied-skill-tree implementation path.

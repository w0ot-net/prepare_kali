# Plan: Pin External Repositories

*Distilled: 2026-08-15*

## Summary

Replace mutable branch pulls with reviewed, immutable commit pins for every cloned
tool and for the `bash_config` code that is executed. Synchronization will verify
repository identity, cleanliness, and exact HEAD state without deleting local work.
This plan depends on the package, quality, process, and truthful-result contracts from
plans 01 through 03.

## Problem

`set_tools` clones repository default branches and runs `git pull --ff-only` on every
existing checkout. `set_bash_config` then executes `install.py` from the latest fetched
branch. A successful run can therefore install different code at different times,
and upstream changes become executable without a reviewed change in this repository.
Existing checkouts are also accepted solely because a `.git` directory exists; their
origin URL and resulting revision are never verified.

## Scope

In scope:

- Represent all eight tool repositories and the separate `bash_config` repository
  as immutable specifications containing a stable local name, expected HTTPS origin,
  and reviewed full 40-character commit SHA.
- Resolve and record the currently approved commit for every existing URL once during
  implementation; subsequent pin changes require an ordinary reviewed code change.
- Clone new repositories without checking out a mutable branch, fetch as needed, and
  detach at the pinned commit.
- For existing repositories, verify the expected origin, require a clean worktree,
  fetch without merging, check out the pinned commit, and verify actual HEAD equals
  the specification.
- Refuse to reset, clean, delete, merge, or overwrite a checkout with local changes or
  a mismatched origin, including after a failed prior run.
- Execute `bash_config/install.py` only after its checkout has passed the same identity
  and exact-revision verification, and announce its repository name and short pin.
- Add unit coverage for command/result mapping and temporary-local-Git integration
  coverage for new clone, exact-pin idempotence, pin advance/rollback, dirty checkout,
  wrong origin, missing revision, and failed fetch behavior.
- Document the managed-checkout contract, trust boundary, recorded pins, and manual
  review/update procedure.

Out of scope:

- Automatically tracking latest branches or creating a pin-update bot/script; mutable
  update automation would be an independently reviewable maintenance feature.
- Cryptographic commit/tag signature policy, sandboxing the installer, or auditing the
  contents of the external repositories.
- Recovering, stashing, rebasing, or deleting user modifications in managed checkout
  directories.
- Vendoring the external projects or converting them to Git submodules.

## Design

Add `prepare_debian/repositories.py` as the single source of external repository
policy. Define one frozen `RepositorySpec` value type with `name`, `url`, and
`revision` fields, a tuple for the eight ordinary tools, and one named specification
for `bash_config`. The abstraction is justified because both repository installation
and executable config installation consume the same identity/revision invariant.
Keep the full SHA visible in normal Python source so pin changes are easy to review;
do not add a parser, secondary lock format, or generated state.

Derive destinations from the explicit specification name, not from URL string parsing.
For a new destination, run `git clone --no-checkout <expected-url> <destination>`.
For an existing destination, require it to be a Git worktree, compare
`git remote get-url origin` with the expected URL, and require empty
`git status --porcelain`. Never use `git pull`.

Fetch origin without merging, verify the pinned object resolves as a commit, and run
`git checkout --detach <full-sha>` only after identity and cleanliness checks pass.
Finally compare `git rev-parse HEAD` to the full pin. If the object is already present,
the implementation may skip the network fetch only when the actual HEAD already equals
the pin; all other paths fetch so a newly recorded reachable pin can be obtained.
Every command-start or nonzero result maps to `False` through the shared process helper.
No recovery command may bypass the dirty/mismatched-origin checks.

`set_tools.main` iterates the ordinary tool specifications and returns false on the
first failed synchronization. `set_bash_config` passes its dedicated specification
through the same synchronization function and only then resolves and invokes the
installer with the running Python interpreter. Logging includes the repository name
and abbreviated expected revision so users and CI logs identify exactly what ran.

Integration tests must create bare and working repositories under pytest temporary
directories and use local paths as origins; they must not depend on GitHub or modify
`~/tools`. Mock only output or failure boundaries that cannot be represented with a
local repository. Unit tests also assert every production specification has a unique
name/URL and a lowercase full-length hexadecimal revision.

## Affected Components

- `prepare_debian/repositories.py`: own immutable repository identity and revision
  specifications for ordinary tools and `bash_config`.
- `prepare_debian/tasks/set_tools.py`: synchronize specifications to verified detached
  commits and enforce origin/clean-worktree/HEAD invariants.
- `prepare_debian/tasks/set_bash_config.py`: use the dedicated pinned specification and
  execute its installer only after exact-state verification.
- `tests/test_repositories.py`: validate completeness, uniqueness, and full immutable
  production pins.
- `tests/test_set_tools.py`: cover synchronization command failures and local-Git state
  transitions without network or home-directory writes.
- `tests/test_set_bash_config.py`: prove installation is gated on verified revision and
  propagates synchronization/interpreter/installer failures.
- `README.md`: document pinned-source behavior, checkout ownership, executed-code trust
  boundary, visible revisions, and the manual review-and-pin-update workflow.

## Implementation Sequence

1. Resolve each configured URL's approved current commit, review that the expected
   repositories and `bash_config/install.py` exist there, and add immutable specs.
2. Replace URL-derived clone/pull logic with specification-driven origin, clean-state,
   fetch, detached-checkout, and exact-HEAD verification.
3. Route ordinary tool setup and `bash_config` setup through the same verified sync
   function; gate and identify installer execution.
4. Add specification unit tests and temporary-local-Git integration tests for all
   accepted and refused state transitions.
5. Update README source-trust and pin-maintenance documentation.

## Validation

- `python -m pytest -q tests/test_repositories.py tests/test_set_tools.py tests/test_set_bash_config.py`
  passes without internet access or writes outside pytest temporary directories.
- Integration tests prove a fresh clone and a pre-existing clean clone both finish at
  the exact requested SHA, and a second run at that SHA is idempotent.
- Integration tests prove advancing or rolling back a pin reaches the newly specified
  SHA without `reset --hard`, while dirty, wrong-origin, and unavailable-pin cases fail
  without changing HEAD or local files.
- Installer tests prove no Python process starts unless Git HEAD equals the configured
  `bash_config` pin and that a failed installer reaches CLI exit code 1.
- `rg -n "git.*pull|pull.*--ff-only" prepare_debian tests` finds no production pull
  path, and inspection confirms every configured repository has one full SHA pin.
- The complete `python -m pytest -q`, Ruff, format, and mypy checks from plan 02 pass.

## Success Criteria

- Every external checkout ends at a reviewed full commit SHA recorded in this
  repository, so identical inputs select identical source code across runs.
- Existing checkout origin, cleanliness, commit availability, and final HEAD are all
  verified from Git state before success is returned.
- No update path merges a mutable branch or destroys/stashes local work, and unsafe
  checkout states fail with actionable diagnostics.
- `bash_config/install.py` can run only from the configured verified commit and its pin
  is visible to the user before execution.
- Tests validate synchronization behavior entirely with local temporary repositories,
  and the README explains how pins are reviewed and intentionally updated.

## Execution Notes

- Added immutable specifications for all eight tools and `bash_config`, synchronized
  clean matching-origin worktrees to detached exact revisions, and gated installer
  execution on verification in commit `41ec43f`.
- Recorded upstream HEAD commits resolved on 2026-08-16 and confirmed the pinned
  `bash_config` revision contains `install.py`.
- Added local temporary-Git coverage for fresh/idempotent sync, pin advance/rollback,
  dirty preservation, wrong origins, unavailable revisions, and installer gating.
- Validated 29 passing tests, Ruff lint/format, mypy, `git diff --check`, and confirmed
  no production `git pull` path remains.

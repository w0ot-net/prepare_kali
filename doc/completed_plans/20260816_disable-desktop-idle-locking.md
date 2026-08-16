# Plan: Disable Desktop Idle Locking and Blanking

*Distilled: 2026-08-16*

## Summary

Add one explicit per-user task that detects whether the current graphical session is
GNOME or XFCE and disables that desktop's automatic idle lock and display blanking
through its native settings interface. The task will preserve manual locking and
unrelated power preferences, read back every changed value, and fail clearly when it
cannot identify or configure the active desktop. This plan depends on plan 03 for the
shared process runner and truthful task/CLI failure contract.

## Problem

`prepare_debian` does not currently manage desktop idle behavior. A configured machine
can therefore blank and automatically lock its display while unattended even when the
desired workstation policy is to leave the active session visible. GNOME stores this
policy in GSettings, while XFCE splits it between xfce4-screensaver and
xfce4-power-manager, so one hard-coded command cannot correctly cover both desktops.

## Scope

In scope:

- Add a `disable_screen_lock` task to the existing CLI task registry and `--all` run.
- Detect the current GNOME or XFCE session case-insensitively from
  `XDG_CURRENT_DESKTOP`, with `DESKTOP_SESSION` as the fallback.
- On GNOME, set `org.gnome.desktop.session idle-delay` to `uint32 0` and
  `org.gnome.desktop.screensaver lock-enabled` to `false`.
- On XFCE, set `/saver/idle-activation/enabled` and
  `/lock/saver-activation/enabled` to `false` in the `xfce4-screensaver` channel,
  and `/xfce4-power-manager/dpms-enabled` to `false` in the
  `xfce4-power-manager` channel.
- Use `gsettings` or `xfconf-query` as appropriate, create explicitly typed XFCE
  properties when defaults are not yet stored, and read every value back before
  reporting success.
- Treat already-correct values as success and preserve all settings outside the
  explicit desired-value lists.
- Return `False` for an unknown/ambiguous desktop, a missing native settings command,
  a command failure, or a read-back mismatch.
- Add focused unit tests with environment and process boundaries replaced, and document
  the new task's user/session requirements and security effect.

Out of scope:

- Disabling manual lock commands or shortcuts; users must still be able to lock the
  session deliberately.
- Changing automatic suspend, hibernate, lid-close behavior, brightness dimming, or
  low-battery actions.
- Configuring GDM/LightDM login screens, system-wide dconf policy, every local account,
  remote sessions, or desktop environments other than GNOME and XFCE.
- Supporting legacy screen-locker replacements such as `xscreensaver` or
  `light-locker` when they are configured instead of the active desktop's native
  screensaver.
- Adding an enable/restore mode, backups, a daemon, an autostart entry, or an `xset`
  fallback.
- Installing GNOME/XFCE packages or starting a graphical session when the task is run
  from a TTY or SSH environment.

## Design

Create `prepare_debian/tasks/disable_screen_lock.py` as the sole owner of this desktop
policy. Keep two small constant desired-value collections—one for GNOME and one for
XFCE—and direct functions for detection, application, and verification. A general
desktop-settings abstraction is unnecessary because there are only two consumers with
different command contracts.

Desktop detection reads the actual process environment rather than inferring the
desktop from installed packages. Normalize the colon-separated `XDG_CURRENT_DESKTOP`
value and recognize GNOME variants such as `GNOME-Classic:GNOME` and
`ubuntu:GNOME`, or XFCE. Consult `DESKTOP_SESSION` only when the primary variable is
unset. If neither identifies exactly one supported desktop, stop without changing
settings and tell the user to run the task as the intended user from a terminal inside
that graphical session. Do not configure both backends merely because both packages
are installed.

For GNOME, use the shared process runner to set the two desired values with `gsettings`.
`idle-delay = uint32 0` disables idle screensaver activation and therefore blanking;
`lock-enabled = false` disables automatic locking when a screensaver activation occurs.
Query both keys after the writes and compare their serialized values to the desired
state. A missing command, schema, key, or writable setting is therefore handled by the
same command-failure or read-back path rather than a separate discovery layer.

For XFCE, require `xfconf-query` and set explicitly typed boolean properties, using its
create option when a fresh profile has not persisted the default property yet. Disable
idle activation rather than the screensaver's global enable switch so manual activation
remains available. Disable lock-with-saver rather than the global lock switch for the
same reason. Disable xfce4-power-manager DPMS to prevent its idle display sleep/off path
without changing system sleep, lid, or brightness settings. Query each property after
setting it and require `false` before success.

The task operates only on the current process user's desktop settings; it does not use
`sudo` or enumerate accounts. Its `main` function selects exactly one backend, stops on
the first failed prerequisite or write, and returns a truthful boolean. Register it in
the existing `TASKS` dictionary so explicit selection and `--all` use the same path.
No filesystem state, backup, or custom marker is needed because the native setting
values are the source of truth.

Tests provide explicit environment mappings and fake completed-process results. Cover
one representative GNOME identifier and one XFCE identifier, already-correct state,
unknown desktop, failed write, and read-back mismatch.
Do not launch a real desktop settings daemon or build a desktop/version matrix.

## Affected Components

- `prepare_debian/tasks/disable_screen_lock.py`: own desktop detection, the bounded
  GNOME/XFCE desired settings, native command execution, read-back verification, and
  truthful task result.
- `prepare_debian/cli.py`: import and register the explicit `disable_screen_lock` task.
- `tests/test_disable_screen_lock.py`: cover detection and the two backend command/result
  contracts without mutating the running desktop.
- `tests/test_cli.py`: after plan 03 creates the registry tests, include the new task in
  existing task-choice/order expectations.
- `README.md`: add the task to usage and the task table, explain that it changes only the
  invoking user's active session, list the supported desktops, and warn that automatic
  locking is a security control being intentionally disabled.

## Implementation Sequence

1. Add the desktop detector and the GNOME/XFCE desired-value definitions.
2. Implement each native backend with prerequisite checks, writes through the shared
   process runner, and direct read-back verification.
3. Compose the selected backend into a boolean task entrypoint and register it with the
   CLI.
4. Add focused backend/detection tests and update any registry expectation introduced by
   plan 03.
5. Document invocation context, exact effect, supported desktops, and security tradeoff
   in the README.

## Validation

- `python -m pytest -q tests/test_disable_screen_lock.py tests/test_cli.py` passes with no
  access to the real session bus or desktop settings.
- Tests prove GNOME receives only the two intended GSettings changes and XFCE receives
  only the three intended xfconf changes, followed by successful read-back.
- Tests prove an unknown desktop or any missing/failed/mismatched setting returns
  `False` without reporting success.
- `python -m pytest -q` passes after the focused tests.
- In a disposable GNOME session, `gsettings get org.gnome.desktop.session idle-delay`
  returns `uint32 0` and `gsettings get org.gnome.desktop.screensaver lock-enabled`
  returns `false` after the task runs.
- In a disposable XFCE session, `xfconf-query` returns `false` for the two screensaver
  properties and the power-manager DPMS property after the task runs.

## Success Criteria

- `prepare-debian --task disable_screen_lock` automatically selects and configures the
  active GNOME or XFCE session for the invoking user.
- The supported desktop no longer blanks the display or locks it because of idle time,
  on either AC power or battery power.
- Manual locking remains available, and suspend, lid, brightness, login-screen, and
  unrelated desktop preferences are unchanged.
- A second run is idempotent and verifies the same native settings rather than relying
  on project-owned state.
- Unsupported or unavailable desktop settings fail with a nonzero CLI result and a
  concise diagnostic instead of silently claiming success.

## Execution Notes

- Implemented in commit `b69194b` with environment-based desktop detection, native
  GNOME/XFCE settings commands, idempotent handling, and direct read-back verification.
- Registered the task with the CLI and documented its invocation context, bounded
  effect, and physical-access security tradeoff.
- Added focused tests for desktop detection, exact backend behavior, fresh XFCE
  properties, idempotency, command failure, read-back mismatch, and CLI registration.
- Validation passed with 47 tests, Ruff lint and formatting checks, mypy across the
  package and tests, and `git diff --check`.
- A disposable GNOME configuration run succeeded and read back `uint32 0` for
  `idle-delay` and `false` for `lock-enabled`.
- Live XFCE acceptance was unavailable because this host has no `xfconf-query` or XFCE
  session. The isolated tests exercise the exact query, typed-create, set, and read-back
  command contract without installing out-of-scope desktop packages.
- Corrected the README privilege wording for two existing package-management tasks so
  it remains accurate after the earlier safe-task-execution plan.

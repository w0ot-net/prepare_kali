# Plan: Enforce Desktop Idle Policy for All Users

## Summary

Extend `disable_screen_lock` so a root invocation from either GNOME or XFCE
installs a persistent, authoritative policy for every existing and future user.
Keep the current GNOME dconf implementation, add native system Xfconf policy for
XFCE, and install an XFCE-only login hook that reapplies the existing X11
screensaver and DPMS commands after each login. Non-root invocations remain
per-user and session-scoped.

## Problem

The task already installs a locked system dconf policy when root runs it from
GNOME, but root in XFCE still follows `configure_xfce()`, which changes only the
active Xfconf session and the current X server. Those values can belong to a
different graphical session than the root process, and the `xset` changes are
lost when a new X server starts, so another account or a session after reboot
can blank and lock again.

XFCE supports administrator defaults and locks through system
`xfce-perchannel-xml` files. Kali already owns files for all three affected
channels, so the task must merge its bounded properties without discarding the
distribution's unrelated settings. X11 screensaver and DPMS state is runtime
state, so it also needs a per-login application path rather than a one-time root
command.

## Scope

In scope:

- Preserve the current locked, all-user GNOME dconf behavior for root runs.
- When root runs the task from XFCE, configure the active session immediately
  and install persistent system policy for all existing and future XFCE users.
- Merge the existing eight boolean `XFCE_SETTINGS` paths into the corresponding
  system Xfconf channel files with value `false` and property-level locks.
- Preserve unknown channel properties, valid Kali defaults, and existing file
  modes; reject malformed XML, wrong channel roots, or ambiguous duplicate
  property paths rather than replacing them.
- Install an XFCE-only XDG autostart entry and a small managed shell helper that
  runs the existing `XFCE_X11_COMMANDS` on every graphical login.
- Make all new filesystem changes atomic, idempotent, directly verified, and
  truthfully propagated through the task result.
- Update focused tests and the nearest README task contract.

Out of scope:

- Applying both desktop backends from a TTY, SSH session, or an unidentified
  desktop; active-desktop detection remains required.
- Supporting XFCE on Wayland, desktop environments other than GNOME and XFCE,
  or third-party lockers such as `xscreensaver` and `light-locker`.
- Changing automatic suspend or hibernate, lid actions, brightness policy,
  low-battery actions, or display-manager login screens.
- Adding a daemon, timer, account-home enumeration, restore/uninstall mode, or
  package installation.
- Redesigning the existing GNOME policy or unrelated configuration-writing
  helpers.

## Design

Keep `disable_screen_lock.py` as the single owner. `main()` continues to detect
exactly one active desktop. A root GNOME run keeps calling
`configure_gnome_system()`. A root XFCE run first calls the existing
`configure_xfce()` so the current session is fixed and verified, then calls a
new `configure_xfce_system()` to install policy for subsequent sessions. A
non-root run continues to call only the existing per-user backend. This ordering
also makes reruns safe when the system policy already prevents Xfconf writes:
the desired values read back as `false`, so only current X11 runtime state needs
refreshing.

Use Xfconf's documented system configuration location,
`/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/`, and its kiosk property-lock
semantics. Add a narrow XML merge function that accepts one expected channel
and its target property paths, validates a single matching `<channel>` root,
walks or creates only the required nested `<property>` nodes, and writes each
leaf as `type="bool"`, `value="false"`. Mark each managed leaf with an
`unlocked` allowlist containing only Debian's non-login `nobody` account; Xfconf
therefore treats the value as locked for every login-capable account, including
root, without relying on undocumented wildcard behavior. Before writing,
resolve `nobody` and require a non-login shell. Remove a conflicting `locked`
attribute only on managed leaves, preserve all siblings and unrelated
attributes, and fail on duplicate path segments or incompatible parent types.
The root task updates the files directly on later runs, so no interactive user
needs permission to override the policy through Xfconf.

Map the existing settings to their native channel files:

- `/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-screensaver.xml`
  receives the five `xfce4-screensaver` paths.
- `/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-power-manager.xml`
  receives the two `xfce4-power-manager` paths.
- `/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-session.xml`
  receives `/shutdown/LockScreen`.

Reuse the existing atomic file-writing behavior and preserve modes. If a channel
file is absent, create a minimal valid channel document; do not copy a user's
configuration into the system location. After each write, parse the installed
file again and require every managed leaf to have the expected type, value, and
lock. Existing user overrides remain on disk but are ignored by Xfconf while the
system property is locked, which avoids destructive edits to home directories.
This follows upstream Xfconf's system-file and kiosk model rather than inventing
project-owned user state.

Render a project-owned executable at
`/usr/local/lib/prepare-debian/disable-xfce-idle` that runs `xset s off`,
`xset s noblank`, and `xset -dpms`, and a matching
`/etc/xdg/autostart/prepare-debian-disable-xfce-idle.desktop` with
`OnlyShowIn=XFCE;`. Validate the helper with `/bin/sh -n` before atomic
installation, use explicit absolute paths in the desktop entry, and verify
content and modes after installation. The hook is not a daemon: it runs once in
each XFCE graphical session, where `DISPLAY` and the session environment are
correct. The existing immediate `configure_xfce()` path remains responsible for
checking command success during the root invocation; future autostart execution
is intentionally bounded to login-time X11 state.

No new cross-desktop abstraction is needed. The system XML merge is justified
only by the three real Xfconf channel consumers, and direct parse/read-back plus
the existing command checks remain the source of truth.

## Affected Components

- `prepare_debian/tasks/disable_screen_lock.py`: add XFCE system-policy paths,
  bounded XML merging and verification, managed login-hook installation, and
  root-XFCE routing while preserving current GNOME and non-root behavior.
- `tests/test_disable_screen_lock.py`: cover XML preservation and rejection,
  locked values across all target channels, atomic/idempotent hook installation,
  failure propagation, and root versus non-root XFCE dispatch.
- `README.md`: state that root runs enforce persistent all-user policy for both
  GNOME and XFCE, explain the XFCE login hook, and retain the existing security
  and unsupported-locker boundaries.

## Implementation Sequence

1. Define the XFCE system file and login-hook constants from the existing
   `XFCE_SETTINGS` and `XFCE_X11_COMMANDS` contracts.
2. Add and test the narrow system Xfconf XML merge/read-back behavior, including
   preservation, lock semantics, missing files, and invalid inputs.
3. Add atomic rendering, shell syntax validation, and verification for the
   XFCE-only autostart helper and desktop entry.
4. Compose these operations in `configure_xfce_system()` and route root XFCE
   runs through immediate per-session configuration followed by system policy;
   keep non-root and GNOME routing unchanged.
5. Update focused documentation and run the complete quality suite.

## Validation

- `python -m pytest -q tests/test_disable_screen_lock.py tests/test_cli.py`
  proves the focused backend, dispatch, and failure contracts without touching
  the host desktop.
- XML fixture tests begin with representative Kali channel files and prove that
  all eight managed leaves are false and locked while unrelated theme,
  keyboard, power-button, failsafe-session, and array values survive.
- Tests cover a second identical run, missing system files, preserved modes,
  duplicate paths, malformed XML, wrong channels, an invalid `nobody` account,
  shell syntax failure, and failed atomic writes.
- `python -m pytest -q`, `python -m ruff check .`,
  `python -m ruff format --check .`, `python -m mypy prepare_debian tests`, and
  `git diff --check` pass.
- In a disposable Kali XFCE VM, run the task as root, verify the managed Xfconf
  values from an existing user and a fresh user, and confirm attempts to set a
  managed value to `true` are rejected. Log out and back in (and then reboot)
  and confirm `xset q` reports the screen saver and DPMS disabled with no
  automatic idle lock.
- Re-run the existing GNOME acceptance checks to confirm `idle-delay` remains
  `uint32 0`, `lock-enabled` remains `false`, and both keys remain non-writable
  under the root-installed dconf policy.

## Success Criteria

- A root invocation in GNOME continues to enforce no idle lock or blanking for
  every GNOME user across reboot.
- A root invocation in XFCE immediately disables the active session and causes
  every existing and future XFCE login, including root, to receive locked false
  values for all managed screensaver, locker, session, and power-manager keys.
- After an XFCE logout/login or reboot, the X11 screen saver and DPMS timers are
  disabled without rerunning the setup manually.
- Non-root invocations remain scoped to the active user and do not attempt
  system writes.
- Unrelated Kali Xfconf defaults and user files are preserved, malformed or
  unverifiable policy state produces a task failure, and reruns are idempotent.

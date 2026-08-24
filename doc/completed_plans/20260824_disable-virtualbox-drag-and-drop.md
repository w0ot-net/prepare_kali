# Plan: Disable VirtualBox Guest Drag and Drop

## Summary

Add one setup task that detects an Oracle VirtualBox guest and persistently disables
the Guest Additions drag-and-drop client in Kali's existing desktop-session launcher.
The task will leave the other X11 Guest Additions clients intact, stop any currently
running drag-and-drop client, and do nothing successfully on non-VirtualBox systems.

## Problem

Kali's VirtualBox Guest Additions session script starts
`VBoxClient --draganddrop` at desktop login. Failed drag-and-drop operations can leave
that client unstable and interfere with desktop input; restarting it only restores the
same failure-prone state. The project currently has no VirtualBox-specific setup task,
so a full setup run cannot disable that client persistently.

Current Kali packages use `/etc/X11/Xsession.d/98vboxadd-xclient` as the launch owner.
Its X11 branch starts clipboard, display, seamless-mode, and drag-and-drop clients
separately. Its Wayland branch uses one `VBoxClient --wayland` process for combined
desktop integration, so guaranteeing that drag and drop is disabled on Wayland also
disables the features bundled into that process.

## Scope

In scope:

- Add a `disable_virtualbox_drag_and_drop` task to the normal task registry and
  no-argument setup run.
- Detect VirtualBox directly with `systemd-detect-virt --vm`, accepting only its
  `oracle` identifier; treat other hypervisors and bare metal as successful no-ops.
- On a VirtualBox guest, require root privileges before changing the system Xsession
  launcher.
- Disable the active `/usr/bin/VBoxClient --draganddrop` launch command while leaving
  X11 clipboard, display resizing, host-version checking, and seamless mode unchanged.
- Disable the combined `/usr/bin/VBoxClient --wayland` launch command when present,
  retaining a shell `true` statement so its conditional branch remains syntactically
  valid.
- Make the edit idempotent, preserve the launcher's unrelated content and mode, and
  fail without writing when the launcher has an unexpected active command shape.
- Stop currently running `VBoxClient --draganddrop` and `VBoxClient --wayland`
  processes after the persistent change; accept “no matching process” as success.
- Add focused tests and document the behavior and Wayland tradeoff.

Out of scope:

- Changing the host VM's `VBoxManage` drag-and-drop setting; the guest setup script
  cannot reliably own host configuration.
- Installing, removing, upgrading, or restarting VirtualBox Guest Additions or
  `VBoxService`.
- Disabling X11 clipboard sharing, display resizing, host-version checking, or
  seamless mode.
- Preserving Wayland clipboard integration when the installed Guest Additions build
  exposes clipboard and drag-and-drop through the same client process.
- Supporting VMware, Hyper-V, QEMU, or arbitrary third-party VBoxClient launchers.
- Adding a service, background monitor, restore mode, or general system-file editing
  framework.

## Design

Create a direct task module as the sole owner of this policy. Detection will call the
existing process runner with `systemd-detect-virt --vm`; output equal to `oracle`
selects the VirtualBox path, a normal nonzero result or another identifier skips the
task, and inability to execute the detector is a truthful failure. This uses systemd's
documented VirtualBox identifier and avoids maintaining DMI heuristics.

For a detected VirtualBox guest, inspect
`/etc/X11/Xsession.d/98vboxadd-xclient`. If Guest Additions and this launcher are not
installed, report that there is nothing to disable. Otherwise, render a narrowly
modified copy: replace the active X11 drag-and-drop command with a stable managed
comment, and replace an active Wayland command with the managed explanation plus
`true`. Recognize those managed forms on later runs. Do not rewrite whitespace or any
other launcher commands.

Validate the rendered file with `/bin/sh -n` before replacing the installed launcher,
then preserve its mode. Refuse to write if drag-and-drop syntax is present in an
unrecognized active form, because silently leaving a new package layout enabled would
violate the task's result contract. Directly reread the installed file after the write
and require that neither managed client has an active launch command.

After persistence succeeds, use exact command-line matches to stop existing
drag-and-drop and combined Wayland clients. Treat `pkill` status 0 (processes stopped)
and 1 (none existed) as success; other statuses fail with a concise diagnostic. Do not
restart any VirtualBox process. This takes effect immediately while the edited session
launcher keeps drag and drop disabled after later logins.

The implementation needs task-local detection and rendering helpers only. No shared
abstraction is justified because no other task owns a package-managed session script
or VirtualBox process policy.

## Affected Components

- `prepare_debian/tasks/disable_virtualbox_drag_and_drop.py`: detect VirtualBox,
  validate and update the Guest Additions session launcher, and stop active
  drag-and-drop clients.
- `prepare_debian/cli.py`: register the task for explicit and default execution.
- `tests/test_disable_virtualbox_drag_and_drop.py`: cover VirtualBox selection,
  non-VirtualBox skips, exact/idempotent launcher transformation, preservation of
  useful X11 clients, malformed launcher rejection, and process-stop status handling.
- `tests/test_cli.py`: include the new public task in the registry contract.
- `README.md`: document the task, root requirement, retained X11 integrations, and
  combined Wayland-client tradeoff.

## Implementation Sequence

1. Add VirtualBox detection and the pure launcher transformation with explicit managed
   forms and unexpected-layout rejection.
2. Add root/file checks, pre-write shell validation, verified persistence, and exact
   current-process termination.
3. Register the task, add focused tests, and update the nearest README task contract.

## Validation

- `python3 -m pytest -q tests/test_disable_virtualbox_drag_and_drop.py tests/test_cli.py`
- `python3 -m pytest -q`
- `python3 -m ruff check .`
- `python3 -m ruff format --check .`
- `python3 -m mypy prepare_debian tests`
- `git diff --check`
- In a disposable Kali VirtualBox guest, run the task twice and verify both runs
  succeed, `/bin/sh -n /etc/X11/Xsession.d/98vboxadd-xclient` succeeds, no exact
  drag-and-drop/Wayland client process remains, and the X11 clipboard and display
  clients remain running.
- On a non-VirtualBox system, verify the task reports a skip and does not inspect or
  change the Xsession launcher.

## Success Criteria

- A default setup run on a VirtualBox guest prevents Guest Additions drag and drop from
  starting at subsequent desktop logins and stops the currently running client.
- Repeating the task is a successful no-op with the same verified launcher state.
- X11 clipboard, resizing, host-version, and seamless launch commands are unchanged.
- Non-VirtualBox systems are unchanged and do not fail the overall setup run.
- Missing prerequisites, insufficient privileges, malformed launcher content, shell
  validation failure, write/read-back failure, or a real process-control error produce
  a nonzero task result instead of a false success.

## Execution Notes (2026-08-24)

### Implemented

- Added `disable_virtualbox_drag_and_drop` to explicit task selection and the default
  setup run.
- Added Oracle VirtualBox detection, root enforcement, exact and idempotent launcher
  edits, pre-install shell validation, mode preservation, read-back verification, and
  exact process termination without restarting Guest Additions.
- Documented retained X11 integrations, the combined Wayland-client tradeoff, and the
  non-VirtualBox no-op behavior.

### Changed Files and Ownership Boundaries

- Added `prepare_debian/tasks/disable_virtualbox_drag_and_drop.py` as the sole owner of
  VirtualBox guest detection, launcher editing, and process termination.
- Updated `prepare_debian/cli.py`, `tests/test_cli.py`, and `README.md` for the public
  task contract.
- Added `tests/test_disable_virtualbox_drag_and_drop.py` for the task's focused
  behavior checks.
- Applied formatting-only updates to `main.py` and
  `tests/test_disable_screen_lock.py` so the repository's declared current Ruff check
  remains clean; no behavior changed in those files.

### Deviations

- Ruff 0.16, which satisfies the repository's declared `ruff>=0.8,<1` range, required
  small formatting updates in two existing files outside the named component list.
  This was a bounded mechanical correction needed for the plan's repository-wide
  validation and did not expand the feature boundary.

### Validation

- `python3 -m pytest -q tests/test_disable_virtualbox_drag_and_drop.py tests/test_cli.py`:
  15 passed.
- `python3 -m pytest -q`: 64 passed.
- `python3 -m ruff check .`: passed.
- `python3 -m ruff format --check .`: 42 files already formatted.
- `python3 -m mypy prepare_debian tests`: no issues in 30 source files.
- `git diff --check`: passed.
- `python3 main.py --task disable_virtualbox_drag_and_drop`: successful no-op on the
  non-VirtualBox development host without inspecting or changing the system launcher.
- A live disposable Kali VirtualBox guest was not available in this workspace; the
  exact packaged launcher shapes supplied for Kali are covered by the focused tests.

### Implementation Commit

- `60933a7de5a452bcd864919ffe02aaf021536063` — Disable VirtualBox guest drag and drop.

### Open Items

- No implementation blocker remains. Run the documented task twice in the target Kali
  VirtualBox guest as the environment-specific acceptance check after pulling.

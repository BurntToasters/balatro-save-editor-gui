# Failure modes (1.0.1 audit fixes)

Written before the fixes, per AGENTS.md. Each item names the E2E check that covers it
(`npm run e2e`, report in `e2e-artifacts/`).

## 1. Uninstaller deletes more than the app
- Install path typed as an existing folder (`D:\Games`): uninstall must leave every file the
  installer didn't put there. -> `installer: uninstall keeps foreign files`
- The install folder must always be a dedicated `Balatro Save Editor` folder, even when a parent
  folder is typed. -> `installer: forces dedicated folder`
- Uninstall must still remove everything the app installed (exe, `_internal`, uninstaller,
  shortcuts, uninstall registry key) and the folder itself when it ends up empty.
  -> `installer: uninstall removes app`

## 2. Joker actions race each other
- Double-clicking Delete must delete one joker, not two. -> `gui: double delete`
- Double-clicking Duplicate must add one joker. -> `gui: double duplicate`
- A joker action while a load or save runs must not hit the wrong save.
  -> `gui: joker action ignored while busy`
- A failed joker action must not leave buttons stuck disabled. -> `gui: joker buttons recover`

## 2b. Perishable sticker without a tally (second audit)
- Balatro's `Card:calculate_perishable()` compares `ability.perish_tally > 0`; a joker marked
  perishable without `perish_tally` errors at the end of a round. Turning Perishable on must
  also write `perish_tally` = the run's `GAME.perishable_rounds` (5 if missing).
  -> `gui: perishable gets a tally`
- A joker that already has a tally keeps it (don't reset a half-used one).
  -> `gui: existing tally kept`

## 3. Save write is not atomic
- An error halfway through writing must leave the original save byte-for-byte intact.
  -> `save: failed write keeps original`
- No temp files may be left next to the save, on success or failure. -> `save: no temp files`
- The written file must still round-trip (reload + validate). -> `save: round trip`
- A save Balatro briefly holds open (replace fails once) must still succeed on retry.
  -> `save: retries a locked replace`
- Added in the second audit: a save opened through a symlink (e.g. synced to another drive)
  must be written to the link's target; the link must stay a link. -> `save: symlink kept`
- The swapped-in file must keep the original's permissions (a temp file starts as owner-only on
  macOS/Linux). -> `save: permissions kept`

## 4. Closing the window drops unsaved edits
- Closing with unsaved edits must ask; "No" keeps the window open with edits intact.
  -> `gui: close asks when dirty`
- Closing with no edits must not ask. -> `gui: close quiet when clean`
- Restart after Reset settings (already confirmed in the page) must not ask again.
  -> `gui: restart does not double-ask`
- Added in the second audit: pywebview runs the closing handler on the GUI thread, and on macOS
  and GTK its confirmation dialog waits for that same thread, so asking from inside the handler
  freezes the app. The handler must return at once (close cancelled) and ask from another
  thread; Yes then closes the window. -> `gui: close handler returns without waiting`,
  `gui: close asks when dirty`, `gui: yes on the close prompt closes`
- Pressing close again while the prompt is up must not stack a second prompt.
  -> `gui: second close while asking is ignored`

## 5. Non-ASCII saves won't open
- A save with UTF-8 text (modded joker names) must load and show the text correctly.
  -> `save: utf-8 loads`
- Saving it must keep that text byte-exact. -> `save: utf-8 round trip`
- A save that isn't valid UTF-8 must still load and round-trip byte-exact (latin-1 fallback).
  -> `save: non-utf8 round trip`

## 6. Shortcuts land in the wrong profile
- Start menu and desktop shortcuts go to the all-users folders, and uninstall removes them from
  there. -> `installer: all-users shortcuts` (checked in the compiled script; writing to
  all-users folders needs admin, which the E2E run doesn't have)
- Added after the first E2E run: 1.0.0 put its shortcuts in the installing user's profile.
  Upgrading must remove those, or the Start menu shows the app twice; uninstall must remove them
  too. -> `installer: removes 1.0.0 per-user shortcuts`

## 7. Upgrading over an existing install
- Files from the previous version in `_internal` that the new version doesn't ship must be gone.
  -> `installer: upgrade drops stale files`
- A running copy of the app must stop the install with a message instead of half-overwriting it.
  -> `installer: refuses while app runs`

## 8. Empty or invalid number fields
- An empty or non-numeric Money / Mult / slot field must block Save with a message naming the
  field, and write nothing. -> `gui: empty money blocks save`
- An empty or invalid Sell value must not set 0; the field goes back to its old value with a
  message. -> `gui: empty sell reverts`

## 9. Backups pile up forever
- After a save, at most 10 of this save's backups remain (newest kept). -> `save: backups pruned`
- Files that aren't this save's backups (other saves, user files) are never touched.
  -> `save: prune leaves other files`

## 10. Save detection throws on an unreadable folder
- An unreadable profile folder must be skipped; the other profiles are still found.
  -> `paths: unreadable folder skipped`

## 11. GPG passphrase visible in the process list
- The passphrase must not appear in gpg's arguments; signing still works with a
  passphrase-protected key. -> `gpg: passphrase via stdin`

## 11b. Version bump (second audit)
- `npm run bump` must update `package-lock.json` too, or it drifts from `package.json`.
  -> `release: bump updates lockfile`
- An explicit pre-release (`1.1.0-beta.1`) must be accepted; release-policy already supports
  betas. -> `release: bump to pre-release`
- `patch`/`minor`/`major` from a pre-release must give a clean version (`1.1.0-beta.1` + patch =
  `1.1.0`, the release it was a beta of), never `NaN`. -> `release: bump from pre-release`
- Garbage input must fail without touching any file. -> `release: bad bump changes nothing`

## 11c. Building a pre-release (second audit)
- The PyInstaller spec split `1.1.0-beta.1` on dots into the Windows version resource
  (`filevers=(1, 1, 0-beta, 1)`), which isn't valid, so pre-release builds failed. The numeric
  fields must use the `x.y.z` core; the text fields keep the full version.
  -> `build: pre-release builds`, `build: exe version info`
- macOS `CFBundleShortVersionString` must be the numeric core too (Apple requires x.y.z).
  -> checked in the spec text on Windows (`build: mac bundle version`)

## 12. E2E runs leave no artifact
- Every E2E run writes a JSON report (each check, pass/fail, observed values) plus screenshots
  to `e2e-artifacts/`, and exits non-zero on any failure. -> the report itself

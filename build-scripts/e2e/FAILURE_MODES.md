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

## 2c. Editions only half applied (reported on 1.0.1)
Balatro 1.0.1 (card.lua, from the installed game) keeps a card's whole edition table in the
save and loads it as-is: `Card:set_edition` writes the effect value (`chips`=50 foil,
`mult`=10 holo, `x_mult`=1.5 polychrome), the flag, and `type`; `get_edition()` scores from
the value; the tooltip badge needs `type`. The editor wrote only the flag, so the shader showed
but the effect and badge didn't.
- Setting each edition must write the full table Balatro writes. -> `gui: editions are complete`
- Negative: every negative joker in play adds 1 to `cardAreas.jokers.config.card_limit`
  (`set_edition` / `add_to_deck` +1, `remove_from_deck` -1). The editor must keep that true:
  - make a joker negative: +1; take negative off (or switch to another edition): -1;
    switching between non-negative editions: 0 -> `gui: negative adds a slot`,
    `gui: removing negative takes the slot back`
  - delete a negative joker: -1; duplicate one: +1 -> `gui: negative delete/duplicate slots`
- Saves already edited by 1.0.0 / 1.0.1 (flag only, no `type`) must be repaired on load with
  the same rules (negative repaired = +1 slot), shown to the user, and written on the next Save.
  -> `gui: old half editions repaired`
- A complete edition written by the game must be left exactly as it is. -> `gui: game editions untouched`

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

## 13. Linux AppImage requires a newer glibc than the supported system
- EPEL 8 live mirrors can disappear or publish inconsistent metadata after EPEL 8 end of
  life. The build must use an immutable archived snapshot for its Qt native dependency. ->
  `linux: pinned compatibility build`
- Building on a current Linux host can make bundled CPython require that host's glibc. The
  AppImage must instead build in the pinned manylinux_2_28 environment. ->
  `linux: pinned compatibility build`
- Every ELF file in the PyInstaller bundle must require at most `GLIBC_2.28`; one newer
  transitive native dependency must fail the build before packaging. ->
  `linux: bundle within the glibc 2.28 baseline`
- The bundle must contain its Qt WebEngine backend instead of relying on whichever GTK/WebKit
  packages happen to exist on the build or target machine. -> `linux: Qt backend bundled`
- The frozen app must start on the glibc 2.28 baseline itself; missing native Qt dependencies
  must fail E2E. -> `linux: renders on real X11 (AlmaLinux 8, glibc 2.28 baseline)`

## 14. AppImage aborts on Linux Mint 21/22 with "Could not initialize GLX" (reported on 1.0.3, #17)
Reproduced in Ubuntu 22.04 / 24.04 containers (the Mint 21 / 22 bases) with Xvfb and the
distro's Mesa: `glxinfo` works, the frozen app core-dumps. PyInstaller copied the build image's
own `libstdc++.so.6` (GCC 8, at most `GLIBCXX_3.4.25`) into the bundle and its bootloader puts
the bundle first on `LD_LIBRARY_PATH`. The host's Mesa (`libGLX_mesa` -> `libgallium` ->
`libLLVM`) needs `GLIBCXX_3.4.26`-`3.4.32`, so it cannot load inside the app: Mesa 23 fails
context creation and Chromium aborts; Mesa 24+ makes libglvnd drop the vendor silently, Qt finds
no FBConfig and calls qFatal. The 1.0.3 E2E ran the app with `QT_QPA_PLATFORM=offscreen`, which
never opens an X11 window or loads GLX, so it passed.
- The bundle must not ship libraries the target's graphics stack and desktop provide
  (`libstdc++`, `libgcc_s`, `libgbm`, `libX11`, `libexpat`, `libz`, ... -
  `build-scripts/linux-host-libs.txt`, from the AppImage project's excludelist). One of them
  coming back must fail the build. -> `linux: host libraries not bundled`
- With `libstdc++`/`libgcc_s` from the host, no bundled ELF may need a C++ runtime newer than the
  glibc 2.28 baseline has (`GLIBCXX_3.4.25`, `CXXABI_1.3.11`, `GCC_7.0.0`), or the app fails on
  the oldest supported systems instead. -> `linux: bundle within the glibc 2.28 baseline`
- The host's GLX/EGL/GBM/DRI libraries must link exactly as well with the bundle on the library
  path as without it (no new missing versions or undefined symbols), on the baseline and on the
  Mint 21 / 22 bases. -> `linux: host GL stack loads beside bundle (<target>)`
- The app must render on a real X server with the target's own Mesa and no software-rendering
  overrides, stay running, and log no GL failures (`Could not initialize GLX`,
  `MESA-LOADER: failed`, `QRhiGles2: Failed`, ...). A blank window must fail too; the screenshot
  is kept. -> `linux: renders on real X11 (<target>)`
- A library left to the host that a target desktop does not have stops the app from starting
  (seen while testing: `libasound.so.2` on a minimal image). The E2E targets install only the
  packages that provide `linux-host-libs.txt`, plus X and Mesa, so a new host dependency fails
  there first. -> `linux: renders on real X11 (<target>)`

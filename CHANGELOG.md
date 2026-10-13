## ⬇️ Downloads

- **Windows - Installer:** [<u>x64</u>](https://github.com/BurntToasters/balatro-save-editor-gui/releases/download/v1.0.3/Balatro-Save-Editor-1.0.3-win-x64.exe) ([sig](https://github.com/BurntToasters/balatro-save-editor-gui/releases/download/v1.0.3/Balatro-Save-Editor-1.0.3-win-x64.exe.asc))
- **macOS - arm64 DMG:** [<u>arm64</u>](https://github.com/BurntToasters/balatro-save-editor-gui/releases/download/v1.0.3/Balatro-Save-Editor-1.0.3-mac-arm64.dmg) ([sig](https://github.com/BurntToasters/balatro-save-editor-gui/releases/download/v1.0.3/Balatro-Save-Editor-1.0.3-mac-arm64.dmg.asc))
- **Linux - AppImage:** [<u>x64</u>](https://github.com/BurntToasters/balatro-save-editor-gui/releases/download/v1.0.3/Balatro-Save-Editor-1.0.3-linux-x64.AppImage) ([sig](https://github.com/BurntToasters/balatro-save-editor-gui/releases/download/v1.0.3/Balatro-Save-Editor-1.0.3-linux-x64.AppImage.asc))

*GPG Pubkey: https://tuxedo.rosie.run/GPG/BurntToasters_0xF2FBC20F_public.asc*

## 1.0.3
* **FIX - Linux AppImage:** Fixed startup failures on Linux Mint 21.1 and other glibc 2.28+ systems. Linux builds now use a compatible glibc baseline and bundle the Qt webview backend instead of relying on system GTK/Python extensions. [#17]
  - The AppImage no longer ships its own copies of system libraries (C++ runtime, graphics, X11). They stopped your system's graphics drivers from loading, so the app crashed at launch with `Could not initialize GLX`.

## 1.0.2
* **Joker Editions:** Fixed an issue where only the joker addition shader was applied when adding/modifying jokers and not the actual gameplay modifier.

## 1.0.1
* **Saving:** `BSE GUI` now notices when Balatro changes your save while the app is open. It reloads automatically, or asks before overwriting if you have unsaved edits.
* **Safer saves:** Saves are now written to a temporary file first and then swapped in, so a crash mid-save can't corrupt your save. Backups are capped at the 10 newest per save.
* **Unsaved changes:** Closing the app with unsaved edits now asks before discarding them.
* **Jokers:** Fixed double-clicking Delete or Duplicate removing/adding two jokers.
  - Adding the Perishable sticker now also sets how many rounds the joker has left, so Balatro doesn't error at the end of the round.
* **Modded saves:** Saves containing non-English text (e.g. modded joker names) now open and save correctly.
* **Windows installer:** Uninstalling now only removes the app's own files, installs always go into their own `Balatro Save Editor` folder, and shortcuts are created for all users. Upgrading removes old version files and asks you to close the app if it's running.
* **Misc:** Empty or invalid number fields now show an error instead of saving 0, plus other small fixes and new end-to-end tests.

## 1.0.0
Welcome to the 1.0.0 release of Balatro Save Editor (GUI)!
A lot has changed since the last release lets break it down.
* **New - Theming:** The website and app have been fully overhauled to be a fun little balatro-like interface!
  - A flat UI mode was added to the app (toggleable at the bottom right of the sidebar)
* **Jokers:** Joker editing is now stable!
* **New - Joker search:** Users can now search the dropdown list for jokers when adding them to their save.
* **New - Joker Rarity:** In the dropdown menu jokers now have a dot before their name to show their rarity.
  - 🔵 Common | 🟢 Uncommon | 🔴 Rare | 🟣 Legendary
* **New - Update Checker:** Added an update checker that checks the apps version at launch (can be disabled in settings), and a manual update checker in settings!
* **New - Windows Codesigning:** Like my other apps, I have implemented `Azure Artifact Signing` to Balatro Save Editor GUI!
* **Misc:** Bug fixes, improvements to release flows, back-end testing enhancements, general fixes, api migrations to `gh cli` and more!!! 


<!-- Footer -->
*This app was made possible from the CLI code created by: https://github.com/problemsalved/balatro_save_editor Thank you!!*

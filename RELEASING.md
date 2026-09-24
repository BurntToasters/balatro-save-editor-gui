# Releasing

Builds are per-platform: run the matching command on a machine of that OS/arch
(PyInstaller cannot cross-compile). Signing secrets come from `.env` (copy
`.env.example`); GitHub access comes from the GitHub CLI's stored login.

## One-time setup

- `npm run venv` and `npm install`
- `.env` filled in (see `.env.example`)
- [GitHub CLI](https://cli.github.com/) installed and signed in on each release
  machine: `gh auth login`. `GH_TOKEN` / `GITHUB_TOKEN` are ignored by `publish`.
- A GPG secret key (`GPG_KEY_ID`)
- macOS: an Apple Silicon Mac with a native arm64 Python (Intel Macs aren't supported);
  a "Developer ID Application" cert in the keychain; notarytool credentials
- Windows: [NSIS](https://nsis.sourceforge.io/) (`makensis` on PATH)
- Linux: `appimagetool` on PATH

## Bump the version

```bash
npm run bump patch        # or minor | major | 1.2.3
```

Updates `package.json` and `app/__init__.py`. The release tag is `v<version>`.

## Release per platform

```bash
npm run release:mac     # Apple Silicon (arm64)
npm run release:win
npm run release:linux
```

Each command runs, in order:

| Step | mac | win | linux |
| --- | --- | --- | --- |
| `build` (PyInstaller) | ✓ | ✓ | ✓ |
| `sign:mac` (codesign, hardened runtime) | ✓ | – | – |
| `dist:*` (installer) | `.dmg` | `.exe` | `.AppImage` |
| `notarize:mac` (notarytool + staple) | ✓ | – | – |
| `sign:gpg` (detached `.asc` + `SHA256SUMS-<platform>.txt`) | ✓ | ✓ | ✓ |
| `publish` (draft GitHub release upload) | ✓ | ✓ | ✓ |

`build` auto-runs `licenses` first (a `prebuild` hook), which regenerates
`web/licenses.json` (bundled into the app for the in-app **Licenses** viewer) and
`THIRD_PARTY_NOTICES.txt` at the repo root.

Windows is GPG-signed only (no Authenticode). The release is left as a **draft**
on GitHub — review and publish it manually.

## Artifacts

Output lands in `release/`, named `Balatro-Save-Editor-<version>-<os>-<arch>`:

- installer (`.dmg` / `.exe` / `.AppImage`)
- `<installer>.asc` — detached GPG signature
- `SHA256SUMS-<os>-<arch>.txt` and its `.asc`

All are uploaded to the draft release for tag `v<version>`. Running a platform's
release again refreshes only that platform's assets.

## Verify

```bash
gpg --verify <installer>.asc <installer>
shasum -a 256 -c SHA256SUMS-<os>-<arch>.txt   # sha256sum -c on Linux
```

macOS notarization: `xcrun stapler validate <installer>.dmg`

## Useful extras

```bash
npm run publish:dry   # show repo/tag/assets without uploading
npm run test:scripts  # unit tests for the release helpers
npm run clean         # remove build/ dist/ release/
```

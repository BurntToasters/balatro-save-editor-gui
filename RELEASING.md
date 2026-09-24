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
- Windows: [NSIS](https://nsis.sourceforge.io/) 3.08+ (`makensis` on PATH); the Azure
  Artifact Signing `AZURE_*` values in `.env`; then once, as Administrator:
  `npm run setup:win:artifact-signing` (installs Microsoft's Artifact Signing Client Tools)
- Linux: `appimagetool` on PATH

## Bump the version

```bash
npm run bump patch        # or minor | major | 1.2.3
```

Updates `package.json`, then runs `npm run sync`: `app/__init__.py` and the download
and `.asc` links in the `## Downloads` section of `CHANGELOG.md` follow the new version.
The release tag is `v<version>`.

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
| `sign:win` (Authenticode on the app `.exe`) | – | ✓ | – |
| `dist:*` (installer) | `.dmg` | `.exe` (uninstaller + installer Authenticode-signed) | `.AppImage` |
| `notarize:mac` (notarytool + staple) | ✓ | – | – |
| `verify:win` (valid, timestamped, expected publisher + Subject DN) | – | ✓ | – |
| `sign:gpg` (detached `.asc` + `SHA256SUMS-<platform>.txt`) | ✓ | ✓ | ✓ |
| `publish` (draft GitHub release upload) | ✓ | ✓ | ✓ |

`build` auto-runs `licenses` first (a `prebuild` hook), which regenerates
`web/licenses.json` (bundled into the app for the in-app **Licenses** viewer) and
`THIRD_PARTY_NOTICES.txt` at the repo root.

Windows binaries are Authenticode-signed through Azure Artifact Signing before GPG
signing, so the `.asc` and checksums cover the signed installer. Every signature is
checked for a valid chain, an RFC 3161 timestamp, and the exact
`AZURE_ARTIFACT_SIGNING_PUBLISHER` / `AZURE_ARTIFACT_SIGNING_PUBLISHER_DN`.
`SKIP_WIN_CODESIGN=1` builds unsigned, and only for pre-release versions
(`1.2.0-beta.1`); stable `x.y.z` versions refuse it. `npm run dist:win` (no signing)
is still available for local test builds.

The release is left as a **draft** on GitHub — review and publish it manually.

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

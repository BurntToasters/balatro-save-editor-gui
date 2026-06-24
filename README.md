# Balatro Save Editor

This app was made possible from the CLI code created by: problemsalved https://github.com/problemsalved/balatro_save_editor Thank you!!

A cross-platform desktop GUI for editing [Balatro](https://www.playbalatro.com/) `save.jkr` files.

Forked from [problemsalved/balatro_save_editor](https://github.com/problemsalved/balatro_save_editor) the original command-line editor and wrapped in a [pywebview](https://pywebview.flowrl.com/) GUI. The Python parser (raw-deflate `zlib` + byte-exact recompression validation) is reused unchanged.

## Features

The editor auto-detects your Balatro save and lets you toggle any of these changes, then writes them back (creating a `.bak` backup first):

- **Money** – set your dollars to any value
- **Beat current blind** – set chips to one below the current blind target
- **Hand multipliers** – set the multiplier for every poker hand
- **Card slot limits** – raise joker and consumable slot counts
- **Remove "eternal"** – strip the eternal sticker from jokers
- **[Experimental] Joker Editing** - Add/Remove/Modify jokers and their enhancements

## Supported platforms

| OS | Installer | Save location |
| --- | --- | --- |
| Windows x64 | `.exe` (NSIS) | `%APPDATA%\Balatro\<profile>\save.jkr` |
| macOS (universal) | `.dmg` | `~/Library/Application Support/Balatro/<profile>/save.jkr` |
| Linux x64 | `.AppImage` | Steam Proton prefix (`compatdata/2379780/...`) |

If a save isn't found automatically, use **Open…** to pick the file manually.

## Development

Requires Python 3.14+ and Node 24+.

```bash
npm run venv      # create .venv and install Python deps
npm run dev       # launch the app from source
npm test          # run the pytest suite
npm run smoke:gui # drive the real window against a temp save
```

## Building

PyInstaller produces a standalone app for the platform you run it on (it cannot cross-compile, so build each target on its own machine).

```bash
npm run build         # PyInstaller bundle -> dist/
npm run smoke:runtime # launch the built app to confirm it starts
npm run dist          # wrap into the platform installer -> release/
```

## Releasing

See [RELEASING.md](RELEASING.md) for the signed, notarized, published release flow.

## Safety

Every write creates a timestamped `.bak` next to the save. After writing, the file is reloaded and re-validated (decompress → reparse → recompress must match), so a corrupt write is caught immediately. Editing save files is unsupported by the game; back up your saves.

## License

This project is licensed [MPL-2.0](LICENSE).

The save-parsing core is derived from [problemsalved/balatro_save_editor](https://github.com/problemsalved/balatro_save_editor) (the upstream repo has no separate license file; included with attribution to the original author).

Bundled third-party components (CPython, pywebview, pyobjc, etc.) and their licenses are listed in-app under the **Licenses** button, and written to `THIRD_PARTY_NOTICES.txt` on each build (`npm run licenses`).

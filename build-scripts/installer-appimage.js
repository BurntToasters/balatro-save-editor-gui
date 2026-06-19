'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { ROOT, RELEASE_DIR, productName, appName, arch, artifactBase, ensureReleaseDir } = require('./pkg');

if (process.platform !== 'linux') {
  console.error('AppImage packaging runs on Linux only.');
  process.exit(1);
}

const sourceDir = path.join(ROOT, 'dist', appName);
if (!fs.existsSync(path.join(sourceDir, appName))) {
  console.error(`Build not found: ${path.join(sourceDir, appName)}\nRun: npm run build`);
  process.exit(1);
}

const appDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bse-appdir-'));
const binDir = path.join(appDir, 'usr', 'bin');
fs.mkdirSync(binDir, { recursive: true });

function cleanup() {
  fs.rmSync(appDir, { recursive: true, force: true });
}

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: 'inherit', ...opts });
  if (r.error && r.error.code === 'ENOENT') {
    console.error(`${cmd} not found.`);
    cleanup();
    process.exit(1);
  }
  if (r.status !== 0) {
    cleanup();
    process.exit(r.status === null ? 1 : r.status);
  }
}

// Copy the PyInstaller onedir into usr/bin.
run('cp', ['-R', `${sourceDir}/.`, binDir]);

fs.writeFileSync(
  path.join(appDir, `${appName}.desktop`),
  `[Desktop Entry]
Type=Application
Name=${productName}
Exec=${appName}
Icon=${appName}
Categories=Utility;
Terminal=false
`,
);

fs.copyFileSync(path.join(ROOT, 'icon', 'icon-linux.png'), path.join(appDir, `${appName}.png`));

const appRun = path.join(appDir, 'AppRun');
fs.writeFileSync(
  appRun,
  `#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/${appName}" "$@"
`,
);
fs.chmodSync(appRun, 0o755);

ensureReleaseDir();
const outFile = path.join(RELEASE_DIR, `${artifactBase()}.AppImage`);
fs.rmSync(outFile, { force: true });

const appimageArch = arch() === 'arm64' ? 'aarch64' : 'x86_64';
run('appimagetool', [appDir, outFile], { env: { ...process.env, ARCH: appimageArch } });
cleanup();
console.log(`Created ${outFile}`);

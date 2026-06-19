'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { ROOT, RELEASE_DIR, productName, appName, version, arch, artifactBase, cleanReleaseDir } = require('./pkg');

if (process.platform !== 'linux') {
  console.error('AppImage packaging runs on Linux only.');
  process.exit(1);
}

const sourceDir = path.join(ROOT, 'dist', appName);
if (!fs.existsSync(path.join(sourceDir, appName))) {
  console.error(`Build not found: ${path.join(sourceDir, appName)}\nRun: npm run build`);
  process.exit(1);
}

// appimagetool is often an AppImage that needs FUSE; self-extract avoids that
// on headless VMs/containers where FUSE is unavailable.
const childEnv = { ...process.env, APPIMAGE_EXTRACT_AND_RUN: '1' };

if (spawnSync('appimagetool', ['--version'], { env: childEnv }).error) {
  console.error(
    'appimagetool not found on PATH.\n' +
      'Install it, e.g.:\n' +
      '  wget https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage\n' +
      '  chmod +x appimagetool-x86_64.AppImage && sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool',
  );
  process.exit(1);
}

const appDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bse-appdir-'));
const binDir = path.join(appDir, 'usr', 'bin');
fs.mkdirSync(binDir, { recursive: true });

function cleanup() {
  fs.rmSync(appDir, { recursive: true, force: true });
}

function run(cmd, args, opts = {}) {
  console.log(`$ ${cmd} ${args.join(' ')}`);
  const r = spawnSync(cmd, args, { stdio: 'inherit', env: childEnv, ...opts });
  if (r.error) {
    console.error(`${cmd} failed to start: ${r.error.message}`);
    cleanup();
    process.exit(1);
  }
  if (r.status !== 0) {
    console.error(`${cmd} exited with status ${r.status}.`);
    cleanup();
    process.exit(r.status === null ? 1 : r.status);
  }
}

console.log(`Staging AppDir at ${appDir}`);
run('cp', ['-R', `${sourceDir}/.`, binDir]);

fs.writeFileSync(
  path.join(appDir, `${appName}.desktop`),
  `[Desktop Entry]
Type=Application
Name=${productName}
Version=1.0
X-AppImage-Version=${version}
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

cleanReleaseDir();
const outFile = path.join(RELEASE_DIR, `${artifactBase()}.AppImage`);
fs.rmSync(outFile, { force: true });

const appimageArch = arch() === 'arm64' ? 'aarch64' : 'x86_64';
run('appimagetool', [appDir, outFile], { env: { ...childEnv, ARCH: appimageArch } });
cleanup();
console.log(`Created ${outFile}`);

'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { ROOT, RELEASE_DIR, macAppName, productName, artifactBase, cleanReleaseDir } = require('./pkg');

if (process.platform !== 'darwin') {
  console.error('DMG packaging runs on macOS only.');
  process.exit(1);
}

const appPath = path.join(ROOT, 'dist', `${macAppName}.app`);
if (!fs.existsSync(appPath)) {
  console.error(`App not found: ${appPath}\nRun: npm run build`);
  process.exit(1);
}

cleanReleaseDir();
const dmgPath = path.join(RELEASE_DIR, `${artifactBase()}.dmg`);
fs.rmSync(dmgPath, { force: true });

const staging = fs.mkdtempSync(path.join(os.tmpdir(), 'bse-dmg-'));

function cleanup() {
  fs.rmSync(staging, { recursive: true, force: true });
}

function run(cmd, args) {
  const r = spawnSync(cmd, args, { stdio: 'inherit' });
  if (r.status !== 0) {
    cleanup();
    process.exit(r.status === null ? 1 : r.status);
  }
}

run('cp', ['-R', appPath, path.join(staging, `${macAppName}.app`)]);
run('ln', ['-s', '/Applications', path.join(staging, 'Applications')]);
run('hdiutil', [
  'create',
  '-volname', productName,
  '-srcfolder', staging,
  '-ov',
  '-format', 'UDZO',
  dmgPath,
]);
cleanup();
console.log(`Created ${dmgPath}`);

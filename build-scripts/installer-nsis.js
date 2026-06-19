'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { ROOT, RELEASE_DIR, pkg, version, productName, appName, artifactBase, cleanReleaseDir } = require('./pkg');

if (process.platform !== 'win32') {
  console.error('NSIS packaging runs on Windows only.');
  process.exit(1);
}

const sourceDir = path.join(ROOT, 'dist', appName);
const exeName = `${appName}.exe`;
if (!fs.existsSync(path.join(sourceDir, exeName))) {
  console.error(`Build not found: ${path.join(sourceDir, exeName)}\nRun: npm run build`);
  process.exit(1);
}

cleanReleaseDir();
const outFile = path.join(RELEASE_DIR, `${artifactBase()}.exe`);
fs.rmSync(outFile, { force: true });

const nsi = path.join(__dirname, 'win', 'installer.nsi');
const icon = path.join(ROOT, 'icon', 'icon.ico');
const publisher = (pkg.author || '').replace(/<.*>/, '').trim() || 'BurntToasters';

const args = [
  `-DAPPNAME=${productName}`,
  `-DVERSION=${version}`,
  `-DPUBLISHER=${publisher}`,
  `-DSOURCE_DIR=${sourceDir}`,
  `-DEXENAME=${exeName}`,
  `-DICON=${icon}`,
  `-DOUTFILE=${outFile}`,
  nsi,
];

console.log(`$ makensis ${args.join(' ')}`);
const r = spawnSync('makensis', args, { stdio: 'inherit' });
if (r.error && r.error.code === 'ENOENT') {
  console.error('makensis not found. Install NSIS and ensure makensis is on PATH.');
  process.exit(1);
}
if (r.status !== 0) process.exit(r.status === null ? 1 : r.status);
console.log(`Created ${outFile}`);

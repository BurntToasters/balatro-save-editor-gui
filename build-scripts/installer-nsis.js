'use strict';

// --sign: Authenticode-sign the uninstaller (during compile) and the installer via
// Azure Artifact Signing. Release uses this; plain dist:win stays unsigned for local testing.

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { ROOT, RELEASE_DIR, pkg, version, productName, appName, artifactBase, cleanReleaseDir } = require('./pkg');
const { nsisSignCommand, signFile } = require('./win-codesign');

const sign = process.argv.includes('--sign');

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

// !uninstfinalize (signs the generated uninstaller) needs NSIS 3.08+.
function assertNsisCanSign() {
  const r = spawnSync('makensis', ['-VERSION'], { encoding: 'utf8' });
  const m = String(r.stdout || '').match(/v?(\d+)\.(\d+)/);
  if (!m || Number(m[1]) < 3 || (Number(m[1]) === 3 && Number(m[2]) < 8)) {
    console.error(`Signed builds need NSIS 3.08 or newer (found: ${String(r.stdout || 'none').trim()}).`);
    process.exit(1);
  }
}

cleanReleaseDir();
const outFile = path.join(RELEASE_DIR, `${artifactBase()}.exe`);
fs.rmSync(outFile, { force: true });

const nsi = path.join(__dirname, 'win', 'installer.nsi');
const icon = path.join(ROOT, 'icon', 'icon.ico');
const publisher = (pkg.author || '').replace(/<.*>/, '').trim() || 'BurntToasters';

let signDir = null;
if (sign) {
  assertNsisCanSign();
  signDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bse-nsis-'));
  fs.writeFileSync(path.join(signDir, 'sign.nsh'), `!uninstfinalize '${nsisSignCommand()}' = 0\n`);
}

const args = [
  `-DAPPNAME=${productName}`,
  `-DVERSION=${version}`,
  `-DPUBLISHER=${publisher}`,
  `-DSOURCE_DIR=${sourceDir}`,
  `-DEXENAME=${exeName}`,
  `-DICON=${icon}`,
  `-DOUTFILE=${outFile}`,
  ...(signDir ? [`-DSIGN_INCLUDE=${path.join(signDir, 'sign.nsh')}`] : []),
  nsi,
];

console.log(`$ makensis ${args.join(' ')}`);
const r = spawnSync('makensis', args, { stdio: 'inherit' });
if (signDir) fs.rmSync(signDir, { recursive: true, force: true });
if (r.error && r.error.code === 'ENOENT') {
  console.error('makensis not found. Install NSIS and ensure makensis is on PATH.');
  process.exit(1);
}
if (r.status !== 0) process.exit(r.status === null ? 1 : r.status);
if (sign) signFile(outFile);
console.log(`Created ${outFile}${sign ? ' (signed)' : ''}`);

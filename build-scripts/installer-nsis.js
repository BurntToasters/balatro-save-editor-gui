'use strict';

// --sign: Authenticode-sign the uninstaller (during compile) and the installer via
// Azure Artifact Signing. Release uses this; plain dist:win stays unsigned for local testing.
//
// E2E only (build-scripts/e2e): --source <dir> --out <file> --e2e-user-level --app-name <name>
// build a test installer from a fake app folder that installs without admin, under its own name
// so it never touches a real install's shortcuts. MAKENSIS overrides the binary.

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { ROOT, RELEASE_DIR, pkg, version, productName, appName, artifactBase, cleanReleaseDir } = require('./pkg');
const { nsisSignCommand, signFile } = require('./win-codesign');

const argv = process.argv.slice(2);
const flag = (name) => argv.includes(name);
const option = (name) => {
  const i = argv.indexOf(name);
  return i === -1 ? null : argv[i + 1];
};

const sign = flag('--sign');
const e2eUserLevel = flag('--e2e-user-level');
const makensis = process.env.MAKENSIS || 'makensis';

if (process.platform !== 'win32') {
  console.error('NSIS packaging runs on Windows only.');
  process.exit(1);
}

const sourceDir = path.resolve(option('--source') || path.join(ROOT, 'dist', appName));
const exeName = `${appName}.exe`;
if (!fs.existsSync(path.join(sourceDir, exeName))) {
  console.error(`Build not found: ${path.join(sourceDir, exeName)}\nRun: npm run build`);
  process.exit(1);
}

// !uninstfinalize (signs the generated uninstaller) needs NSIS 3.08+.
function assertNsisCanSign() {
  const r = spawnSync(makensis, ['-VERSION'], { encoding: 'utf8' });
  const m = String(r.stdout || '').match(/v?(\d+)\.(\d+)/);
  if (!m || Number(m[1]) < 3 || (Number(m[1]) === 3 && Number(m[2]) < 8)) {
    console.error(`Signed builds need NSIS 3.08 or newer (found: ${String(r.stdout || 'none').trim()}).`);
    process.exit(1);
  }
}

// The uninstaller (and an upgrade) removes exactly the build's own top-level entries, so a
// file the user keeps in the install folder is never deleted.
function appFilesMacro(dir) {
  const lines = ['!macro RemoveAppFiles'];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (/["$\r\n]/.test(entry.name)) throw new Error(`Unsupported file name in build: ${entry.name}`);
    lines.push(entry.isDirectory() ? `  RMDir /r "$INSTDIR\\${entry.name}"` : `  Delete "$INSTDIR\\${entry.name}"`);
  }
  lines.push('!macroend', '');
  return lines.join('\n');
}

const customOut = option('--out');
if (!customOut) cleanReleaseDir();
const outFile = path.resolve(customOut || path.join(RELEASE_DIR, `${artifactBase()}.exe`));
fs.rmSync(outFile, { force: true });

const nsi = path.join(__dirname, 'win', 'installer.nsi');
const icon = path.join(ROOT, 'icon', 'icon.ico');
const publisher = (pkg.author || '').replace(/<.*>/, '').trim() || 'BurntToasters';

const workDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bse-nsis-'));
const appFiles = path.join(workDir, 'app-files.nsh');
fs.writeFileSync(appFiles, appFilesMacro(sourceDir));
let signInclude = null;
if (sign) {
  assertNsisCanSign();
  signInclude = path.join(workDir, 'sign.nsh');
  fs.writeFileSync(signInclude, `!uninstfinalize '${nsisSignCommand()}' = 0\n`);
}

const args = [
  `-DAPPNAME=${option('--app-name') || productName}`,
  `-DVERSION=${version}`,
  `-DPUBLISHER=${publisher}`,
  `-DSOURCE_DIR=${sourceDir}`,
  `-DEXENAME=${exeName}`,
  `-DICON=${icon}`,
  `-DOUTFILE=${outFile}`,
  `-DAPP_FILES_INCLUDE=${appFiles}`,
  ...(signInclude ? [`-DSIGN_INCLUDE=${signInclude}`] : []),
  ...(e2eUserLevel ? ['-DE2E_USER_LEVEL'] : []),
  nsi,
];

console.log(`$ ${makensis} ${args.join(' ')}`);
const r = spawnSync(makensis, args, { stdio: 'inherit' });
fs.rmSync(workDir, { recursive: true, force: true });
if (r.error && r.error.code === 'ENOENT') {
  console.error('makensis not found. Install NSIS and ensure makensis is on PATH.');
  process.exit(1);
}
if (r.status !== 0) process.exit(r.status === null ? 1 : r.status);
if (sign) signFile(outFile);
console.log(`Created ${outFile}${sign ? ' (signed)' : ''}`);

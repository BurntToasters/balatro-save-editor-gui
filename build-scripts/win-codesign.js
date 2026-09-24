'use strict';

// Windows Authenticode signing via Azure Artifact Signing (build-scripts/win/*.ps1).
// Env (via `dotenv -e .env --`): AZURE_* / AZURE_ARTIFACT_SIGNING_* (see .env.example).
// Usage: node win-codesign.js app      sign the PyInstaller app exe (before NSIS packs it)
//        node win-codesign.js verify   verify the app exe + release/*.exe identity and timestamp

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { ROOT, RELEASE_DIR, appName } = require('./pkg');

const WIN_DIR = path.join(__dirname, 'win');
const SIGN_PS1 = path.join(WIN_DIR, 'artifact-sign.ps1');
const VERIFY_PS1 = path.join(WIN_DIR, 'verify-authenticode.ps1');

const appExePath = () => path.join(ROOT, 'dist', appName, `${appName}.exe`);

function powershellArgs(script, ...rest) {
  return ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script, ...rest];
}

function runPowershell(args) {
  const r = spawnSync('powershell.exe', args, { stdio: 'inherit' });
  if (r.error) throw r.error;
  if (r.status !== 0) process.exit(r.status === null ? 1 : r.status);
}

// NSIS runs this on the generated uninstaller; %1 is replaced with its path.
function nsisSignCommand() {
  return ['powershell.exe', ...powershellArgs(`"${SIGN_PS1}"`, '-FilePath', '"%1"')].join(' ');
}

function signFile(file) {
  runPowershell(powershellArgs(SIGN_PS1, '-FilePath', file));
}

function verifyFiles(files) {
  runPowershell(powershellArgs(VERIFY_PS1, ...files));
}

module.exports = { appExePath, nsisSignCommand, signFile, verifyFiles };

if (require.main === module) {
  if (process.platform !== 'win32') {
    console.error('Windows code signing runs on Windows only.');
    process.exit(1);
  }
  const mode = process.argv[2];
  const exe = appExePath();
  if (!fs.existsSync(exe)) {
    console.error(`Build not found: ${exe}\nRun: npm run build`);
    process.exit(1);
  }
  if (mode === 'app') {
    signFile(exe);
  } else if (mode === 'verify') {
    const installers = fs.existsSync(RELEASE_DIR)
      ? fs.readdirSync(RELEASE_DIR).filter((f) => f.toLowerCase().endsWith('.exe')).map((f) => path.join(RELEASE_DIR, f))
      : [];
    if (!installers.length) {
      console.error('No installer in release/. Run: npm run dist:win:signed');
      process.exit(1);
    }
    verifyFiles([exe, ...installers]);
  } else {
    console.error('Usage: node build-scripts/win-codesign.js app|verify');
    process.exit(1);
  }
}

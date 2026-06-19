'use strict';

const { spawnSync, execSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { ROOT, macAppName } = require('./pkg');

if (process.platform !== 'darwin') {
  console.error('macOS signing only.');
  process.exit(1);
}

const identity = process.env.APPLE_SIGNING_IDENTITY || process.env.CSC_NAME;
if (!identity) {
  console.error('Set APPLE_SIGNING_IDENTITY in .env (e.g. "Developer ID Application: Name (TEAMID)"). Use "-" for ad-hoc.');
  process.exit(1);
}

const appPath = path.join(ROOT, 'dist', `${macAppName}.app`);
if (!fs.existsSync(appPath)) {
  console.error(`App not found: ${appPath}\nRun: npm run build`);
  process.exit(1);
}

const entitlements = path.join(__dirname, 'mac', 'entitlements.plist');
const adhoc = identity === '-';

function run(cmd, args) {
  const r = spawnSync(cmd, args, { stdio: 'inherit' });
  if (r.status !== 0) process.exit(r.status === null ? 1 : r.status);
}

function sign(target) {
  const args = ['--force', '--options', 'runtime', '--entitlements', entitlements, '--sign', identity, target];
  // Secure timestamps require a real identity; skip for ad-hoc test signing.
  if (!adhoc) args.splice(1, 0, '--timestamp');
  run('codesign', args);
}

// Every Mach-O binary must be signed with hardened runtime + timestamp, not just
// *.dylib/*.so (e.g. the extension-less Python.framework binary). Detect them all.
function machOFiles() {
  const out = execSync(`find "${appPath}" -type f -print0 | xargs -0 file`, {
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
  });
  return out
    .split('\n')
    .filter((l) => l.includes('Mach-O'))
    .map((l) => l.replace(/: +Mach-O.*$/, ''))
    .filter(Boolean)
    // Deepest paths first so nested code is signed before its container.
    .sort((a, b) => b.split('/').length - a.split('/').length);
}

const nested = machOFiles();
console.log(`Signing ${nested.length} Mach-O binaries inside-out…`);
for (const f of nested) sign(f);

console.log('Signing app bundle…');
sign(appPath);

run('codesign', ['--verify', '--deep', '--strict', '--verbose=2', appPath]);
console.log('App signed and verified.');

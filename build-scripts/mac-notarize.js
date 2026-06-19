'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { RELEASE_DIR, artifactBase } = require('./pkg');

if (process.platform !== 'darwin') {
  console.error('macOS notarization only.');
  process.exit(1);
}

const target = process.argv[2] || path.join(RELEASE_DIR, `${artifactBase()}.dmg`);
if (!fs.existsSync(target)) {
  console.error(`Artifact not found: ${target}\nRun: npm run dist:mac`);
  process.exit(1);
}

function run(cmd, args) {
  console.log(`$ ${cmd} ${args.filter((a) => !isSecret(a)).join(' ')}`);
  const r = spawnSync(cmd, args, { stdio: 'inherit' });
  if (r.status !== 0) process.exit(r.status === null ? 1 : r.status);
}

const secrets = new Set();
function isSecret(a) {
  return secrets.has(a);
}

// Prefer a stored keychain profile; fall back to Apple ID + app-specific password.
let submitArgs;
const profile = process.env.APPLE_KEYCHAIN_PROFILE;
if (profile) {
  submitArgs = ['notarytool', 'submit', target, '--keychain-profile', profile, '--wait'];
} else {
  const appleId = process.env.APPLE_ID;
  const teamId = process.env.APPLE_TEAM_ID;
  const appPw = process.env.APPLE_APP_PASSWORD;
  if (!appleId || !teamId || !appPw) {
    console.error('Set APPLE_KEYCHAIN_PROFILE, or APPLE_ID + APPLE_TEAM_ID + APPLE_APP_PASSWORD in .env');
    process.exit(1);
  }
  secrets.add(appPw);
  submitArgs = [
    'notarytool', 'submit', target,
    '--apple-id', appleId,
    '--team-id', teamId,
    '--password', appPw,
    '--wait',
  ];
}

run('xcrun', submitArgs);
run('xcrun', ['stapler', 'staple', target]);
run('xcrun', ['stapler', 'validate', target]);
console.log(`Notarized + stapled: ${target}`);

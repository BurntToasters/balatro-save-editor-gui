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

// Credentials: keychain profile, or Apple ID + app-specific password.
let cred;
const profile = process.env.APPLE_KEYCHAIN_PROFILE;
if (profile) {
  cred = ['--keychain-profile', profile];
} else {
  const { APPLE_ID, APPLE_TEAM_ID, APPLE_APP_PASSWORD } = process.env;
  if (!APPLE_ID || !APPLE_TEAM_ID || !APPLE_APP_PASSWORD) {
    console.error('Set APPLE_KEYCHAIN_PROFILE, or APPLE_ID + APPLE_TEAM_ID + APPLE_APP_PASSWORD in .env');
    process.exit(1);
  }
  cred = ['--apple-id', APPLE_ID, '--team-id', APPLE_TEAM_ID, '--password', APPLE_APP_PASSWORD];
}

function xcrun(args, opts = {}) {
  return spawnSync('xcrun', args, { encoding: 'utf8', ...opts });
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    const m = text && text.match(/\{[\s\S]*\}/);
    if (m) {
      try {
        return JSON.parse(m[0]);
      } catch {
        /* fall through */
      }
    }
    return null;
  }
}

console.log(`Submitting ${path.basename(target)} to Apple notary service…`);
const submit = xcrun(['notarytool', 'submit', target, ...cred, '--output-format', 'json', '--wait']);
process.stdout.write(submit.stdout || '');
process.stderr.write(submit.stderr || '');

const result = parseJson(submit.stdout) || {};
const { id, status } = result;
console.log(`Notarization status: ${status || 'unknown'}${id ? ` (id ${id})` : ''}`);

if (status !== 'Accepted') {
  if (id) {
    console.error('\nNotarization failed. Fetching log:\n');
    const log = xcrun(['notarytool', 'log', id, ...cred], { stdio: 'inherit' });
    if (log.status !== 0) console.error('(could not fetch notarization log)');
  }
  process.exit(1);
}

const staple = xcrun(['stapler', 'staple', target], { stdio: 'inherit' });
if (staple.status !== 0) process.exit(staple.status === null ? 1 : staple.status);
const validate = xcrun(['stapler', 'validate', target], { stdio: 'inherit' });
if (validate.status !== 0) process.exit(validate.status === null ? 1 : validate.status);
console.log(`Notarized + stapled: ${target}`);

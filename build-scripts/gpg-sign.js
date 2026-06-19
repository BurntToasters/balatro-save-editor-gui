'use strict';

const { spawnSync } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { RELEASE_DIR } = require('./pkg');

const SIG_EXT = '.asc';
const CHECKSUMS = 'SHA256SUMS';

if (!fs.existsSync(RELEASE_DIR)) {
  console.error('No release/ directory. Build installers first (npm run dist).');
  process.exit(1);
}

function artifacts() {
  return fs
    .readdirSync(RELEASE_DIR)
    .filter((f) => !f.endsWith(SIG_EXT) && f !== CHECKSUMS)
    .filter((f) => fs.statSync(path.join(RELEASE_DIR, f)).isFile());
}

function gpgSign(file) {
  const out = `${file}${SIG_EXT}`;
  fs.rmSync(out, { force: true });
  const args = ['--batch', '--yes', '--armor', '--detach-sign'];
  if (process.env.GPG_KEY_ID) args.push('--local-user', process.env.GPG_KEY_ID);
  if (process.env.GPG_PASSPHRASE) {
    args.push('--pinentry-mode', 'loopback', '--passphrase', process.env.GPG_PASSPHRASE);
  }
  args.push('--output', out, file);
  const r = spawnSync('gpg', args, { stdio: ['ignore', 'inherit', 'inherit'] });
  if (r.error && r.error.code === 'ENOENT') {
    console.error('gpg not found. Install GnuPG.');
    process.exit(1);
  }
  if (r.status !== 0) process.exit(r.status === null ? 1 : r.status);
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

const files = artifacts();
if (!files.length) {
  console.error('No artifacts found in release/.');
  process.exit(1);
}

const lines = [];
for (const f of files) {
  const full = path.join(RELEASE_DIR, f);
  gpgSign(full);
  lines.push(`${sha256(full)}  ${f}`);
  console.log(`signed ${f}`);
}

const checksumsPath = path.join(RELEASE_DIR, CHECKSUMS);
fs.writeFileSync(checksumsPath, lines.join('\n') + '\n');
gpgSign(checksumsPath);
console.log(`Wrote ${CHECKSUMS} and detached signatures for ${files.length} artifact(s).`);

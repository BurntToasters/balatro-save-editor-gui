'use strict';

// Signs release artifacts with GPG (detached .asc) and writes a per-platform
// SHA256SUMS file. Upload is handled separately by publish.js.
// Env (via `dotenv -e .env --`): GPG_KEY_ID (optional), GPG_PASSPHRASE (optional).

const { execFileSync, spawnSync } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { RELEASE_DIR, osTag, arch } = require('./pkg');

const SIGNABLE_EXTENSIONS = ['.dmg', '.exe', '.appimage', '.deb', '.rpm', '.zip', '.msi'];
const ARCH_PATTERNS = {
  x64: ['-x64', '-x86_64', '-amd64', '_x64', '_amd64'],
  arm64: ['-arm64', '-aarch64', '_arm64', '_aarch64'],
};

const args = process.argv.slice(2);
const archIdx = args.indexOf('--arch');
const targetArch = archIdx !== -1 ? args[archIdx + 1] : null;

function fileArch(name) {
  const lower = name.toLowerCase();
  for (const [a, patterns] of Object.entries(ARCH_PATTERNS)) {
    if (patterns.some((p) => lower.includes(p))) return a;
  }
  return null;
}

function signableArtifacts() {
  if (!fs.existsSync(RELEASE_DIR)) {
    console.error(`No release/ directory. Build installers first (npm run dist).`);
    process.exit(1);
  }
  return fs.readdirSync(RELEASE_DIR).filter((f) => {
    const full = path.join(RELEASE_DIR, f);
    if (!fs.statSync(full).isFile()) return false;
    if (!SIGNABLE_EXTENSIONS.some((ext) => f.toLowerCase().endsWith(ext))) return false;
    if (targetArch) {
      const fa = fileArch(f);
      return fa === targetArch || fa === null;
    }
    return true;
  });
}

function gpgSign(file) {
  const out = `${file}.asc`;
  fs.rmSync(out, { force: true });
  const gpgArgs = ['--batch', '--yes', '--armor', '--detach-sign'];
  if (process.env.GPG_KEY_ID) gpgArgs.push('--local-user', process.env.GPG_KEY_ID);
  if (process.env.GPG_PASSPHRASE) {
    gpgArgs.push('--pinentry-mode', 'loopback', '--passphrase', process.env.GPG_PASSPHRASE);
  }
  gpgArgs.push('--output', out, file);
  execFileSync('gpg', gpgArgs, { stdio: 'pipe' });
  return out;
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function main() {
  if (spawnSync('gpg', ['--version'], { stdio: 'pipe' }).status !== 0) {
    console.error('gpg not found. Install GnuPG (brew install gnupg / gpg4win / apt install gnupg).');
    process.exit(1);
  }
  if (!process.env.GPG_KEY_ID) {
    console.warn('GPG_KEY_ID not set - using default secret key.');
  }

  const files = signableArtifacts();
  if (!files.length) {
    console.error('No signable artifacts found in release/.');
    process.exit(1);
  }

  const platform = `${osTag()}-${arch()}`;
  const checksums = [];
  const signed = [];

  for (const f of files) {
    const full = path.join(RELEASE_DIR, f);
    gpgSign(full);
    checksums.push(`${sha256(full)}  ${f}`);
    signed.push(f);
    console.log(`signed ${f}`);
  }

  const checksumFile = path.join(RELEASE_DIR, `SHA256SUMS-${platform}.txt`);
  fs.writeFileSync(checksumFile, checksums.join('\n') + '\n');
  gpgSign(checksumFile);

  console.log(`Signed ${signed.length} artifact(s) + SHA256SUMS-${platform}.txt`);
}

main();

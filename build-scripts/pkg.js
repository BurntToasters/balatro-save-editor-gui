'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { ROOT } = require('./venv-python');

const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));

function arch() {
  if (process.env.BALATRO_ARCH) return process.env.BALATRO_ARCH;
  return process.arch === 'arm64' ? 'arm64' : 'x64';
}

function osTag() {
  if (process.platform === 'darwin') return 'mac';
  if (process.platform === 'win32') return 'win';
  return 'linux';
}

// e.g. Balatro-Save-Editor-0.1.0-mac-arm64
function artifactBase() {
  const name = pkg.productName.replace(/\s+/g, '-');
  return `${name}-${pkg.version}-${osTag()}-${arch()}`;
}

const RELEASE_DIR = path.join(ROOT, 'release');

module.exports = {
  ROOT,
  RELEASE_DIR,
  pkg,
  version: pkg.version,
  productName: pkg.productName,
  appId: pkg.appId,
  appName: 'balatro-save-editor',
  macAppName: 'Balatro Save Editor',
  arch,
  osTag,
  artifactBase,
  ensureReleaseDir() {
    fs.mkdirSync(RELEASE_DIR, { recursive: true });
    return RELEASE_DIR;
  },
  // Wipe release/ before building a new installer
  cleanReleaseDir() {
    if (fs.existsSync(RELEASE_DIR)) {
      for (const f of fs.readdirSync(RELEASE_DIR)) {
        fs.rmSync(path.join(RELEASE_DIR, f), { recursive: true, force: true });
      }
    }
    fs.mkdirSync(RELEASE_DIR, { recursive: true });
    return RELEASE_DIR;
  },
};

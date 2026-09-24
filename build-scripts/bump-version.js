'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { ROOT } = require('./venv-python');
const { syncVersion } = require('./sync-version');

const SEMVER = /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$/;

const arg = process.argv[2];
if (!arg) {
  console.error('Usage: node build-scripts/bump-version.js <patch|minor|major|X.Y.Z[-pre]>');
  process.exit(1);
}

function bump(v, kind) {
  if (SEMVER.test(kind)) return kind;
  const m = String(v).match(SEMVER);
  if (!m) {
    console.error(`Current version isn't semver: ${v}`);
    process.exit(1);
  }
  const [maj, min, pat] = m.slice(1, 4).map(Number);
  const pre = !!m[4];
  // From a pre-release, the next version is the release it was a pre-release of.
  if (kind === 'major') return pre && min === 0 && pat === 0 ? `${maj}.0.0` : `${maj + 1}.0.0`;
  if (kind === 'minor') return pre && pat === 0 ? `${maj}.${min}.0` : `${maj}.${min + 1}.0`;
  if (kind === 'patch') return pre ? `${maj}.${min}.${pat}` : `${maj}.${min}.${pat + 1}`;
  console.error(`Unknown bump type: ${kind}`);
  process.exit(1);
}

function writeJson(file, data) {
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n');
}

const pkgPath = path.join(ROOT, 'package.json');
const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
const next = bump(pkg.version, arg);
const prev = pkg.version;
pkg.version = next;
writeJson(pkgPath, pkg);

// Keep the lockfile's own version in step, as `npm version` would.
const lockPath = path.join(ROOT, 'package-lock.json');
if (fs.existsSync(lockPath)) {
  const lock = JSON.parse(fs.readFileSync(lockPath, 'utf8'));
  lock.version = next;
  if (lock.packages && lock.packages['']) lock.packages[''].version = next;
  writeJson(lockPath, lock);
}

console.log(`Version: ${prev} -> ${next}`);
syncVersion();

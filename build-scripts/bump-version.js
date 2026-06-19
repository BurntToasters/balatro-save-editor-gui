'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { ROOT } = require('./venv-python');

const arg = process.argv[2];
if (!arg) {
  console.error('Usage: node build-scripts/bump-version.js <patch|minor|major|X.Y.Z>');
  process.exit(1);
}

function bump(v, kind) {
  if (/^\d+\.\d+\.\d+$/.test(kind)) return kind;
  const [maj, min, pat] = v.split('.').map(Number);
  if (kind === 'major') return `${maj + 1}.0.0`;
  if (kind === 'minor') return `${maj}.${min + 1}.0`;
  if (kind === 'patch') return `${maj}.${min}.${pat + 1}`;
  console.error(`Unknown bump type: ${kind}`);
  process.exit(1);
}

const pkgPath = path.join(ROOT, 'package.json');
const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
const next = bump(pkg.version, arg);
const prev = pkg.version;
pkg.version = next;
fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n');

const initPath = path.join(ROOT, 'app', '__init__.py');
const init = fs.readFileSync(initPath, 'utf8').replace(
  /__version__\s*=\s*["'][^"']+["']/,
  `__version__ = "${next}"`,
);
fs.writeFileSync(initPath, init);

console.log(`Version: ${prev} -> ${next} (package.json + app/__init__.py)`);

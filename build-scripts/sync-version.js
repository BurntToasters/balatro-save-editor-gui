'use strict';

// Syncs the version from package.json into other source files (no bumping).
const fs = require('node:fs');
const path = require('node:path');
const { ROOT } = require('./venv-python');

const version = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8')).version;
const changed = [];

function patch(relPath, regex, replacement) {
  const file = path.join(ROOT, relPath);
  let text;
  try {
    text = fs.readFileSync(file, 'utf8');
  } catch {
    return;
  }
  const next = text.replace(regex, replacement);
  if (next !== text) {
    fs.writeFileSync(file, next);
    changed.push(relPath);
  }
}

patch('app/__init__.py', /__version__\s*=\s*["'][^"']+["']/, `__version__ = "${version}"`);

console.log(`Synced version ${version} -> ${changed.length ? changed.join(', ') : '(already in sync)'}`);

'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const VENV = path.join(ROOT, '.venv');

function venvPython() {
  return process.platform === 'win32'
    ? path.join(VENV, 'Scripts', 'python.exe')
    : path.join(VENV, 'bin', 'python');
}

function ensureVenvPython() {
  const py = venvPython();
  if (!fs.existsSync(py)) {
    console.error(`venv python not found at ${py}\nRun: npm run venv`);
    process.exit(1);
  }
  return py;
}

module.exports = { ROOT, VENV, venvPython, ensureVenvPython };

if (require.main === module) {
  const py = ensureVenvPython();
  const r = spawnSync(py, process.argv.slice(2), { stdio: 'inherit', cwd: ROOT });
  process.exit(r.status === null ? 1 : r.status);
}

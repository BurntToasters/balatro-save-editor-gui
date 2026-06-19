'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { ROOT, VENV, venvPython } = require('./venv-python');

function run(cmd, args) {
  console.log(`$ ${cmd} ${args.join(' ')}`);
  const r = spawnSync(cmd, args, { stdio: 'inherit', cwd: ROOT });
  if (r.status !== 0) process.exit(r.status === null ? 1 : r.status);
}

function pickBasePython() {
  const candidates =
    process.platform === 'win32'
      ? ['py', 'python', 'python3']
      : ['python3.14', 'python3', 'python'];
  for (const c of candidates) {
    const r = spawnSync(c, ['--version'], { encoding: 'utf8' });
    if (r.status === 0) return c;
  }
  console.error('No Python interpreter found (need 3.14+).');
  process.exit(1);
}

const py = venvPython();
if (!fs.existsSync(py)) {
  run(pickBasePython(), ['-m', 'venv', VENV]);
}
run(py, ['-m', 'pip', 'install', '--upgrade', 'pip']);
run(py, ['-m', 'pip', 'install', '-r', path.join(ROOT, 'requirements-dev.txt')]);
console.log('venv ready.');

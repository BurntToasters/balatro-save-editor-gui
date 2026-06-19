'use strict';

const { spawnSync } = require('node:child_process');
const { ensureVenvPython, ROOT } = require('./venv-python');

const py = ensureVenvPython();
const args = ['-m', 'PyInstaller', 'balatro-save-editor.spec', '--noconfirm', '--clean'];
console.log(`$ ${py} ${args.join(' ')}`);
const r = spawnSync(py, args, { stdio: 'inherit', cwd: ROOT });
process.exit(r.status === null ? 1 : r.status);

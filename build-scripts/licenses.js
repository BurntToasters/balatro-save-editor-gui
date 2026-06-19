'use strict';

const { spawnSync } = require('node:child_process');
const path = require('node:path');
const { ensureVenvPython, ROOT } = require('./venv-python');

const py = ensureVenvPython();
const r = spawnSync(py, [path.join(__dirname, 'collect_licenses.py')], {
  stdio: 'inherit',
  cwd: ROOT,
});
process.exit(r.status === null ? 1 : r.status);

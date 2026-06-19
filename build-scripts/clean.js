'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { ROOT } = require('./venv-python');

for (const dir of ['build', 'dist', 'release']) {
  fs.rmSync(path.join(ROOT, dir), { recursive: true, force: true });
  console.log(`removed ${dir}/`);
}

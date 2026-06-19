'use strict';

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { ROOT } = require('./venv-python');

function artifactPath() {
  const dist = path.join(ROOT, 'dist');
  if (process.platform === 'darwin') {
    return path.join(dist, 'Balatro Save Editor.app', 'Contents', 'MacOS', 'balatro-save-editor');
  }
  if (process.platform === 'win32') {
    return path.join(dist, 'balatro-save-editor', 'balatro-save-editor.exe');
  }
  return path.join(dist, 'balatro-save-editor', 'balatro-save-editor');
}

const bin = artifactPath();
if (!fs.existsSync(bin)) {
  console.error(`Built artifact not found: ${bin}\nRun: npm run build`);
  process.exit(1);
}

console.log(`Launching ${bin}`);
const child = spawn(bin, [], { stdio: ['ignore', 'pipe', 'pipe'] });
let out = '';
let killed = false;
child.stdout.on('data', (d) => (out += d));
child.stderr.on('data', (d) => (out += d));

child.on('error', (err) => {
  console.error(`Failed to launch: ${err.message}`);
  process.exit(1);
});

child.on('exit', (code, signal) => {
  if (killed) return;
  console.error(`App exited early (code=${code}, signal=${signal}).`);
  if (out.trim()) console.error(out.trim());
  process.exit(1);
});

setTimeout(() => {
  killed = true;
  child.kill('SIGTERM');
  console.log('App started and stayed alive for 5s. Runtime smoke OK.');
  process.exit(0);
}, 5000);

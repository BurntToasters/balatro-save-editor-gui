'use strict';

const { spawnSync } = require('node:child_process');
const os = require('node:os');
const { ROOT } = require('./pkg');

const IMAGE = 'quay.io/pypa/manylinux_2_28_x86_64:2026.05.07-2';
const BUILD_IMAGE = 'balatro-save-editor-linux-build:manylinux_2_28-py312';

const dockerDesktopE2e = process.env.BSE_LINUX_E2E_DOCKER_DESKTOP === '1';
if (process.platform !== 'linux' && !dockerDesktopE2e) {
  console.error('Linux compatibility builds run on Linux only.');
  process.exit(1);
}
if (os.arch() !== 'x64') {
  console.error(`Linux compatibility image supports x64 only (host is ${os.arch()}).`);
  process.exit(1);
}

const uid = process.getuid ? process.getuid() : 1000;
const gid = process.getgid ? process.getgid() : 1000;
console.log(`Preparing Linux x64 build image from ${IMAGE}`);
const image = spawnSync(
  'docker',
  ['build', '--file', 'build-scripts/linux.Dockerfile', '--tag', BUILD_IMAGE, '.'],
  { cwd: ROOT, stdio: 'inherit' },
);
if (image.error) {
  console.error(`docker failed to start: ${image.error.message}`);
  process.exit(1);
}
if (image.status !== 0) process.exit(image.status === null ? 1 : image.status);

const command = [
  'python build-scripts/collect_licenses.py pywebview PySide6',
  'python -m PyInstaller balatro-save-editor.spec --noconfirm --clean',
  'python build-scripts/verify-linux-compat.py dist/balatro-save-editor',
].join(' && ');
const args = [
  'run',
  '--rm',
  '--user',
  `${uid}:${gid}`,
  '--env',
  'HOME=/tmp',
  '--volume',
  `${ROOT}:/project`,
  '--workdir',
  '/project',
  BUILD_IMAGE,
  '/bin/bash',
  '-lc',
  command,
];

console.log(`Building Linux x64 bundle with ${BUILD_IMAGE}`);
const result = spawnSync('docker', args, { cwd: ROOT, stdio: 'inherit' });
if (result.error) {
  console.error(`docker failed to start: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status === null ? 1 : result.status);

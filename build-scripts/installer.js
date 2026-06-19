'use strict';

// Dispatches to the installer script for the current platform.
const map = {
  darwin: './installer-dmg.js',
  win32: './installer-nsis.js',
  linux: './installer-appimage.js',
};

const mod = map[process.platform];
if (!mod) {
  console.error(`Unsupported platform: ${process.platform}`);
  process.exit(1);
}
require(mod);

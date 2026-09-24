'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'docs', 'img', 'social.png');

const CANDIDATES = {
  win32: [
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  ],
  darwin: [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ],
  linux: ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge'],
};

function findBrowser() {
  if (process.env.BROWSER_BIN) return process.env.BROWSER_BIN;
  const hit = (CANDIDATES[process.platform] || []).find((p) => fs.existsSync(p));
  if (!hit) {
    console.error('No Chromium-based browser found. Set BROWSER_BIN=/path/to/chrome.');
    process.exit(1);
  }
  return hit;
}

const cnamePath = path.join(ROOT, 'docs', 'CNAME');
const domain = fs.existsSync(cnamePath) ? fs.readFileSync(cnamePath, 'utf8').trim() : '';
const url = pathToFileURL(path.join(__dirname, 'social-card.html'));
if (domain) url.searchParams.set('domain', domain);

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'bse-card-'));
try {
  const r = spawnSync(
    findBrowser(),
    [
      '--headless=new',
      '--disable-gpu',
      '--hide-scrollbars',
      '--force-device-scale-factor=1',
      `--user-data-dir=${profile}`,
      '--virtual-time-budget=5000',
      '--window-size=1280,640',
      `--screenshot=${OUT}`,
      url.href,
    ],
    { stdio: 'ignore' },
  );
  if (r.status !== 0 || !fs.existsSync(OUT)) {
    console.error('Browser failed to render the social card.');
    process.exit(1);
  }
  console.log(`Wrote ${path.relative(ROOT, OUT)}`);
} finally {
  fs.rmSync(profile, { recursive: true, force: true });
}

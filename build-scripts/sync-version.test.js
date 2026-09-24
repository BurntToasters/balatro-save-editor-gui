'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { rewriteDownloadLinks } = require('./sync-version');

const BASE = 'https://github.com/o/r/releases/download';
const opts = { slug: 'Balatro-Save-Editor', version: '1.0.0' };

test('header download links move to the current version', () => {
  const md = [
    `- [x64](${BASE}/v0.2.4/Balatro-Save-Editor-0.2.4-win-x64.exe)`,
    `- [arm64](${BASE}/v0.2.4/Balatro-Save-Editor-0.2.4-mac-arm64.dmg)`,
    `- [x64](${BASE}/v0.2.4/Balatro-Save-Editor-0.2.4-linux-x64.AppImage)`,
    '',
    '## 1.0.0',
  ].join('\n');
  const out = rewriteDownloadLinks(md, opts);
  assert.ok(out.includes(`${BASE}/v1.0.0/Balatro-Save-Editor-1.0.0-win-x64.exe`));
  assert.ok(out.includes(`${BASE}/v1.0.0/Balatro-Save-Editor-1.0.0-mac-arm64.dmg`));
  assert.ok(out.includes(`${BASE}/v1.0.0/Balatro-Save-Editor-1.0.0-linux-x64.AppImage`));
  assert.ok(!out.includes('0.2.4'));
});

test('a "## Downloads" section is rewritten, installers and .asc signatures alike', () => {
  const exe = (v) => `${BASE}/v${v}/Balatro-Save-Editor-${v}-win-x64.exe`;
  const md = [
    '## ⬇️ Downloads',
    '',
    `- **Windows:** [x64](${exe('0.2.4')}) ([sig](${exe('0.2.4')}.asc))`,
    '',
    '*GPG Pubkey: https://tuxedo.rosie.run/GPG/key.asc*',
    '',
    '## 1.0.0',
    '',
    '## 0.2.4',
    `- [x64](${exe('0.2.4')}) ([sig](${exe('0.2.4')}.asc))`,
  ].join('\n');
  const out = rewriteDownloadLinks(md, opts);
  const [downloads, rest] = out.split('## 1.0.0');
  assert.ok(downloads.includes(`[x64](${exe('1.0.0')})`));
  assert.ok(downloads.includes(`[sig](${exe('1.0.0')}.asc)`));
  assert.ok(!downloads.includes('0.2.4'));
  assert.ok(downloads.includes('https://tuxedo.rosie.run/GPG/key.asc'));
  assert.ok(rest.includes(`[x64](${exe('0.2.4')})`) && rest.includes(`[sig](${exe('0.2.4')}.asc)`));
});

test('links inside older release sections are left alone', () => {
  const old = `${BASE}/v0.2.4/Balatro-Save-Editor-0.2.4-win-x64.exe`;
  const md = `- [x64](${old})\n\n## 1.0.0\n\n## 0.2.4\n- [x64](${old})\n`;
  const out = rewriteDownloadLinks(md, opts);
  assert.equal(out.split(old).length - 1, 1);
});

test('pre-release versions round-trip', () => {
  const md = `[x](${BASE}/v1.1.0-beta.1/Balatro-Save-Editor-1.1.0-beta.1-win-x64.exe)`;
  assert.equal(
    rewriteDownloadLinks(md, { ...opts, version: '1.1.0-beta.2' }),
    `[x](${BASE}/v1.1.0-beta.2/Balatro-Save-Editor-1.1.0-beta.2-win-x64.exe)`,
  );
  const back = rewriteDownloadLinks(md, opts);
  assert.equal(back, `[x](${BASE}/v1.0.0/Balatro-Save-Editor-1.0.0-win-x64.exe)`);
});

test('unrelated links and other products are untouched', () => {
  const md = `[key](https://tuxedo.rosie.run/GPG/key.asc) [other](${BASE}/v0.2.4/Other-App-0.2.4-win-x64.exe)`;
  assert.equal(rewriteDownloadLinks(md, opts), md);
});

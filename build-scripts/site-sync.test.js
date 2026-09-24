'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { siteUrlFrom, canonicalOf, rebase, setLastmod, problems } = require('./site-sync');

const REPO = 'git+https://github.com/BurntToasters/balatro-save-editor-gui.git';

test('site URL comes from CNAME, else the github.io project URL', () => {
  assert.equal(siteUrlFrom({ cname: 'bse.example.com\n', repoUrl: REPO }), 'https://bse.example.com/');
  assert.equal(siteUrlFrom({ cname: 'https://bse.example.com/', repoUrl: REPO }), 'https://bse.example.com/');
  assert.equal(siteUrlFrom({ cname: '', repoUrl: REPO }), 'https://burnttoasters.github.io/balatro-save-editor-gui/');
  assert.throws(() => siteUrlFrom({ cname: '', repoUrl: 'nope' }), /cannot parse/);
});

test('rebase swaps every absolute site URL and nothing else', () => {
  const from = 'https://o.github.io/r/';
  const html =
    `<link rel="canonical" href="${from}" />` +
    `<meta property="og:image" content="${from}img/social.png" />` +
    '<a href="https://github.com/o/r">repo</a>';
  const out = rebase(html, from, 'https://x.dev/');
  assert.equal(canonicalOf(out), 'https://x.dev/');
  assert.ok(out.includes('content="https://x.dev/img/social.png"'));
  assert.ok(out.includes('href="https://github.com/o/r"'));
  assert.equal(rebase(html, from, from), html);
});

test('sitemap lastmod is replaced', () => {
  assert.equal(setLastmod('<lastmod>2020-01-01</lastmod>', '2026-09-24'), '<lastmod>2026-09-24</lastmod>');
});

test('docs/ URLs match docs/CNAME (run npm run site:sync if this fails)', () => {
  const { list } = problems();
  assert.deepEqual(list, []);
});

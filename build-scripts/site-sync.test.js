'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { siteUrlFrom, canonicalOf, rebase, pageUrl, isIndexable, buildSitemap, sitemapLocs, problems } = require('./site-sync');

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

test('page URLs map index.html files to directory URLs', () => {
  const base = 'https://x.dev/';
  assert.equal(pageUrl(base, 'docs/index.html'), 'https://x.dev/');
  assert.equal(pageUrl(base, 'docs/save-location/index.html'), 'https://x.dev/save-location/');
  assert.equal(pageUrl(base, 'docs/about.html'), 'https://x.dev/about.html');
});

test('404 and noindex pages stay out of the sitemap', () => {
  assert.equal(isIndexable('docs/index.html', '<html></html>'), true);
  assert.equal(isIndexable('docs/404.html', '<html></html>'), false);
  assert.equal(isIndexable('docs/draft/index.html', '<meta name="robots" content="noindex" />'), false);
});

test('sitemap lists each page with its own lastmod', () => {
  const xml = buildSitemap([
    { loc: 'https://x.dev/', lastmod: '2026-09-24' },
    { loc: 'https://x.dev/save-location/', lastmod: '2026-09-20' },
  ]);
  assert.deepEqual(sitemapLocs(xml), ['https://x.dev/', 'https://x.dev/save-location/']);
  assert.ok(xml.includes('<lastmod>2026-09-20</lastmod>'));
  assert.ok(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>'));
});

test('docs/ URLs match docs/CNAME (run npm run site:sync if this fails)', () => {
  const { list } = problems();
  assert.deepEqual(list, []);
});

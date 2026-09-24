'use strict';

// Syncs the version from package.json into other source files (no bumping).
const fs = require('node:fs');
const path = require('node:path');
const { ROOT } = require('./venv-python');

const VERSION = String.raw`\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?`;

// The "## ... Downloads" section up to the next "## " heading; without one, the text
// above the first heading. Links inside older release notes stay pinned.
function downloadsRange(text) {
  const heading = /^## .*\bDownloads\b.*$/im.exec(text);
  const start = heading ? heading.index + heading[0].length : 0;
  const next = text.slice(start).search(/^## /m);
  return [start, next === -1 ? text.length : start + next];
}

// Points installer and signature (.asc) download links at v<version>.
function rewriteDownloadLinks(text, { slug, version }) {
  const [start, end] = downloadsRange(text);
  const link = new RegExp(`(/releases/download/)v${VERSION}(/${slug}-)${VERSION}(?=-(?:win|mac|linux)-)`, 'g');
  return text.slice(0, start) + text.slice(start, end).replace(link, `$1v${version}$2${version}`) + text.slice(end);
}

function syncVersion() {
  const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
  const version = pkg.version;
  const slug = pkg.productName.replace(/\s+/g, '-');
  const changed = [];

  function patch(relPath, transform) {
    const file = path.join(ROOT, relPath);
    let text;
    try {
      text = fs.readFileSync(file, 'utf8');
    } catch {
      return;
    }
    const next = transform(text);
    if (next !== text) {
      fs.writeFileSync(file, next);
      changed.push(relPath);
    }
  }

  patch('app/__init__.py', (t) => t.replace(/__version__\s*=\s*["'][^"']+["']/, `__version__ = "${version}"`));
  patch('CHANGELOG.md', (t) => rewriteDownloadLinks(t, { slug, version }));

  console.log(`Synced version ${version} -> ${changed.length ? changed.join(', ') : '(already in sync)'}`);
}

module.exports = { rewriteDownloadLinks, syncVersion };

if (require.main === module) syncVersion();

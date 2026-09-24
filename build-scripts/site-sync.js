'use strict';
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const DOCS = path.join(ROOT, 'docs');
const REWRITE = ['docs/index.html', 'docs/404.html', 'docs/sitemap.xml', 'docs/robots.txt', 'README.md'];

function siteUrlFrom({ cname, repoUrl }) {
  const domain = String(cname || '').trim().split(/\s+/)[0];
  if (domain) return `https://${domain.replace(/^https?:\/\//, '').replace(/\/+$/, '')}/`;
  const m = String(repoUrl || '').match(/github\.com[/:]([^/]+)\/([^/.]+)/);
  if (!m) throw new Error('No docs/CNAME and cannot parse GitHub repo from package.json repository.url');
  return `https://${m[1].toLowerCase()}.github.io/${m[2]}/`;
}

function canonicalOf(html) {
  const m = html.match(/<link\s+rel="canonical"\s+href="([^"]+)"/);
  return m ? m[1] : null;
}

const rebase = (text, from, to) => (from && from !== to ? text.split(from).join(to) : text);

function setLastmod(xml, date) {
  return xml.replace(/<lastmod>[^<]*<\/lastmod>/g, `<lastmod>${date}</lastmod>`);
}

// Last time the page content changed: today if index.html is dirty, else its last commit date.
function contentDate() {
  const rel = 'docs/index.html';
  try {
    const dirty = execFileSync('git', ['status', '--porcelain', '--', rel], { cwd: ROOT, encoding: 'utf8' }).trim();
    if (!dirty) {
      const d = execFileSync('git', ['log', '-1', '--format=%cs', '--', rel], { cwd: ROOT, encoding: 'utf8' }).trim();
      if (d) return d;
    }
  } catch {
    /* not a git checkout */
  }
  return new Date().toISOString().slice(0, 10);
}

const read = (p) => fs.readFileSync(p, 'utf8');

function readState() {
  const pkgPath = path.join(ROOT, 'package.json');
  const pkg = JSON.parse(read(pkgPath));
  const cnamePath = path.join(DOCS, 'CNAME');
  const cname = fs.existsSync(cnamePath) ? read(cnamePath) : '';
  const base = siteUrlFrom({ cname, repoUrl: pkg.repository && pkg.repository.url });
  const current = canonicalOf(read(path.join(DOCS, 'index.html')));
  if (!current) throw new Error('docs/index.html has no <link rel="canonical">');
  return { base, current, pkg, pkgPath };
}

function problems() {
  const { base, current, pkg } = readState();
  const out = [];
  if (current !== base) out.push(`canonical is ${current}, expected ${base}`);
  for (const rel of REWRITE) {
    const file = path.join(ROOT, rel);
    if (fs.existsSync(file) && current !== base && read(file).includes(current)) out.push(`${rel} still uses ${current}`);
  }
  if (!read(path.join(DOCS, 'robots.txt')).includes(`Sitemap: ${base}sitemap.xml`)) out.push('robots.txt Sitemap line is stale');
  if (!read(path.join(DOCS, 'sitemap.xml')).includes(`<loc>${base}</loc>`)) out.push('sitemap.xml <loc> is stale');
  if (pkg.homepage !== base) out.push(`package.json homepage is ${pkg.homepage}, expected ${base}`);
  return { base, list: out };
}

function sync() {
  const { base, current, pkg, pkgPath } = readState();
  const changed = [];
  for (const rel of REWRITE) {
    const file = path.join(ROOT, rel);
    if (!fs.existsSync(file)) continue;
    const text = read(file);
    let next = rebase(text, current, base);
    if (rel === 'docs/sitemap.xml') next = setLastmod(next, contentDate());
    if (next !== text) {
      fs.writeFileSync(file, next);
      changed.push(rel);
    }
  }
  if (pkg.homepage !== base) {
    const text = read(pkgPath);
    fs.writeFileSync(pkgPath, text.replace(/("homepage":\s*)"[^"]*"/, `$1"${base}"`));
    changed.push('package.json');
  }
  console.log(`Site URL ${base} -> ${changed.length ? changed.join(', ') : '(already in sync)'}`);
  if (current !== base) console.log(`Also update the repo homepage: gh repo edit --homepage ${base}`);
}

module.exports = { siteUrlFrom, canonicalOf, rebase, setLastmod, problems };

if (require.main === module) {
  if (process.argv.includes('--check')) {
    const { base, list } = problems();
    if (list.length) {
      console.error(`docs/ is out of sync with ${base}:\n  - ${list.join('\n  - ')}\nRun: npm run site:sync`);
      process.exit(1);
    }
    console.log(`docs/ in sync with ${base}`);
  } else {
    sync();
  }
}

'use strict';
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const DOCS = path.join(ROOT, 'docs');
const OTHER_REWRITE = ['docs/robots.txt', 'README.md'];

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

// docs/index.html -> base, docs/save-location/index.html -> base + "save-location/".
function pageUrl(base, rel) {
  const inDocs = rel.replace(/\\/g, '/').replace(/^docs\//, '');
  return base + inDocs.replace(/(^|\/)index\.html$/, '$1');
}

function isIndexable(rel, html) {
  if (/(^|\/)404\.html$/.test(rel.replace(/\\/g, '/'))) return false;
  return !/<meta\s+name="robots"\s+content="[^"]*noindex/i.test(html);
}

function buildSitemap(entries) {
  const urls = entries.map((e) => `  <url>\n    <loc>${e.loc}</loc>\n    <lastmod>${e.lastmod}</lastmod>\n  </url>\n`).join('');
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}</urlset>\n`;
}

const sitemapLocs = (xml) => [...xml.matchAll(/<loc>([^<]*)<\/loc>/g)].map((m) => m[1]);

function htmlPages(dir = DOCS) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...htmlPages(full));
    else if (entry.name.endsWith('.html')) out.push(path.relative(ROOT, full).replace(/\\/g, '/'));
  }
  return out.sort();
}

// When a page's content last changed: today if it has uncommitted edits, else its last commit date.
function contentDate(rel) {
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
  const pages = htmlPages().map((rel) => {
    const html = read(path.join(ROOT, rel));
    return { rel, html, indexable: isIndexable(rel, html) };
  });
  return { base, current, pkg, pkgPath, pages };
}

function problems() {
  const { base, current, pkg, pages } = readState();
  const out = [];
  for (const page of pages) {
    if (!page.indexable) continue;
    const want = pageUrl(base, page.rel);
    const got = canonicalOf(page.html);
    if (got !== want) out.push(`${page.rel} canonical is ${got || '(missing)'}, expected ${want}`);
  }
  const rewrite = [...pages.map((p) => p.rel), 'docs/sitemap.xml', ...OTHER_REWRITE];
  for (const rel of rewrite) {
    const file = path.join(ROOT, rel);
    if (fs.existsSync(file) && current !== base && read(file).includes(current)) out.push(`${rel} still uses ${current}`);
  }
  if (!read(path.join(DOCS, 'robots.txt')).includes(`Sitemap: ${base}sitemap.xml`)) out.push('robots.txt Sitemap line is stale');
  const want = pages.filter((p) => p.indexable).map((p) => pageUrl(base, p.rel)).sort();
  const have = sitemapLocs(read(path.join(DOCS, 'sitemap.xml'))).sort();
  if (JSON.stringify(have) !== JSON.stringify(want)) out.push(`sitemap.xml lists ${have.join(', ') || 'nothing'}, expected ${want.join(', ')}`);
  if (pkg.homepage !== base) out.push(`package.json homepage is ${pkg.homepage}, expected ${base}`);
  return { base, list: out };
}

function sync() {
  const { base, current, pkg, pkgPath, pages } = readState();
  const changed = [];
  const write = (rel, text) => {
    const file = path.join(ROOT, rel);
    if (fs.existsSync(file) && read(file) === text) return;
    fs.writeFileSync(file, text);
    changed.push(rel);
  };
  for (const page of pages) write(page.rel, rebase(page.html, current, base));
  for (const rel of OTHER_REWRITE) {
    const file = path.join(ROOT, rel);
    if (fs.existsSync(file)) write(rel, rebase(read(file), current, base));
  }
  const entries = pages.filter((p) => p.indexable).map((p) => ({ loc: pageUrl(base, p.rel), lastmod: contentDate(p.rel) }));
  write('docs/sitemap.xml', buildSitemap(entries));
  if (pkg.homepage !== base) {
    write('package.json', read(pkgPath).replace(/("homepage":\s*)"[^"]*"/, `$1"${base}"`));
  }
  console.log(`Site URL ${base} (${entries.length} page(s) in sitemap) -> ${changed.length ? changed.join(', ') : '(already in sync)'}`);
  if (current !== base) console.log(`Also update the repo homepage: gh repo edit --homepage ${base}`);
}

module.exports = { siteUrlFrom, canonicalOf, rebase, pageUrl, isIndexable, buildSitemap, sitemapLocs, problems };

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

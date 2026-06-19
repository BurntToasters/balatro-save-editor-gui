'use strict';

// Creates (or reuses) a draft GitHub release for v<version> and uploads every
// file in release/ (installers + .asc signatures + SHA256SUMS-*.txt).
// Env (via `dotenv -e .env --`): GH_TOKEN.

const fs = require('node:fs');
const https = require('node:https');
const path = require('node:path');
const { RELEASE_DIR, pkg, version } = require('./pkg');

const dryRun = process.argv.includes('--dry-run');
const token = process.env.GH_TOKEN || process.env.GITHUB_TOKEN;
const tag = `v${version}`;

const TIMEOUT_MS = Number.parseInt(process.env.GH_REQUEST_TIMEOUT_MS || '30000', 10);
const RETRIES = Number.parseInt(process.env.GH_REQUEST_RETRIES || '3', 10);
const RETRY_DELAY_MS = Number.parseInt(process.env.GH_REQUEST_RETRY_DELAY_MS || '1500', 10);

function repoSlug() {
  const url = (pkg.repository && pkg.repository.url) || '';
  const m = url.match(/github\.com[/:]([^/]+)\/([^/.]+)/);
  if (!m) {
    console.error('Cannot parse GitHub repo from package.json repository.url');
    process.exit(1);
  }
  return { owner: m[1], repo: m[2] };
}

const { owner, repo } = repoSlug();

function listAssets() {
  if (!fs.existsSync(RELEASE_DIR)) return [];
  return fs.readdirSync(RELEASE_DIR).filter((f) => fs.statSync(path.join(RELEASE_DIR, f)).isFile());
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function isRetryable(err) {
  if (!err) return false;
  const codes = new Set([408, 409, 425, 429, 500, 502, 503, 504]);
  const errnos = new Set(['ETIMEDOUT', 'ECONNRESET', 'ENOTFOUND', 'EAI_AGAIN', 'ECONNREFUSED', 'EPIPE']);
  if (typeof err.statusCode === 'number' && codes.has(err.statusCode)) return true;
  if (typeof err.code === 'string' && errnos.has(err.code)) return true;
  const m = String(err.message || '').toLowerCase();
  return m.includes('timeout') || m.includes('socket hang up') || m.includes('aborted');
}

function authHeaders(extra = {}) {
  return {
    Authorization: `Bearer ${token}`,
    'User-Agent': 'balatro-save-editor-release',
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    ...extra,
  };
}

function rawRequest(options, body) {
  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', (c) => (data += c));
      res.on('end', () => {
        const status = res.statusCode || 0;
        if (status >= 200 && status < 300) {
          resolve(data ? JSON.parse(data) : {});
        } else {
          const err = new Error(`${options.method} ${options.path} -> ${status}: ${data.slice(0, 300)}`);
          err.statusCode = status;
          reject(err);
        }
      });
    });
    req.setTimeout(TIMEOUT_MS, () => {
      const err = new Error(`timeout ${options.method} ${options.path}`);
      err.code = 'ETIMEDOUT';
      req.destroy(err);
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

async function withRetry(fn, label) {
  for (let attempt = 1; attempt <= Math.max(1, RETRIES); attempt++) {
    try {
      return await fn();
    } catch (err) {
      if (attempt >= RETRIES || !isRetryable(err)) throw err;
      const delay = RETRY_DELAY_MS * attempt;
      console.warn(`retry ${label} ${attempt}/${RETRIES - 1} in ${delay}ms (${err.message})`);
      await sleep(delay);
    }
  }
}

function api(method, apiPath, body) {
  const data = body ? Buffer.from(JSON.stringify(body)) : null;
  return withRetry(
    () =>
      rawRequest(
        {
          method,
          hostname: 'api.github.com',
          path: apiPath,
          headers: authHeaders(data ? { 'Content-Type': 'application/json', 'Content-Length': data.length } : {}),
        },
        data,
      ),
    `${method} ${apiPath}`,
  );
}

// Draft releases are NOT found by tag (no git ref yet); search the list too.
async function getOrCreateRelease() {
  try {
    const r = await api('GET', `/repos/${owner}/${repo}/releases/tags/${tag}`);
    console.log(`Using published release ${tag} (id ${r.id}).`);
    return r;
  } catch (err) {
    if (err.statusCode !== 404) console.warn(err.message);
  }
  const releases = await api('GET', `/repos/${owner}/${repo}/releases?per_page=100`);
  const existing = Array.isArray(releases) ? releases.filter((r) => r.tag_name === tag) : [];
  if (existing.length) {
    existing.sort((a, b) => (b.assets?.length || 0) - (a.assets?.length || 0));
    console.log(`Using draft release ${tag} (id ${existing[0].id}).`);
    return existing[0];
  }
  const created = await api('POST', `/repos/${owner}/${repo}/releases`, {
    tag_name: tag,
    name: `${pkg.productName} ${version}`,
    draft: true,
    prerelease: version.includes('beta') || version.includes('alpha'),
  });
  console.log(`Created draft release ${tag} (id ${created.id}).`);
  return created;
}

async function deleteAssetIfExists(release, name) {
  const existing = (release.assets || []).find((a) => a.name === name);
  if (existing) await api('DELETE', `/repos/${owner}/${repo}/releases/assets/${existing.id}`);
}

function contentType(name) {
  return name.endsWith('.asc') || name.endsWith('.txt') ? 'text/plain' : 'application/octet-stream';
}

function uploadOnce(release, name) {
  const file = path.join(RELEASE_DIR, name);
  const size = fs.statSync(file).size;
  const url = new URL(release.upload_url.replace('{?name,label}', ''));
  url.searchParams.set('name', name);
  return new Promise((resolve, reject) => {
    const req = https.request(
      {
        method: 'POST',
        hostname: url.hostname,
        path: url.pathname + url.search,
        headers: authHeaders({ 'Content-Type': contentType(name), 'Content-Length': size }),
      },
      (res) => {
        let data = '';
        res.on('data', (c) => (data += c));
        res.on('end', () => {
          const status = res.statusCode || 0;
          if (status >= 200 && status < 300) resolve();
          else {
            const err = new Error(`upload ${name} -> ${status}: ${data.slice(0, 200)}`);
            err.statusCode = status;
            reject(err);
          }
        });
      },
    );
    req.setTimeout(TIMEOUT_MS, () => {
      const err = new Error(`upload timeout ${name}`);
      err.code = 'ETIMEDOUT';
      req.destroy(err);
    });
    req.on('error', reject);
    fs.createReadStream(file).pipe(req);
  });
}

async function uploadAsset(release, name) {
  await deleteAssetIfExists(release, name);
  await withRetry(() => uploadOnce(release, name), `upload ${name}`);
}

async function main() {
  const assets = listAssets();
  if (!assets.length) {
    console.error('No files in release/ to publish. Run dist + sign:gpg first.');
    process.exit(1);
  }

  if (dryRun) {
    console.log(`[dry-run] repo=${owner}/${repo} tag=${tag}`);
    console.log(`[dry-run] would upload ${assets.length} asset(s):`);
    assets.forEach((a) => console.log(`  - ${a}`));
    return;
  }

  if (!token) {
    console.error('Set GH_TOKEN in .env');
    process.exit(1);
  }

  const release = await getOrCreateRelease();
  for (const name of assets) {
    await uploadAsset(release, name);
    console.log(`uploaded ${name}`);
  }
  console.log(`Done. Draft release ${tag}: https://github.com/${owner}/${repo}/releases`);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});

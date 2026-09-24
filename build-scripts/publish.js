'use strict';

// Creates (or reuses) a draft GitHub release for v<version> and uploads every
// file in release/ (installers + .asc signatures + SHA256SUMS-*.txt).
// Auth: the GitHub CLI's stored login (`gh auth login`); no token in .env.

const fs = require('node:fs');
const path = require('node:path');
const { RELEASE_DIR, pkg, version } = require('./pkg');
const { assertGitHubCliAuthenticated, githubApi, uploadReleaseAsset } = require('./github-cli');

const dryRun = process.argv.includes('--dry-run');
const tag = `v${version}`;

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
  if (typeof err.statusCode === 'number' && codes.has(err.statusCode)) return true;
  const m = String(err.message || '').toLowerCase();
  return ['timeout', 'timed out', 'connection reset', 'eof', 'tls handshake', 'no such host'].some((s) => m.includes(s));
}

async function withRetry(fn, label) {
  for (let attempt = 1; attempt <= Math.max(1, RETRIES); attempt++) {
    try {
      return fn();
    } catch (err) {
      if (attempt >= RETRIES || !isRetryable(err)) throw err;
      const delay = RETRY_DELAY_MS * attempt;
      console.warn(`retry ${label} ${attempt}/${RETRIES - 1} in ${delay}ms (${err.message.split('\n')[0]})`);
      await sleep(delay);
    }
  }
}

const api = (method, endpoint, body) => withRetry(() => githubApi(method, endpoint, body), `${method} ${endpoint}`);

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

async function uploadAsset(release, name) {
  await deleteAssetIfExists(release, name);
  await withRetry(() => uploadReleaseAsset(release.upload_url, path.join(RELEASE_DIR, name)), `upload ${name}`);
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

  assertGitHubCliAuthenticated();
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

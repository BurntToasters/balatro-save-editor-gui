// Fills the download button and table from the latest GitHub release.
// The static HTML already links to releases/latest, so any failure here leaves a working page.
(() => {
  const REPO = 'BurntToasters/balatro-save-editor-gui';
  const CACHE_KEY = 'bse-latest-release';
  const CACHE_MS = 15 * 60 * 1000;

  const PLATFORMS = [
    { os: 'win', label: 'Windows', ext: 'exe' },
    { os: 'mac', label: 'macOS', ext: 'dmg' },
    { os: 'linux', label: 'Linux', ext: 'AppImage' },
  ];
  const ARCH_LABEL = { x64: 'x64', arm64: 'arm64' };
  const MAC_ARCH_LABEL = { arm64: 'Apple Silicon' };

  function detectOS() {
    const ua = navigator.userAgent || '';
    if (/android|iphone|ipad|ipod|mobile/i.test(ua)) return null;
    const p = ((navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || ua).toLowerCase();
    if (p.includes('win')) return 'win';
    if (p.includes('mac')) return 'mac';
    if (p.includes('linux') || p.includes('x11')) return 'linux';
    return null;
  }

  async function latestRelease() {
    try {
      const hit = JSON.parse(sessionStorage.getItem(CACHE_KEY) || 'null');
      if (hit && Date.now() - hit.at < CACHE_MS) return hit.data;
    } catch {
      /* storage unavailable */
    }
    const res = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
      headers: { Accept: 'application/vnd.github+json' },
    });
    if (!res.ok) throw new Error(`GitHub API ${res.status}`);
    const data = await res.json();
    try {
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), data }));
    } catch {
      /* storage unavailable */
    }
    return data;
  }

  function pickInstaller(assets, platform) {
    const re = new RegExp(`-${platform.os}-([a-z0-9]+)\\.${platform.ext}$`, 'i');
    const found = assets
      .map((a) => ({ asset: a, m: a.name.match(re) }))
      .filter((x) => x.m)
      .map((x) => ({ ...x.asset, arch: x.m[1].toLowerCase() }));
    return found[0] || null;
  }

  const archLabel = (platform, arch) =>
    (platform.os === 'mac' ? MAC_ARCH_LABEL : ARCH_LABEL)[arch] || arch;

  const mb = (bytes) => `${(bytes / 1048576).toFixed(0)} MB`;

  function el(tag, props = {}, ...children) {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...children.filter((c) => c != null));
    return node;
  }

  const link = (asset, text) => (asset ? el('a', { href: asset.browser_download_url }, text) : '—');

  function render(release) {
    const assets = release.assets || [];
    const byName = new Map(assets.map((a) => [a.name, a]));
    const version = (release.tag_name || '').replace(/^v/, '');
    const mine = detectOS();
    const rows = [];
    let mineRow = null;

    for (const platform of PLATFORMS) {
      const inst = pickInstaller(assets, platform);
      if (!inst) continue;
      const arch = archLabel(platform, inst.arch);
      const sig = byName.get(`${inst.name}.asc`);
      const sums = byName.get(`SHA256SUMS-${platform.os}-${inst.arch}.txt`);
      const row = el(
        'tr',
        { className: platform.os === mine ? 'mine' : '' },
        el('td', {}, platform.label, ' ', el('span', { className: 'arch' }, arch)),
        el('td', {}, el('a', { className: 'file', href: inst.browser_download_url }, inst.name), ' ',
          el('span', { className: 'size' }, mb(inst.size))),
        el('td', {}, link(sig, '.asc')),
        el('td', {}, link(sums, 'SHA256SUMS')),
      );
      rows.push(row);
      if (platform.os === mine) mineRow = { platform, inst, arch };
    }
    if (!rows.length) return;

    document.getElementById('dl-rows').replaceChildren(...rows);
    if (version) document.getElementById('dl-version').textContent = `v${version}`;

    const btn = document.getElementById('dl-main');
    const meta = document.getElementById('dl-meta');
    if (mineRow) {
      btn.textContent = `Download for ${mineRow.platform.label}`;
      btn.href = mineRow.inst.browser_download_url;
      meta.textContent = `v${version} · ${mineRow.platform.label} ${mineRow.arch} · ${mb(mineRow.inst.size)} · free and open source`;
    } else {
      btn.href = '#download';
      meta.textContent = `v${version} · Windows, macOS, Linux · free and open source`;
    }
  }

  latestRelease().then(render).catch(() => {
    /* keep the static releases/latest links */
  });
})();

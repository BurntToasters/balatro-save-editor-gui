const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;

let currentPath = null;

function setStatus(msg, kind = '') {
  const el = $('status');
  el.textContent = msg || '';
  el.className = 'status' + (kind ? ' ' + kind : '');
}

function ensureOption(path, label) {
  const sel = $('profile');
  sel.disabled = false;
  let opt = [...sel.options].find((o) => o.value === path);
  if (!opt) {
    opt = document.createElement('option');
    opt.value = path;
    opt.textContent = (label ? label + ' — ' : '') + path;
    sel.appendChild(opt);
  }
  sel.value = path;
}

function renderState(state) {
  const loaded = state && state.loaded;
  $('save').disabled = !loaded;
  if (!loaded) {
    $('save-path').textContent = '';
    return;
  }
  currentPath = state.save_path;
  $('save-path').textContent = state.save_path;
  $('cur-money').textContent = state.money ?? '—';
  $('cur-blind').textContent = state.blind_target ?? '—';
  $('cur-mult').textContent =
    state.hand_mults && state.hand_mults.length ? state.hand_mults.join(', ') : '—';
  $('cur-jokers').textContent = state.joker_limit ?? '—';
  $('cur-cons').textContent = state.consumable_limit ?? '—';
  $('cur-eternal').textContent = state.eternal_jokers ?? 0;

  if (state.money && !$('val-money').value) $('val-money').value = state.money;

  const hasBlind = state.blind_target != null;
  $('en-chips').disabled = !hasBlind;
  if (!hasBlind) $('en-chips').checked = false;
  $('en-chips').closest('.preset').classList.toggle('disabled', !hasBlind);

  const noEternal = !state.eternal_jokers;
  $('en-eternal').disabled = noEternal;
  if (noEternal) $('en-eternal').checked = false;
  $('en-eternal').closest('.preset').classList.toggle('disabled', noEternal);

  if ([...$('profile').options].some((o) => o.value === state.save_path)) {
    $('profile').value = state.save_path;
  }
}

function gather() {
  const num = (id) => Number($(id).value);
  return {
    money: { enabled: $('en-money').checked, value: num('val-money') },
    chips: { enabled: $('en-chips').checked },
    multipliers: { enabled: $('en-mult').checked, value: num('val-mult') },
    card_limits: {
      enabled: $('en-limits').checked,
      joker_limit: num('val-jokers'),
      consumable_limit: num('val-cons'),
    },
    strip_eternal: { enabled: $('en-eternal').checked },
  };
}

async function loadPath(path) {
  setStatus('Loading…');
  const res = await api().load_save(path ?? null);
  if (!res.ok) {
    renderState({ loaded: false });
    setStatus(res.error, 'error');
    return;
  }
  renderState(res.state);
  setStatus(`Loaded ${res.state.profile}.`, 'ok');
}

async function refreshProfiles() {
  const saves = await api().detect_saves();
  const sel = $('profile');
  sel.innerHTML = '';
  if (!saves.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No save detected';
    sel.appendChild(opt);
    sel.disabled = true;
    return saves;
  }
  sel.disabled = false;
  for (const s of saves) {
    const opt = document.createElement('option');
    opt.value = s.path;
    opt.textContent = `${s.label} — ${s.path}`;
    sel.appendChild(opt);
  }
  return saves;
}

async function applyAndSave() {
  if (!currentPath) {
    setStatus('No save loaded.', 'error');
    return;
  }
  const changes = gather();
  if (!Object.values(changes).some((c) => c.enabled)) {
    setStatus('Select at least one change first.', 'error');
    return;
  }
  $('save').disabled = true;
  setStatus('Applying…');
  try {
    const ap = await api().apply(changes);
    if (!ap.ok) {
      setStatus(ap.error, 'error');
      return;
    }
    const backup = $('backup').checked;
    const sv = await api().save(backup);
    if (!sv.ok) {
      setStatus(sv.error, 'error');
      return;
    }
    renderState(sv.state);
    setStatus('Saved.' + (backup ? ' A backup was created next to the save file.' : ''), 'ok');
  } finally {
    $('save').disabled = !currentPath;
  }
}

function openExternal(url) {
  if (url && window.pywebview) api().open_url(url);
}

function licenseEntryNode(e) {
  const wrap = document.createElement('div');
  wrap.className = 'license-entry';

  const head = document.createElement('div');
  head.className = 'license-head';
  const title = document.createElement('span');
  title.className = 'license-name';
  title.textContent = e.version ? `${e.name} ${e.version}` : e.name;
  const tag = document.createElement('span');
  tag.className = 'license-tag';
  tag.textContent = e.license || 'Unknown';
  head.append(title, tag);
  wrap.appendChild(head);

  if (e.url) {
    const a = document.createElement('a');
    a.href = '#';
    a.className = 'license-url';
    a.textContent = e.url;
    a.dataset.url = e.url;
    wrap.appendChild(a);
  }

  if (e.text) {
    const det = document.createElement('details');
    const sum = document.createElement('summary');
    sum.textContent = 'License text';
    const pre = document.createElement('pre');
    pre.textContent = e.text;
    det.append(sum, pre);
    wrap.appendChild(det);
  }
  return wrap;
}

async function openLicenses() {
  const body = $('licenses-body');
  body.textContent = 'Loading…';
  $('licenses-modal').hidden = false;
  let data;
  try {
    data = await api().get_licenses();
  } catch {
    body.textContent = 'Could not load license info.';
    return;
  }
  body.textContent = '';
  const entries = data.entries || [];
  if (data.app) {
    body.appendChild(licenseEntryNode({ ...data.app, license: (data.app.license || '') + ' · this app' }));
  }
  if (!entries.length && !data.app) {
    body.textContent = 'License information was not generated for this build.';
    return;
  }
  for (const e of entries) body.appendChild(licenseEntryNode(e));
}

function closeLicenses() {
  $('licenses-modal').hidden = true;
}

window.addEventListener('pywebviewready', async () => {
  $('open').addEventListener('click', async () => {
    const path = await api().pick_file();
    if (path) {
      ensureOption(path, 'Picked');
      await loadPath(path);
    }
  });
  $('reload').addEventListener('click', () => {
    if (currentPath) loadPath(currentPath);
  });
  $('profile').addEventListener('change', (e) => {
    if (e.target.value) loadPath(e.target.value);
  });
  $('save').addEventListener('click', applyAndSave);

  $('licenses-btn').addEventListener('click', openLicenses);
  $('licenses-close').addEventListener('click', closeLicenses);
  $('licenses-modal').addEventListener('click', (e) => {
    if (e.target.id === 'licenses-modal') closeLicenses();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLicenses();
  });
  document.addEventListener('click', (e) => {
    const link = e.target.closest('[data-url]');
    if (link) {
      e.preventDefault();
      openExternal(link.dataset.url);
    }
  });

  const saves = await refreshProfiles();
  if (saves.length) {
    await loadPath(saves[0].path);
  } else {
    setStatus('No Balatro save found. Use Open… to choose a save.jkr file.', '');
  }
});

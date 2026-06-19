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
    $('jokers-panel').hidden = true;
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
  await loadJokers();
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

// ---- jokers ----

const EDITION_OPTS = [
  ['', 'None'],
  ['foil', 'Foil'],
  ['holo', 'Holographic'],
  ['polychrome', 'Polychrome'],
  ['negative', 'Negative'],
];
const RARITY_NAMES = { 1: 'Common', 2: 'Uncommon', 3: 'Rare', 4: 'Legendary' };
let CATALOG = [];

const escapeHtml = (s) =>
  String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const escapeAttr = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const nameForKey = (key) => (CATALOG.find((c) => c.key === key) || {}).name || key;

function catalogOptionsHtml() {
  const groups = { 1: [], 2: [], 3: [], 4: [] };
  for (const j of CATALOG) (groups[j.rarity] || (groups[j.rarity] = [])).push(j);
  let html = '';
  for (const r of [1, 2, 3, 4]) {
    if (!groups[r] || !groups[r].length) continue;
    html += `<optgroup label="${RARITY_NAMES[r] || 'Rarity ' + r}">`;
    for (const j of groups[r]) html += `<option value="${escapeAttr(j.key)}">${escapeHtml(j.name)}</option>`;
    html += '</optgroup>';
  }
  return html;
}

function labeled(text, control) {
  const l = document.createElement('label');
  l.className = 'j-field';
  const s = document.createElement('span');
  s.textContent = text;
  l.append(s, control);
  return l;
}

function buildJokerRow(j) {
  const row = document.createElement('div');
  row.className = 'joker-row';

  const main = document.createElement('div');
  main.className = 'joker-main';
  const nm = document.createElement('span');
  nm.className = 'joker-name';
  nm.textContent = j.name || j.center || `Joker ${j.index + 1}`;
  const ct = document.createElement('span');
  ct.className = 'joker-center muted';
  ct.textContent = j.center || '';
  main.append(nm, ct);
  row.appendChild(main);

  const ctrls = document.createElement('div');
  ctrls.className = 'joker-ctrls';

  const typeSel = document.createElement('select');
  typeSel.className = 'j-type';
  typeSel.innerHTML = catalogOptionsHtml();
  if (j.center && !CATALOG.some((c) => c.key === j.center)) {
    const o = document.createElement('option');
    o.value = j.center;
    o.textContent = j.center;
    typeSel.prepend(o);
  }
  if (j.center) typeSel.value = j.center;
  typeSel.addEventListener('change', async () => {
    applyJokerResult(await api().joker_set_type(j.index, typeSel.value, nameForKey(typeSel.value)));
  });
  ctrls.append(labeled('Type', typeSel));

  const edSel = document.createElement('select');
  edSel.className = 'j-edition';
  for (const [val, label] of EDITION_OPTS) {
    const o = document.createElement('option');
    o.value = val;
    o.textContent = label;
    edSel.appendChild(o);
  }
  edSel.value = j.edition || '';
  edSel.addEventListener('change', async () => {
    applyJokerResult(await api().joker_set_edition(j.index, edSel.value));
  });
  ctrls.append(labeled('Edition', edSel));

  const stickers = document.createElement('span');
  stickers.className = 'j-stickers';
  for (const s of ['eternal', 'perishable', 'rental']) {
    const lbl = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = (j.stickers || []).includes(s);
    cb.addEventListener('change', async () => {
      applyJokerResult(await api().joker_set_sticker(j.index, s, cb.checked));
    });
    lbl.append(cb, document.createTextNode(' ' + capitalize(s)));
    stickers.appendChild(lbl);
  }
  ctrls.append(labeled('Stickers', stickers));

  const sell = document.createElement('input');
  sell.type = 'number';
  sell.min = '0';
  sell.className = 'j-sell';
  if (j.sell_cost != null) sell.value = j.sell_cost;
  sell.addEventListener('change', async () => {
    applyJokerResult(await api().joker_set_sell(j.index, Number(sell.value)));
  });
  ctrls.append(labeled('Sell', sell));

  row.appendChild(ctrls);

  const acts = document.createElement('div');
  acts.className = 'joker-acts';
  const dup = document.createElement('button');
  dup.className = 'ghost';
  dup.textContent = 'Duplicate';
  dup.addEventListener('click', async () => applyJokerResult(await api().joker_duplicate(j.index)));
  const del = document.createElement('button');
  del.className = 'danger';
  del.textContent = 'Delete';
  del.addEventListener('click', async () => applyJokerResult(await api().joker_delete(j.index)));
  acts.append(dup, del);
  row.appendChild(acts);

  return row;
}

function renderJokers(jokers) {
  const list = $('joker-list');
  list.textContent = '';
  $('joker-count').textContent = `(${jokers.length})`;
  if (!jokers.length) {
    const p = document.createElement('p');
    p.className = 'muted';
    p.textContent = 'No jokers in this save.';
    list.appendChild(p);
  }
  for (const j of jokers) list.appendChild(buildJokerRow(j));
}

function applyJokerResult(res) {
  if (!res || !res.ok) {
    setStatus((res && res.error) || 'Joker edit failed.', 'error');
    return;
  }
  renderJokers(res.jokers);
  setStatus('Joker changed — not saved yet. Use "Save jokers to disk".', '');
}

async function loadJokers() {
  const res = await api().get_jokers();
  const ok = !!(res && res.ok);
  $('jokers-panel').hidden = !ok;
  if (ok) {
    renderJokers(res.jokers);
    $('jokers-save').disabled = false;
  }
}

async function saveJokers() {
  if (!currentPath) {
    setStatus('No save loaded.', 'error');
    return;
  }
  $('jokers-save').disabled = true;
  setStatus('Saving jokers…');
  const backup = $('backup').checked;
  const sv = await api().save(backup);
  if (!sv.ok) {
    setStatus(sv.error, 'error');
    $('jokers-save').disabled = false;
    return;
  }
  renderState(sv.state);
  await loadJokers();
  setStatus('Jokers saved.' + (backup ? ' A backup was created.' : ''), 'ok');
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

  try {
    CATALOG = await api().joker_catalog();
    $('joker-add-select').innerHTML = catalogOptionsHtml();
  } catch {
    /* catalog unavailable */
  }
  $('jokers-save').addEventListener('click', saveJokers);
  $('joker-add-btn').addEventListener('click', async () => {
    const key = $('joker-add-select').value;
    if (key) applyJokerResult(await api().joker_add(key, nameForKey(key)));
  });

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

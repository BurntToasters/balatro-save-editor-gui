const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;

let currentPath = null;
let jokersDirty = false;
let debug = false;

// ---- status / dirty ----

function setStatus(msg, kind = '') {
  const el = $('status');
  el.textContent = msg || '';
  el.title = msg || '';
  el.className = 'status' + (kind ? ' ' + kind : '');
}

const PRESET_TOGGLES = ['en-money', 'en-chips', 'en-mult', 'en-limits', 'en-eternal'];

const presetsDirty = () => PRESET_TOGGLES.some((id) => $(id).checked);
const isDirty = () => jokersDirty || presetsDirty();

function refreshDirty() {
  const dirty = !!currentPath && isDirty();
  $('dirty').hidden = !dirty;
  $('save').disabled = !dirty;
}

function clearPresets() {
  for (const id of PRESET_TOGGLES) $(id).checked = false;
}

async function confirmDiscard() {
  if (!currentPath || !isDirty()) return true;
  return api().confirm('Discard changes?', 'You have unsaved changes. Discard them?');
}

// ---- save file / run state ----

function selectProfile(path, label) {
  const sel = $('profile');
  if (sel.disabled) sel.textContent = ''; // drop the "No save detected" placeholder
  sel.disabled = false;
  if (![...sel.options].some((o) => o.value === path)) {
    const opt = new Option(`${label} (opened)`, path);
    opt.title = path;
    sel.appendChild(opt);
  }
  sel.value = path;
}

function setPresetAvailable(toggleId, available) {
  const cb = $(toggleId);
  cb.disabled = !available;
  if (!available) cb.checked = false;
  cb.closest('.row').classList.toggle('na', !available);
}

function renderState(state) {
  const loaded = !!(state && state.loaded);
  $('run-set').disabled = !loaded;
  $('joker-add-set').disabled = !loaded;
  $('reload').disabled = !loaded;
  if (!loaded) {
    currentPath = null;
    $('save-path').textContent = '';
    renderJokers(null);
    refreshDirty();
    return;
  }
  currentPath = state.save_path;
  $('save-path').textContent = state.save_path;
  $('save-path').title = state.save_path;
  $('cur-money').textContent = state.money ?? '—';
  $('cur-blind').textContent = state.blind_target ?? '—';
  $('cur-mult').textContent =
    state.hand_mults && state.hand_mults.length ? state.hand_mults.join(', ') : '—';
  $('cur-jokers').textContent = state.joker_limit ?? '—';
  $('cur-cons').textContent = state.consumable_limit ?? '—';
  $('cur-eternal').textContent = state.eternal_jokers ?? 0;

  if (state.money && !$('val-money').value) $('val-money').value = state.money;

  setPresetAvailable('en-chips', state.blind_target != null);
  setPresetAvailable('en-eternal', !!state.eternal_jokers);

  selectProfile(state.save_path, state.profile);
  refreshDirty();
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
  clearPresets();
  jokersDirty = false;
  if (!res.ok) {
    renderState({ loaded: false });
    setStatus(res.error, 'error');
    return;
  }
  renderState(res.state);
  await loadJokers();
  setStatus(`Loaded ${res.state.profile}.`);
}

async function refreshProfiles() {
  const saves = await api().detect_saves();
  const sel = $('profile');
  sel.textContent = '';
  if (!saves.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No save detected — use Open…';
    sel.appendChild(opt);
    sel.disabled = true;
    return saves;
  }
  sel.disabled = false;
  for (const s of saves) {
    const opt = new Option(s.label, s.path);
    opt.title = s.path;
    sel.appendChild(opt);
  }
  return saves;
}

async function save() {
  if (!currentPath || !isDirty()) return;
  $('save').disabled = true;
  setStatus('Saving…');
  try {
    if (presetsDirty()) {
      const ap = await api().apply(gather());
      if (!ap.ok) {
        setStatus(ap.error, 'error');
        return;
      }
    }
    const backup = $('backup').checked;
    const sv = await api().save(backup);
    if (!sv.ok) {
      setStatus(sv.error, 'error');
      return;
    }
    clearPresets();
    jokersDirty = false;
    renderState(sv.state);
    await loadJokers();
    setStatus('Saved.' + (backup ? ' Backup created next to the save file.' : ''), 'ok');
  } finally {
    refreshDirty();
  }
}

async function openFile() {
  if (!(await confirmDiscard())) return;
  const path = await api().pick_file();
  if (path) await loadPath(path);
}

// ---- jokers ----

const EDITION_OPTS = [
  ['', 'None'],
  ['foil', 'Foil'],
  ['holo', 'Holographic'],
  ['polychrome', 'Polychrome'],
  ['negative', 'Negative'],
];
const STICKERS = ['eternal', 'perishable', 'rental'];
const RARITY_NAMES = { 1: 'Common', 2: 'Uncommon', 3: 'Rare', 4: 'Legendary' };
let CATALOG = [];
let catalogTemplate = document.createElement('select');

const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const nameForKey = (key) => (CATALOG.find((c) => c.key === key) || {}).name || key;

function buildCatalogTemplate() {
  const sel = document.createElement('select');
  const groups = {};
  for (const j of CATALOG) (groups[j.rarity] || (groups[j.rarity] = [])).push(j);
  for (const r of Object.keys(groups).sort()) {
    const og = document.createElement('optgroup');
    og.label = RARITY_NAMES[r] || `Rarity ${r}`;
    for (const j of groups[r]) og.appendChild(new Option(j.name, j.key));
    sel.appendChild(og);
  }
  catalogTemplate = sel;
}

const catalogSelect = () => catalogTemplate.cloneNode(true);

function mini(text, control) {
  const l = document.createElement('label');
  l.className = 'mini';
  l.append(text, control);
  return l;
}

function button(text, cls, onClick) {
  const b = document.createElement('button');
  b.className = cls;
  b.textContent = text;
  b.addEventListener('click', onClick);
  return b;
}

function buildJokerRow(j) {
  const row = document.createElement('div');
  row.className = 'joker';

  const name = document.createElement('div');
  name.className = 'joker-name';
  const nm = document.createElement('b');
  nm.textContent = j.name || j.center || `Joker ${j.index + 1}`;
  const ct = document.createElement('span');
  ct.className = 'muted';
  ct.textContent = j.center || '';
  name.append(nm, ct);

  const acts = document.createElement('div');
  acts.className = 'joker-acts';
  acts.append(
    button('Duplicate', 'quiet', async () => applyJokerResult(await api().joker_duplicate(j.index))),
    button('Delete', 'quiet danger', async () => applyJokerResult(await api().joker_delete(j.index))),
  );

  const ctrls = document.createElement('div');
  ctrls.className = 'joker-ctrls';

  const typeSel = catalogSelect();
  if (j.center && !CATALOG.some((c) => c.key === j.center)) {
    typeSel.prepend(new Option(j.center, j.center));
  }
  if (j.center) typeSel.value = j.center;
  typeSel.addEventListener('change', async () => {
    applyJokerResult(await api().joker_set_type(j.index, typeSel.value, nameForKey(typeSel.value)));
  });

  const edSel = document.createElement('select');
  for (const [val, label] of EDITION_OPTS) edSel.appendChild(new Option(label, val));
  edSel.value = j.edition || '';
  edSel.addEventListener('change', async () => {
    applyJokerResult(await api().joker_set_edition(j.index, edSel.value));
  });

  const sell = document.createElement('input');
  sell.type = 'number';
  sell.min = '0';
  sell.step = '1';
  if (j.sell_cost != null) sell.value = j.sell_cost;
  sell.addEventListener('change', async () => {
    applyJokerResult(await api().joker_set_sell(j.index, Number(sell.value)));
  });

  const stickers = document.createElement('div');
  stickers.className = 'stickers';
  for (const s of STICKERS) {
    const lbl = document.createElement('label');
    lbl.className = 'check';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = (j.stickers || []).includes(s);
    cb.addEventListener('change', async () => {
      applyJokerResult(await api().joker_set_sticker(j.index, s, cb.checked));
    });
    lbl.append(cb, capitalize(s));
    stickers.appendChild(lbl);
  }

  ctrls.append(mini('Type', typeSel), mini('Edition', edSel), mini('Sell', sell), stickers);
  row.append(name, acts, ctrls);
  return row;
}

function renderJokers(jokers) {
  const list = $('joker-list');
  const scroller = $('content');
  const keep = scroller.scrollTop;
  list.textContent = '';
  $('joker-count').textContent = jokers ? `(${jokers.length})` : '';
  if (!jokers || !jokers.length) {
    const p = document.createElement('p');
    p.className = 'empty';
    p.textContent = jokers ? 'No jokers in this save.' : 'No save loaded.';
    list.appendChild(p);
  } else {
    for (const j of jokers) list.appendChild(buildJokerRow(j));
  }
  scroller.scrollTop = keep;
}

function applyJokerResult(res) {
  if (!res || !res.ok) {
    setStatus((res && res.error) || 'Joker edit failed.', 'error');
    return;
  }
  jokersDirty = true;
  renderJokers(res.jokers);
  refreshDirty();
  setStatus('');
}

async function loadJokers() {
  const res = await api().get_jokers();
  renderJokers(res && res.ok ? res.jokers : null);
}

// ---- licenses ----

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
  $('licenses-close').focus();
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

// ---- sidebar: jump + scrollspy ----

function initNav() {
  const scroller = $('content');
  const items = [...document.querySelectorAll('.nav-item')];
  const sections = items.map((b) => $(b.dataset.target));

  let jumping = false;

  const setActive = (idx) => items.forEach((b, i) => b.classList.toggle('active', i === idx));

  items.forEach((b, i) =>
    b.addEventListener('click', () => {
      // Keep the clicked item active even when a short section can't reach the top.
      jumping = true;
      scroller.scrollTop = sections[i].offsetTop;
      setActive(i);
      requestAnimationFrame(() => requestAnimationFrame(() => (jumping = false)));
    }),
  );

  scroller.addEventListener('scroll', () => {
    if (jumping) return;
    const top = scroller.scrollTop;
    if (top + scroller.clientHeight >= scroller.scrollHeight - 2) return setActive(sections.length - 1);
    let idx = 0;
    sections.forEach((s, i) => {
      if (s.offsetTop <= top + 24) idx = i;
    });
    setActive(idx);
  });
}

// ---- make the webview behave like a window, not a page ----

const BLOCKED_KEYS = new Set(['r', 'f', 'g', 'p', 'u', 's', 'o', 'j', 'h', '+', '-', '=', '0']);

function initAppFeel() {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !$('licenses-modal').hidden) {
      closeLicenses();
      return;
    }
    const mod = e.ctrlKey || e.metaKey;
    const k = e.key.toLowerCase();
    if (mod && !e.shiftKey && !e.altKey && (k === 's' || k === 'o')) {
      e.preventDefault();
      if (k === 's') save();
      else if ($('licenses-modal').hidden) openFile();
      return;
    }
    if (debug) return;
    if (/^F(3|5|7|12)$/.test(e.key) || (mod && BLOCKED_KEYS.has(k)) || (e.altKey && /^Arrow(Left|Right)$/.test(e.key))) {
      e.preventDefault();
    }
    if (e.key === 'Backspace' && !e.target.closest('input, textarea, select')) e.preventDefault();
  });

  document.addEventListener('contextmenu', (e) => {
    if (!debug && !e.target.closest('input[type="number"], textarea')) e.preventDefault();
  });

  document.addEventListener('wheel', (e) => { if (e.ctrlKey) e.preventDefault(); }, { passive: false });
  // Scrolling over a focused number field shouldn't silently change its value.
  document.addEventListener('wheel', (e) => {
    const a = document.activeElement;
    if (a && a.type === 'number' && e.target === a) a.blur();
  }, { passive: true });

  for (const t of ['dragover', 'drop']) document.addEventListener(t, (e) => e.preventDefault());
  document.addEventListener('dragstart', (e) => { if (!e.target.closest?.('input')) e.preventDefault(); });

  document.addEventListener('click', (e) => {
    const link = e.target.closest('[data-url]');
    if (link) {
      e.preventDefault();
      api().open_url(link.dataset.url);
    } else if (e.target.closest('a')) {
      e.preventDefault();
    }
  });
}

// ---- boot ----

window.addEventListener('pywebviewready', async () => {
  try {
    const info = await api().app_info();
    debug = !!info.debug;
    if (info.version) $('app-version').textContent = info.version;
  } catch {
    /* older bridge */
  }
  initAppFeel();
  initNav();

  $('open').addEventListener('click', openFile);
  $('reload').addEventListener('click', async () => {
    if (currentPath && (await confirmDiscard())) loadPath(currentPath);
  });
  $('profile').addEventListener('change', async (e) => {
    const path = e.target.value;
    if (!path) return;
    if (!(await confirmDiscard())) {
      e.target.value = currentPath || '';
      return;
    }
    loadPath(path);
  });
  $('save').addEventListener('click', save);

  for (const id of PRESET_TOGGLES) $(id).addEventListener('change', refreshDirty);
  // Typing a value implies you want that preset applied.
  for (const input of document.querySelectorAll('[data-toggle]')) {
    input.addEventListener('input', () => {
      const cb = $(input.dataset.toggle);
      if (!cb.disabled && !cb.checked) {
        cb.checked = true;
        refreshDirty();
      }
    });
  }

  try {
    CATALOG = await api().joker_catalog();
    buildCatalogTemplate();
    const addSel = $('joker-add-select');
    addSel.replaceChildren(...catalogSelect().childNodes);
    addSel.selectedIndex = 0;
  } catch {
    /* catalog unavailable */
  }
  $('joker-add-btn').addEventListener('click', async () => {
    const key = $('joker-add-select').value;
    if (key) applyJokerResult(await api().joker_add(key, nameForKey(key)));
  });

  $('licenses-btn').addEventListener('click', openLicenses);
  $('licenses-close').addEventListener('click', closeLicenses);
  $('licenses-modal').addEventListener('click', (e) => {
    if (e.target.id === 'licenses-modal') closeLicenses();
  });

  try {
    const saves = await refreshProfiles();
    if (saves.length) {
      await loadPath(saves[0].path);
    } else {
      renderState({ loaded: false });
      setStatus('No Balatro save found. Use Open… to choose a save.jkr file.');
    }
  } finally {
    api().ui_ready();
  }
});

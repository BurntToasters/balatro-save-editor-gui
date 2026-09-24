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
const RARITY_ORDER = [1, 2, 3, 4, 0]; // 0 = not in the catalog ("Other")
let CATALOG = [];

const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const catalogEntry = (key) => CATALOG.find((c) => c.key === key) || null;
const nameForKey = (key) => (catalogEntry(key) || {}).name || key;
const rarityOf = (key) => (catalogEntry(key) || {}).rarity || 0;

function rarityDot(r) {
  const d = document.createElement('span');
  d.className = `rdot r${r}`;
  d.setAttribute('aria-hidden', 'true');
  return d;
}

// ---- joker picker: a searchable, rarity-coloured stand-in for <select> ----
// Each trigger is a button; one shared popover (#jpick-pop) serves them all.

const picker = { owner: null, options: [], active: -1 };

function renderTrigger(btn) {
  const st = btn._jpick;
  const name = document.createElement('span');
  name.className = 'jpick-name';
  name.textContent = st.value ? nameForKey(st.value) : st.placeholder;
  const chev = document.createElement('span');
  chev.className = 'jpick-chev';
  chev.setAttribute('aria-hidden', 'true');
  btn.replaceChildren(rarityDot(st.value ? rarityOf(st.value) : 0), name, chev);
  btn.title = st.value ? `${nameForKey(st.value)} (${st.value})` : st.placeholder;
}

function createJokerPicker({ value = '', onChange = null, placeholder = 'Choose a joker', id = '' } = {}) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'jpick';
  if (id) btn.id = id;
  btn.setAttribute('aria-haspopup', 'listbox');
  btn.setAttribute('aria-expanded', 'false');
  btn._jpick = { value, extra: value && !catalogEntry(value) ? value : null, onChange, placeholder };
  Object.defineProperty(btn, 'value', { get: () => btn._jpick.value });
  renderTrigger(btn);
  btn.addEventListener('click', () => (picker.owner === btn ? closePicker() : openPicker(btn)));
  btn.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      openPicker(btn);
    } else if (e.key.length === 1 && e.key !== ' ' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      // Start typing on a focused picker to search straight away.
      e.preventDefault();
      openPicker(btn, e.key);
    }
  });
  return btn;
}

function pickerMatches(item, q) {
  return !q || item.name.toLowerCase().includes(q) || item.key.toLowerCase().includes(q);
}

function renderPickerOptions() {
  const st = picker.owner._jpick;
  const q = $('jpick-search').value.trim().toLowerCase();
  const list = $('jpick-list');
  const items = st.extra ? [...CATALOG, { key: st.extra, name: st.extra, rarity: 0 }] : CATALOG;
  list.textContent = '';
  picker.options = [];
  for (const r of RARITY_ORDER) {
    const group = items.filter((it) => (it.rarity || 0) === r && pickerMatches(it, q));
    if (!group.length) continue;
    const head = document.createElement('div');
    head.className = `jpick-head r${r}`;
    head.setAttribute('role', 'presentation');
    head.textContent = RARITY_NAMES[r] || 'Other';
    list.appendChild(head);
    for (const it of group) {
      const i = picker.options.length;
      const opt = document.createElement('div');
      opt.className = `jpick-opt r${r}`;
      opt.id = `jpick-opt-${i}`;
      opt.setAttribute('role', 'option');
      opt.setAttribute('aria-selected', String(it.key === st.value));
      const name = document.createElement('span');
      name.className = 'jpick-name';
      name.textContent = it.name;
      const key = document.createElement('span');
      key.className = 'jpick-key';
      key.textContent = it.key;
      opt.append(rarityDot(r), name, key);
      opt.addEventListener('mousedown', (e) => e.preventDefault()); // keep focus in the search box
      opt.addEventListener('mousemove', () => setPickerActive(i, false));
      opt.addEventListener('click', () => choosePicker(it.key));
      list.appendChild(opt);
      picker.options.push({ el: opt, key: it.key });
    }
  }
  if (!picker.options.length) {
    const empty = document.createElement('div');
    empty.className = 'jpick-empty';
    empty.textContent = 'No jokers match';
    list.appendChild(empty);
  }
}

function setPickerActive(i, scroll = true) {
  const opts = picker.options;
  if (picker.active >= 0 && opts[picker.active]) opts[picker.active].el.classList.remove('active');
  if (!opts.length) {
    picker.active = -1;
    $('jpick-search').removeAttribute('aria-activedescendant');
    return;
  }
  picker.active = Math.max(0, Math.min(i, opts.length - 1));
  const el = opts[picker.active].el;
  el.classList.add('active');
  $('jpick-search').setAttribute('aria-activedescendant', el.id);
  if (scroll) el.scrollIntoView({ block: 'nearest' });
}

function positionPicker() {
  const pop = $('jpick-pop');
  const r = picker.owner.getBoundingClientRect();
  const margin = 8;
  const width = Math.max(r.width, 280);
  const below = window.innerHeight - r.bottom - margin;
  const above = r.top - margin;
  const want = 380;
  pop.style.width = `${width}px`;
  pop.style.left = `${Math.max(margin, Math.min(r.left, window.innerWidth - width - margin))}px`;
  if (below >= Math.min(want, 240) || below >= above) {
    pop.style.top = `${r.bottom + 4}px`;
    pop.style.bottom = 'auto';
    pop.style.maxHeight = `${Math.min(want, below - 4)}px`;
  } else {
    pop.style.top = 'auto';
    pop.style.bottom = `${window.innerHeight - r.top + 4}px`;
    pop.style.maxHeight = `${Math.min(want, above - 4)}px`;
  }
}

function openPicker(btn, initialText = '') {
  if (btn.disabled || !CATALOG.length) return;
  if (picker.owner && picker.owner !== btn) closePicker(false);
  picker.owner = btn;
  btn.setAttribute('aria-expanded', 'true');
  const search = $('jpick-search');
  search.value = initialText;
  $('jpick-pop').hidden = false;
  renderPickerOptions();
  positionPicker();
  search.focus();
  const selected = picker.options.findIndex((o) => o.key === btn._jpick.value);
  setPickerActive(initialText || selected < 0 ? 0 : selected);
}

function closePicker(restoreFocus = true) {
  const owner = picker.owner;
  if (!owner) return;
  picker.owner = null;
  picker.options = [];
  picker.active = -1;
  $('jpick-pop').hidden = true;
  owner.setAttribute('aria-expanded', 'false');
  if (restoreFocus && owner.isConnected) owner.focus();
}

function choosePicker(key) {
  const btn = picker.owner;
  if (!btn) return;
  const st = btn._jpick;
  closePicker();
  if (key === st.value) return;
  st.value = key;
  renderTrigger(btn);
  if (st.onChange) st.onChange(key);
}

function initPicker() {
  const search = $('jpick-search');
  search.addEventListener('input', () => {
    renderPickerOptions();
    setPickerActive(0);
  });
  search.addEventListener('keydown', (e) => {
    const page = 8;
    const moves = {
      ArrowDown: picker.active + 1,
      ArrowUp: picker.active - 1,
      PageDown: picker.active + page,
      PageUp: picker.active - page,
    };
    if (e.key in moves) {
      e.preventDefault();
      setPickerActive(moves[e.key]);
    } else if ((e.key === 'Home' || e.key === 'End') && !search.value) {
      e.preventDefault();
      setPickerActive(e.key === 'Home' ? 0 : picker.options.length - 1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (picker.options[picker.active]) choosePicker(picker.options[picker.active].key);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation(); // close only the picker, not a sheet underneath
      closePicker();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      closePicker();
    }
  });
  document.addEventListener(
    'mousedown',
    (e) => {
      if (picker.owner && !$('jpick-pop').contains(e.target) && !picker.owner.contains(e.target)) closePicker(false);
    },
    true,
  );
  $('content').addEventListener('scroll', () => closePicker(false));
  window.addEventListener('resize', () => closePicker(false));
}

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
  const r = rarityOf(j.center);
  if (r) {
    const tag = document.createElement('span');
    tag.className = `rtag r${r}`;
    tag.textContent = RARITY_NAMES[r];
    name.append(nm, tag, ct);
  } else {
    name.append(nm, ct);
  }

  const acts = document.createElement('div');
  acts.className = 'joker-acts';
  acts.append(
    button('Duplicate', 'quiet', async () => applyJokerResult(await api().joker_duplicate(j.index))),
    button('Delete', 'quiet danger', async () => applyJokerResult(await api().joker_delete(j.index))),
  );

  const ctrls = document.createElement('div');
  ctrls.className = 'joker-ctrls';

  const typeSel = createJokerPicker({
    value: j.center || '',
    placeholder: 'Unknown joker',
    onChange: async (key) => applyJokerResult(await api().joker_set_type(j.index, key, nameForKey(key))),
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

// ---- sheets (licenses, settings) ----

const MODALS = ['licenses-modal', 'settings-modal'];
let modalReturnFocus = null;

const openModalId = () => MODALS.find((id) => !$(id).hidden) || null;

function openModal(id, focusId) {
  modalReturnFocus = document.activeElement;
  $(id).hidden = false;
  $(focusId).focus();
}

function closeModal() {
  const id = openModalId();
  if (!id) return;
  $(id).hidden = true;
  if (modalReturnFocus && modalReturnFocus.focus) modalReturnFocus.focus();
  modalReturnFocus = null;
}

async function openLicenses() {
  const body = $('licenses-body');
  body.textContent = 'Loading…';
  openModal('licenses-modal', 'licenses-close');
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

// ---- settings (settings.json, owned by Python) ----

let settingsState = { ui: 'themed', backup: true, check_updates: true };

function applySettings(next) {
  settingsState = { ...settingsState, ...next };
  document.documentElement.dataset.ui = settingsState.ui;
  for (const b of document.querySelectorAll('[data-ui-choice]')) {
    b.setAttribute('aria-pressed', String(b.dataset.uiChoice === settingsState.ui));
  }
  $('backup').checked = settingsState.backup;
  $('set-backup').checked = settingsState.backup;
  $('set-updates').checked = settingsState.check_updates;
}

async function changeSetting(key, value) {
  const previous = { ...settingsState };
  applySettings({ [key]: value });
  const res = await api().set_setting(key, value);
  if (!res || !res.ok) {
    applySettings(previous);
    setStatus((res && res.error) || 'Could not save settings.', 'error');
    return;
  }
  applySettings(res.settings);
}

// ---- updates: compare with GitHub's latest release, offer the download page ----

let updateCheckRunning = false;

async function checkForUpdates({ quiet = false } = {}) {
  if (updateCheckRunning) return;
  updateCheckRunning = true;
  const btn = $('update-check');
  const out = $('update-status');
  btn.disabled = true;
  if (!quiet) out.textContent = 'Checking…';
  let res;
  try {
    res = await api().check_for_updates();
  } catch {
    res = null;
  } finally {
    btn.disabled = false;
    updateCheckRunning = false;
  }
  if (!res || !res.ok) {
    // A failed check on launch stays silent; the manual button reports it.
    if (!quiet) out.textContent = (res && res.error) || 'Update check failed.';
    return;
  }
  if (!res.update_available) {
    out.textContent = `You're up to date (${res.current}).`;
    return;
  }
  out.textContent = `Version ${res.latest} is available. You have ${res.current}.`;
  const go = await api().confirm(
    'Update available',
    `Balatro Save Editor ${res.latest} is available. You have ${res.current}.\n\nOpen the download page?`,
  );
  if (go) api().open_url(res.url);
  else if (quiet) setStatus(`Version ${res.latest} is available. Settings → Check now to get it.`);
}

async function resetSettings() {
  const ok = await api().confirm(
    'Reset settings?',
    'Reset all settings to their defaults? The app needs to restart to finish.',
  );
  if (!ok) return;
  const res = await api().reset_settings();
  if (!res || !res.ok) {
    setStatus((res && res.error) || 'Could not reset settings.', 'error');
    return;
  }
  applySettings(res.settings);
  const unsaved = currentPath && isDirty() ? ' Your unsaved changes will be lost.' : '';
  if (await api().confirm('Restart now?', `Settings were reset. Restart Balatro Save Editor now?${unsaved}`)) {
    const r = await api().restart();
    if (!r || !r.ok) setStatus((r && r.error) || 'Could not restart. Close and reopen the app.', 'error');
    return;
  }
  closeModal();
  setStatus('Settings reset. Restart the app to finish.');
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
    if (e.key === 'Escape' && picker.owner) {
      closePicker();
      return;
    }
    if (e.key === 'Escape' && openModalId()) {
      closeModal();
      return;
    }
    const mod = e.ctrlKey || e.metaKey;
    const k = e.key.toLowerCase();
    if (mod && !e.shiftKey && !e.altKey && (k === 's' || k === 'o')) {
      e.preventDefault();
      if (k === 's') save();
      else if (!openModalId() && !picker.owner) openFile();
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
    if (info.version) {
      $('app-version').textContent = info.version;
      $('settings-version').textContent = `v${info.version}`;
    }
    if (info.settings) applySettings(info.settings);
    if (info.settings_path) $('settings-path').textContent = info.settings_path;
  } catch {
    /* older bridge */
  }
  initAppFeel();
  initNav();
  initPicker();

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
    const first = CATALOG[0] ? CATALOG[0].key : '';
    $('joker-add-select').replaceWith(createJokerPicker({ id: 'joker-add-select', value: first }));
  } catch {
    /* catalog unavailable */
  }
  $('joker-add-btn').addEventListener('click', async () => {
    const key = $('joker-add-select').value;
    if (key) applyJokerResult(await api().joker_add(key, nameForKey(key)));
  });

  $('licenses-btn').addEventListener('click', openLicenses);
  $('licenses-close').addEventListener('click', closeModal);
  $('settings-btn').addEventListener('click', () => openModal('settings-modal', 'settings-close'));
  $('settings-close').addEventListener('click', closeModal);
  for (const id of MODALS) {
    $(id).addEventListener('click', (e) => {
      if (e.target.id === id) closeModal();
    });
  }

  for (const b of document.querySelectorAll('[data-ui-choice]')) {
    b.addEventListener('click', () => {
      if (b.dataset.uiChoice !== settingsState.ui) changeSetting('ui', b.dataset.uiChoice);
    });
  }
  $('backup').addEventListener('change', (e) => changeSetting('backup', e.target.checked));
  $('set-backup').addEventListener('change', (e) => changeSetting('backup', e.target.checked));
  $('set-updates').addEventListener('change', (e) => changeSetting('check_updates', e.target.checked));
  $('update-check').addEventListener('click', () => checkForUpdates());
  $('settings-reset').addEventListener('click', resetSettings);

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
  if (settingsState.check_updates) checkForUpdates({ quiet: true });
});

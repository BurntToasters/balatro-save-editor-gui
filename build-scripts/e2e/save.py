# E2E: save-file safety through the same Api the page calls (FAILURE_MODES.md 3, 5, 9, 10).
# Run: npm run e2e (or directly with the venv python). Report: e2e-artifacts/save.json
import getpass
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from report import Report, sha256  # noqa: E402

from app import paths  # noqa: E402
from app.api import Api  # noqa: E402
from app.editor import BalatroSaveFile  # noqa: E402

R = Report('save')
TMP = Path(tempfile.mkdtemp(prefix='bse-e2e-save-'))

RUN = (
    'return{["GAME"]={["dollars"]=4,["chips"]=0,["chips_text"]="0",'
    '["hands"]={["High Card"]={["mult"]=1,["played"]=0,},},},["BLIND"]={["chips"]=300,},'
    '["cardAreas"]={["jokers"]={["config"]={["card_limit"]=5,["temp_limit"]=5,},["cards"]={'
    '[1]={["ability"]={["name"]=NAME,},["label"]=NAME,["save_fields"]={["center"]="j_joker",},},'
    '},},["consumeables"]={["config"]={["card_limit"]=2,["temp_limit"]=2,},["cards"]={},},},}'
)


def make_save(folder, name_literal=b'"Joker"'):
    path = TMP / folder / 'save.jkr'
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = RUN.encode('ascii').replace(b'NAME', name_literal)
    path.write_bytes(BalatroSaveFile.compress(raw))
    return path


def text_of(path):
    return BalatroSaveFile.decompress(path.read_bytes())


def temp_files(path):
    return sorted(p.name for p in path.parent.glob('.save.jkr.*.tmp'))


def edit_money(path, value, backup=False):
    api = Api()
    assert api.load_save(str(path))['ok']
    api.apply({'money': {'enabled': True, 'value': value}})
    return api, api.save(create_backup=backup)


# ---- 3. atomic write ----

p = make_save('atomic')
R.input('seed_save_sha256', sha256(p))
api = Api()
api.load_save(str(p))
api.apply({'money': {'enabled': True, 'value': 111}})
before = p.read_bytes()
real_fsync = os.fsync


def failing_fsync(fd):
    raise OSError('disk full (injected halfway through the write)')


os.fsync = failing_fsync
try:
    res = api.save(create_backup=False)
finally:
    os.fsync = real_fsync
R.check('save: failed write keeps original', not res['ok'] and p.read_bytes() == before,
        observed={'ok': res['ok'], 'error': res.get('error'), 'unchanged': p.read_bytes() == before})
R.check('save: no temp files (after failure)', temp_files(p) == [], observed=temp_files(p), expected=[])

res = api.save(create_backup=False)
fresh = Api()
R.check('save: round trip', res['ok'] and fresh.load_save(str(p))['ok'] and fresh.get_state()['money'] == '111',
        observed={'save_ok': res['ok'], 'money_on_disk': fresh.get_state().get('money')})
R.check('save: no temp files (after success)', temp_files(p) == [], observed=temp_files(p), expected=[])

# Balatro holding the file open: Windows refuses the replace until it's closed.
p2 = make_save('locked')
api = Api()
api.load_save(str(p2))
api.apply({'money': {'enabled': True, 'value': 222}})
held = open(p2, 'rb')
threading.Timer(0.25, held.close).start()
t0 = time.monotonic()
res = api.save(create_backup=False)
R.check('save: retries a locked replace', res['ok'] and b'["dollars"]=222' in text_of(p2),
        observed={'ok': res['ok'], 'error': res.get('error'), 'seconds': round(time.monotonic() - t0, 2)})

if sys.platform == 'win32':
    before = p2.read_bytes()
    api.apply({'money': {'enabled': True, 'value': 333}})
    held = open(p2, 'rb')
    try:
        res = api.save(create_backup=False)
    finally:
        held.close()
    R.check('save: gives up on a file that stays locked, original intact',
            not res['ok'] and p2.read_bytes() == before and temp_files(p2) == [],
            observed={'ok': res['ok'], 'error': res.get('error'), 'temp_files': temp_files(p2)})
else:
    R.skip('save: gives up on a file that stays locked', 'open files only block replace on Windows')

# A save reached through a symlink: write the target, keep the link.
real = make_save('link-target')
link_dir = TMP / 'link'
link_dir.mkdir()
link = link_dir / 'save.jkr'
try:
    os.symlink(real, link)
    can_link = True
except OSError as e:  # Windows needs Developer Mode or admin for symlinks
    can_link, link_error = False, repr(e)
if can_link:
    _, res = edit_money(link, 777)
    R.check('save: symlink kept', res['ok'] and link.is_symlink() and b'["dollars"]=777' in text_of(real)
            and temp_files(real) == [] and temp_files(link) == [],
            observed={'ok': res['ok'], 'still_link': link.is_symlink(), 'target_money_777': b'["dollars"]=777' in text_of(real)})
else:
    R.skip('save: symlink kept', f'cannot create symlinks here ({link_error})')

if sys.platform != 'win32':
    pm = make_save('perms')
    os.chmod(pm, 0o644)
    _, res = edit_money(pm, 888)
    mode = oct(os.stat(pm).st_mode & 0o777)
    R.check('save: permissions kept', res['ok'] and mode == '0o644', observed=mode, expected='0o644')
else:
    R.skip('save: permissions kept', 'POSIX permission bits; Windows files have none to lose')

# ---- 5. encodings ----

uni_name = '"小丑 Jöker"'.encode('utf-8')
p3 = make_save('utf8', uni_name)
api = Api()
res = api.load_save(str(p3))
names = [j['name'] for j in api.get_jokers().get('jokers', [])] if res['ok'] else []
R.check('save: utf-8 loads', res['ok'] and names == ['小丑 Jöker'], observed={'ok': res['ok'], 'error': res.get('error'), 'names': names})
_, res = edit_money(p3, 444)
raw = text_of(p3)
R.check('save: utf-8 round trip', res['ok'] and raw.count(uni_name) == 2 and b'["dollars"]=444' in raw,
        observed={'ok': res['ok'], 'name_bytes_kept': raw.count(uni_name)})

latin = b'"J\xe9ker \xff"'  # not valid UTF-8
p4 = make_save('latin1', latin)
_, res = edit_money(p4, 555)
raw = text_of(p4)
R.check('save: non-utf8 round trip', res['ok'] and raw.count(latin) == 2 and b'["dollars"]=555' in raw,
        observed={'ok': res['ok'], 'error': res.get('error'), 'bytes_kept': raw.count(latin)})

# ---- 9. backup pruning ----

p5 = make_save('backups')
folder = p5.parent
old = [f'save.jkr2020-01-{d:02d}T120000.000001.bak' for d in range(1, 13)]
for name in old:
    (folder / name).write_bytes(b'old backup')
keep_files = ['save.jkr.bak', 'notes.txt', 'other.jkr2020-01-01T120000.000001.bak', 'save.jkr2020-01-01T120000.bak.keep']
for name in keep_files:
    (folder / name).write_bytes(b'user file')
_, res = edit_money(p5, 666, backup=True)
backups = sorted(f.name for f in folder.iterdir() if f.name.startswith('save.jkr20') and f.name.endswith('.bak'))
newest = [b for b in backups if not b.startswith('save.jkr2020-')]
R.check('save: backups pruned', res['ok'] and len(backups) == 10 and len(newest) == 1 and backups[:9] == old[-9:],
        observed={'count': len(backups), 'kept_old': backups[:9], 'new': newest}, expected='10 = 9 newest old + 1 new')
R.check('save: prune leaves other files', all((folder / n).is_file() for n in keep_files),
        observed={n: (folder / n).is_file() for n in keep_files})

# ---- 10. unreadable folder ----

if sys.platform == 'win32':
    locked_base = TMP / 'bases' / 'locked'
    open_base = TMP / 'bases' / 'open'
    for base in (locked_base, open_base):
        (base / '1').mkdir(parents=True)
        shutil.copy(make_save('seed'), base / '1' / 'save.jkr')
    user = getpass.getuser()
    subprocess.run(['icacls', str(locked_base), '/deny', f'{user}:(RD)'], capture_output=True, check=True)
    real_bases = paths.candidate_bases
    paths.candidate_bases = lambda: [locked_base, open_base]
    try:
        try:
            found = [str(s) for s in paths.find_saves()]
            err = None
        except Exception as e:  # the bug: one unreadable folder threw for all of them
            found, err = [], repr(e)
        detected = Api().detect_saves()
    finally:
        paths.candidate_bases = real_bases
        subprocess.run(['icacls', str(locked_base), '/remove:d', user], capture_output=True)
    want = str((open_base / '1' / 'save.jkr').resolve())
    R.check('paths: unreadable folder skipped', err is None and found == [want] and len(detected) == 1,
            observed={'found': found, 'error': err}, expected=[want])
else:
    R.skip('paths: unreadable folder skipped', 'uses icacls')

shutil.rmtree(TMP, ignore_errors=True)
R.finish()

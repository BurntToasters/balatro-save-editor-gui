# E2E: the real app window (FAILURE_MODES.md 2, 4, 5, 8). Needs a display.
# Run: npm run e2e (or directly with the venv python). Report + screenshots: e2e-artifacts/gui*
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

CONFIG_DIR = Path(tempfile.mkdtemp(prefix='bse-e2e-cfg-'))
os.environ['BALATRO_EDITOR_CONFIG_DIR'] = str(CONFIG_DIR)
(CONFIG_DIR / 'settings.json').write_text('{"check_updates": false}', encoding='utf-8')

import webview  # noqa: E402
from report import Report, sha256  # noqa: E402

from app import api as api_module  # noqa: E402
from app import paths  # noqa: E402
from app.api import Api  # noqa: E402
from app.editor import BalatroSaveFile, JokerEditor  # noqa: E402
from app.main import index_html  # noqa: E402

R = Report('gui')
TMP = Path(tempfile.mkdtemp(prefix='bse-e2e-gui-'))
X, Y, W, H = 40, 40, 1000, 720
TITLE = 'BSE E2E main'
TITLE_CLEAN = 'BSE E2E clean close'
TITLE_YES = 'BSE E2E yes close'

CARD = '[{n}]={{["ability"]={{["name"]={name},}},["label"]={name},["sell_cost"]=3,["save_fields"]={{["center"]="j_joker",}},}},'


def run_text(names):
    cards = ''.join(CARD.format(n=i + 1, name=f'"{n}"') for i, n in enumerate(names))
    return (
        'return{["GAME"]={["dollars"]=4,["chips"]=0,["chips_text"]="0",'
        '["hands"]={["High Card"]={["mult"]=1,["played"]=0,},},},["BLIND"]={["chips"]=300,},'
        '["cardAreas"]={["jokers"]={["config"]={["card_limit"]=5,["temp_limit"]=5,},["cards"]={' + cards + '},},'
        '["consumeables"]={["config"]={["card_limit"]=2,["temp_limit"]=2,},["cards"]={},},},}'
    )


def make_save(folder, names, tweak=lambda t: t):
    path = TMP / folder / 'save.jkr'
    path.parent.mkdir(parents=True)
    path.write_bytes(BalatroSaveFile.compress(tweak(run_text(names)).encode('utf-8')))
    return path


# The run's perishable length is 7; J4 already has a half-used tally of 2.
main_save = make_save('1', ['J1', 'J2', 'J3', 'J4'], lambda t: t.replace(
    '["dollars"]=4,', '["dollars"]=4,["perishable_rounds"]=7,').replace(
    '["name"]="J4",}', '["name"]="J4",["perish_tally"]=2,}'))
uni_save = make_save('2', ['小丑 Jöker'])
R.input('main_save_sha256', sha256(main_save))
R.input('unicode_save_sha256', sha256(uni_save))


def disk_state(path):
    bsf = BalatroSaveFile(str(path))
    return {'dollars': str(bsf['GAME']['dollars']), 'jokers': [j['name'] for j in JokerEditor(bsf).list_jokers()]}


# Native dialogs can't be clicked from here; record them and answer as the test says.
# With hold=True a call blocks until release(), like a real modal dialog waiting on the user
# (and like pywebview's macOS/GTK dialog, which waits on the GUI thread).
class Dialogs:
    def __init__(self):
        self.calls = []
        self.answer = False
        self.hold = False
        self._gate = threading.Event()

    def __call__(self, title, message):
        self.calls.append(title)
        if self.hold:
            self._gate.wait(30)
            self._gate.clear()
        return self.answer

    def release(self, answer):
        self.answer = answer
        self._gate.set()


def responsive(w, timeout=3.0):
    # True if the window's GUI thread still runs page code (evaluate_js blocks when it's stuck).
    out = []
    t = threading.Thread(target=lambda: out.append(w.evaluate_js('1+1')), daemon=True)
    t.start()
    t.join(timeout)
    return out == [2]


def hwnd(title):
    return ctypes.windll.user32.FindWindowW(None, title)


def user_close(title):
    # What the title-bar X / Alt+F4 sends.
    ctypes.windll.user32.PostMessageW(hwnd(title), 0x0010, 0, 0)  # WM_CLOSE


def js(w, code):
    return w.evaluate_js(code)


def rows(w):
    return js(w, "[...document.querySelectorAll('#joker-list .joker-name b')].map(b=>b.textContent)")


def click(w, selector):
    js(w, f"document.querySelector({selector!r}).click();'go'")


def status(w):
    return js(w, "document.getElementById('status').textContent")


def shot(name):
    R.screenshot(name, X, Y, W, H)



def driver():
    w = main_win
    time.sleep(3)
    W_in, H_in = js(w, 'window.innerWidth'), js(w, 'window.innerHeight')
    global W, H
    W, H = int(W_in), int(H_in)

    # ---- 4. closing a window with no edits doesn't ask ----
    clean_win = webview.create_window(TITLE_CLEAN, url=index_html(), js_api=clean_api, width=700, height=500, x=900, y=60)
    clean_api._window = clean_win
    clean_win.events.closing += clean_api.on_closing
    clean_win.create_confirmation_dialog = clean_dialogs
    time.sleep(3)
    user_close(TITLE_CLEAN)
    time.sleep(1.5)
    R.check('gui: close quiet when clean', clean_dialogs.calls == [] and hwnd(TITLE_CLEAN) == 0,
            observed={'dialogs': clean_dialogs.calls, 'window_still_open': hwnd(TITLE_CLEAN) != 0})

    # ---- 4. Yes on the close prompt really closes ----
    yes_win = webview.create_window(TITLE_YES, url=index_html(), js_api=yes_api, width=700, height=500, x=900, y=60)
    yes_api._window = yes_win
    yes_win.events.closing += yes_api.on_closing
    yes_win.create_confirmation_dialog = yes_dialogs
    time.sleep(3)
    js(yes_win, "const m=document.getElementById('val-money');m.value='9';m.dispatchEvent(new Event('input'));'go'")
    time.sleep(0.5)
    yes_dialogs.answer = True
    user_close(TITLE_YES)
    time.sleep(2.0)
    R.check('gui: yes on the close prompt closes', yes_dialogs.calls == ['Discard changes?'] and hwnd(TITLE_YES) == 0,
            observed={'dialogs': yes_dialogs.calls, 'window_still_open': hwnd(TITLE_YES) != 0})

    # ---- 2. joker actions race ----
    start = rows(w)
    js(w, "const b=document.querySelector('#joker-list .joker .quiet.danger');b.click();b.click();'go'")
    time.sleep(1.2)
    after = rows(w)
    R.check('gui: double delete', after == start[1:], observed=after, expected=start[1:])

    js(w, "const b=document.querySelector('#joker-list .joker .quiet:not(.danger)');b.click();b.click();'go'")
    time.sleep(1.2)
    dup = rows(w)
    R.check('gui: double duplicate', len(dup) == len(after) + 1, observed=dup)

    js(w, "ioBusy++;document.querySelector('#joker-list .joker .quiet.danger').click();'go'")
    time.sleep(0.8)
    busy_rows = rows(w)
    js(w, "ioBusy--;'go'")
    R.check('gui: joker action ignored while busy', busy_rows == dup, observed=busy_rows, expected=dup)

    js(w, "window.__r=null;jokerAction(()=>Promise.reject(new Error('injected'))).then(v=>window.__r=v);'go'")
    time.sleep(0.6)
    failed = js(w, 'window.__r')
    busy_after = js(w, 'ioBusy')
    click(w, '#joker-list .joker .quiet.danger')
    time.sleep(1.0)
    recovered = rows(w)
    R.check('gui: joker buttons recover', failed is False and busy_after == 0 and len(recovered) == len(dup) - 1,
            observed={'result': failed, 'ioBusy': busy_after, 'rows': recovered})

    # ---- 8. empty / invalid number fields ----
    disk_before = disk_state(main_save)
    js(w, "const m=document.getElementById('val-money');m.value='';m.dispatchEvent(new Event('input'));"
          "document.getElementById('en-money').checked=true;refreshDirty();'go'")
    click(w, '#save')
    time.sleep(1.0)
    msg = status(w)
    shot('empty-money-blocked')
    R.check('gui: empty money blocks save', 'Money needs a whole number' in msg and disk_state(main_save) == disk_before
            and js(w, "document.activeElement.id") == 'val-money',
            observed={'status': msg, 'disk_unchanged': disk_state(main_save) == disk_before})

    js(w, "const s=document.getElementById('val-jokers');s.value='-3';s.dispatchEvent(new Event('input'));"
          "const m=document.getElementById('val-money');m.value='50';'go'")
    click(w, '#save')
    time.sleep(1.0)
    msg = status(w)
    R.check('gui: negative slot count blocks save', 'Joker slots needs a whole number of 0' in msg and disk_state(main_save) == disk_before,
            observed=msg)
    js(w, "document.getElementById('val-jokers').value='20';document.getElementById('en-limits').checked=false;"
          "document.getElementById('en-money').checked=false;refreshDirty();'go'")

    first_sell = "document.querySelector('#joker-list .joker input[type=number]')"
    old_sell = js(w, f'{first_sell}.value')
    js(w, f"const s={first_sell};s.value='';s.dispatchEvent(new Event('change'));'go'")
    time.sleep(0.8)
    R.check('gui: empty sell reverts', js(w, f'{first_sell}.value') == old_sell and 'Sell value needs' in status(w),
            observed={'value': js(w, f'{first_sell}.value'), 'old': old_sell, 'status': status(w)})

    # ---- 2b. perishable sticker writes a tally ----
    def perishable_box(name):
        return ("[...document.querySelectorAll('#joker-list .joker')].find(r=>r.querySelector('.joker-name b').textContent==="
                f"{name!r}).querySelectorAll('.stickers input')[1]")
    js(w, f"{perishable_box('J2')}.click();'go'")
    time.sleep(0.8)
    js(w, f"{perishable_box('J4')}.click();'go'")
    time.sleep(0.8)
    click(w, '#save')
    time.sleep(1.5)
    bsf = BalatroSaveFile(str(main_save))
    tallies = {}
    for card in bsf['cardAreas']['jokers']['cards']:
        ability = card['ability']
        tallies[str(ability['name']).strip('"')] = (str(ability['perishable']) if 'perishable' in ability else None,
                                                   str(ability['perish_tally']) if 'perish_tally' in ability else None)
    R.check('gui: perishable gets a tally', tallies.get('J2') == ('true', '7'), observed=tallies, expected={'J2': ('true', '7')})
    R.check('gui: existing tally kept', tallies.get('J4') == ('true', '2'), observed=tallies, expected={'J4': ('true', '2')})

    # ---- 5. utf-8 save in the window ----
    dialogs.answer = True  # discard the joker edits above when switching profile
    js(w, f"const p=document.getElementById('profile');p.value={str(uni_save.resolve())!r};p.dispatchEvent(new Event('change'));'go'")
    time.sleep(2.0)
    uni_rows = rows(w)
    shot('utf8-save-loaded')
    R.check('gui: utf-8 save shows its text', uni_rows == ['小丑 Jöker'], observed=uni_rows)
    dialogs.calls.clear()

    # ---- 4. closing with unsaved edits asks; No keeps everything ----
    js(w, "const m=document.getElementById('val-money');m.value='77';m.dispatchEvent(new Event('input'));'go'")
    time.sleep(0.5)
    dialogs.hold = True
    user_close(TITLE)
    time.sleep(1.0)
    alive = responsive(w)
    R.check('gui: close handler returns without waiting', alive and dialogs.calls == ['Discard changes?'],
            observed={'window_responsive_while_asking': alive, 'dialogs': list(dialogs.calls)})
    user_close(TITLE)
    time.sleep(1.0)
    R.check('gui: second close while asking is ignored', dialogs.calls == ['Discard changes?'], observed=list(dialogs.calls))
    dialogs.hold = False
    dialogs.release(False)
    time.sleep(1.0)
    still_open = hwnd(TITLE) != 0
    R.check('gui: close asks when dirty', still_open
            and js(w, "document.getElementById('val-money').value") == '77'
            and js(w, "!document.getElementById('dirty').hidden"),
            observed={'dialogs': list(dialogs.calls), 'window_still_open': still_open})

    # ---- 4. Reset settings -> Restart already asked; closing mustn't ask again ----
    dialogs.calls.clear()
    dialogs.answer = True
    launched.clear()
    click(w, '#settings-btn')
    time.sleep(0.4)
    click(w, '#settings-reset')  # the window closes itself; checked after webview.start returns


launched = []


class NoLaunch:
    def __init__(self, argv, **kwargs):
        launched.append(argv)


# restart() would start a second copy of the app; swap Popen for the api module only.
api_module.subprocess = types.SimpleNamespace(
    Popen=NoLaunch,
    DETACHED_PROCESS=getattr(subprocess, 'DETACHED_PROCESS', 0),
    CREATE_NEW_PROCESS_GROUP=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0),
)

paths.find_saves = lambda: [main_save.resolve(), uni_save.resolve()]
api = Api()
dialogs = Dialogs()
main_win = webview.create_window(TITLE, url=index_html(), js_api=api, width=W, height=H, x=X, y=Y, frameless=True, on_top=True)
api._window = main_win
main_win.events.closing += api.on_closing
main_win.create_confirmation_dialog = dialogs
clean_api = Api()
clean_dialogs = Dialogs()
yes_api = Api()
yes_dialogs = Dialogs()

webview.start(driver)

time.sleep(0.5)
restart = {'dialogs': list(dialogs.calls), 'launched': list(launched)}
# Reset asks twice in the page (reset? restart?); the close itself must not add a third.
R.check('gui: restart does not double-ask', restart.get('dialogs') == ['Reset settings?', 'Restart now?'] and len(restart.get('launched', [])) == 1
        and hwnd(TITLE) == 0, observed=restart)
R.check('gui: unsaved edits were never written', disk_state(uni_save)['dollars'] == '4', observed=disk_state(uni_save))
shutil.rmtree(TMP, ignore_errors=True)
shutil.rmtree(CONFIG_DIR, ignore_errors=True)
R.finish()

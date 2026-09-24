# Dev-mode GUI smoke test: opens the real window against a temp save,
# drives the UI via evaluate_js, and verifies the edit reaches disk.
# Not part of the pytest suite (needs a display). Run: npm run smoke:gui (also part of npm run e2e).
# Report: e2e-artifacts/smoke.json
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'e2e'))
# Keep the real per-user settings.json out of it.
CONFIG_DIR = Path(tempfile.mkdtemp())
os.environ['BALATRO_EDITOR_CONFIG_DIR'] = str(CONFIG_DIR)
# No network update check (and no native "update available" dialog) during the smoke run.
(CONFIG_DIR / 'settings.json').write_text('{"check_updates": false}', encoding='utf-8')

import webview  # noqa: E402
from report import Report  # noqa: E402

from app import paths  # noqa: E402
from app.api import Api  # noqa: E402
from app.editor import BalatroSaveFile, JokerEditor  # noqa: E402
from app.main import index_html  # noqa: E402

SAMPLE = (
    'return{'
    '["GAME"]={["dollars"]=4,["chips"]=0,["chips_text"]="0",'
    '["hands"]={["High Card"]={["mult"]=1,["played"]=0,},["Pair"]={["mult"]=2,["played"]=0,},},},'
    '["BLIND"]={["chips"]=300,},'
    '["cardAreas"]={'
    '["jokers"]={["config"]={["card_limit"]=5,["temp_limit"]=5,},'
    '["cards"]={[1]={["ability"]={["eternal"]=true,["name"]="Joker",},},[2]={["ability"]={["name"]="Joker",},},},},'
    '["consumeables"]={["config"]={["card_limit"]=2,["temp_limit"]=2,},["cards"]={},},'
    '},}'
)

tmp = Path(tempfile.mkdtemp())
save = tmp / '1' / 'save.jkr'
save.parent.mkdir(parents=True)
save.write_bytes(BalatroSaveFile.compress(bytes(SAMPLE, 'ascii')))
paths.find_saves = lambda: [save.resolve()]

results = {}
stamp_bump = [0]


def disk():
    bsf = BalatroSaveFile(str(save))
    return {
        'dollars': str(bsf['GAME']['dollars']),
        'jokers': len(list(bsf['cardAreas']['jokers']['cards'])),
        'centers': [j['center'] for j in JokerEditor(bsf).list_jokers()],
    }


def balatro_writes(dollars):
    # Stand-in for Balatro rewriting save.jkr while the editor is open.
    save.write_bytes(BalatroSaveFile.compress(bytes(SAMPLE.replace('["dollars"]=4', f'["dollars"]={dollars}'), 'ascii')))
    stamp_bump[0] += 1
    t = time.time_ns() + stamp_bump[0] * 1_000_000_000
    os.utime(save, ns=(t, t))


def js(window, code):
    return window.evaluate_js(code)


def focus_back(window):
    # Same handler the window's focus event runs when you switch back from Balatro.
    js(window, "window.dispatchEvent(new Event('focus'));'go'")
    time.sleep(1.0)


def set_money(window, value):
    js(window, f"const m=document.getElementById('val-money');m.value='{value}';m.dispatchEvent(new Event('input'));'go'")
    time.sleep(0.3)


def driver(window):
    time.sleep(2.5)
    results['ui_start'] = window.evaluate_js("document.documentElement.dataset.ui")
    window.evaluate_js("document.querySelector('.sidebar [data-ui-choice=flat]').click();'go'")
    time.sleep(0.8)
    results['ui_after'] = window.evaluate_js("document.documentElement.dataset.ui")
    results['money'] = window.evaluate_js("document.getElementById('cur-money').textContent")
    results['eternal'] = window.evaluate_js("document.getElementById('cur-eternal').textContent")
    results['jokers'] = window.evaluate_js("document.querySelectorAll('#joker-list .joker').length")
    # Typing a value auto-enables the preset; a joker edit rides along on the same Save.
    window.evaluate_js(
        "const m=document.getElementById('val-money');m.value='12345';"
        "m.dispatchEvent(new Event('input'));"
        "document.querySelector('#joker-list .joker .quiet.danger').click();'go'"
    )
    time.sleep(1.0)
    # Add a joker through the searchable picker: open, search "gold", Enter, Add.
    window.evaluate_js("document.getElementById('joker-add-select').click();'go'")
    time.sleep(0.4)
    window.evaluate_js(
        "const s=document.getElementById('jpick-search');s.value='gold';"
        "s.dispatchEvent(new Event('input'));"
        "s.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));'go'"
    )
    time.sleep(0.4)
    results['picked'] = window.evaluate_js("document.getElementById('joker-add-select').value")
    window.evaluate_js("document.getElementById('joker-add-btn').click();'go'")
    time.sleep(1.0)
    results['dirty'] = window.evaluate_js("!document.getElementById('dirty').hidden")
    window.evaluate_js("document.getElementById('save').click();'go'")
    time.sleep(2.0)
    results['clean'] = window.evaluate_js("document.getElementById('dirty').hidden")
    results['first'] = disk()

    status = "document.getElementById('status').textContent"
    money = "document.getElementById('cur-money').textContent"
    modal_open = "!document.getElementById('conflict-modal').hidden"
    click = lambda id: js(window, f"document.getElementById('{id}').click();'go'")  # noqa: E731

    # No unsaved edits: coming back to the window picks up Balatro's write quietly.
    balatro_writes(777)
    focus_back(window)
    results['auto'] = (js(window, money), js(window, status))

    # Unsaved edits: focus only warns; Save asks; Cancel leaves disk alone.
    set_money(window, 555)
    balatro_writes(888)
    focus_back(window)
    results['warned'] = (js(window, money), js(window, status))
    click('save')
    time.sleep(0.8)
    results['modal_cancel'] = (js(window, modal_open), js(window, "!document.getElementById('conflict-reload').hidden"))
    click('conflict-cancel')
    time.sleep(0.5)
    results['after_cancel'] = (js(window, modal_open), js(window, status), disk()['dollars'])

    # Overwrite writes our edits over Balatro's version (backed up first).
    click('save')
    time.sleep(0.8)
    click('conflict-overwrite')
    time.sleep(1.5)
    results['after_overwrite'] = (js(window, modal_open), js(window, status), disk()['dollars'], len(list(save.parent.glob('save.jkr*.bak'))))

    # Reload drops our edits and shows Balatro's version.
    set_money(window, 111)
    balatro_writes(999)
    click('save')
    time.sleep(0.8)
    click('conflict-reload')
    time.sleep(1.5)
    results['after_reload'] = (js(window, money), js(window, "document.getElementById('dirty').hidden"), disk()['dollars'])

    # Esc on the dialog is Cancel.
    set_money(window, 222)
    balatro_writes(1000)
    click('save')
    time.sleep(0.8)
    js(window, "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));'go'")
    time.sleep(0.5)
    results['after_esc'] = (js(window, modal_open), disk()['dollars'])
    js(window, "document.getElementById('en-money').checked=false;refreshDirty();'go'")

    # Focus check waits out a load or save in flight (e.g. focus back from the Open… picker).
    js(window, "ioBusy++;'go'")
    balatro_writes(1234)
    focus_back(window)
    results['busy_skip'] = js(window, money)
    js(window, "ioBusy--;'go'")
    focus_back(window)
    results['busy_after'] = js(window, money)

    # Ctrl+S with Settings open: Save changed stacks on top; Cancel closes only it.
    click('settings-btn')
    time.sleep(0.4)
    set_money(window, 333)
    balatro_writes(1500)
    js(window, "document.dispatchEvent(new KeyboardEvent('keydown',{key:'s',ctrlKey:true,bubbles:true}));'go'")
    time.sleep(0.8)
    tab = "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',shiftKey:%s,bubbles:true,cancelable:true}));document.activeElement.id"
    results['stacked'] = (
        js(window, modal_open),
        js(window, "!document.getElementById('settings-modal').hidden"),
        js(window, 'openModalId()'),
        js(window, 'document.activeElement.id'),
        js(window, tab % 'true'),   # Shift+Tab from Cancel wraps to Overwrite
        js(window, tab % 'false'),  # Tab from Overwrite wraps to Cancel
    )
    click('conflict-cancel')
    time.sleep(0.5)
    results['stacked_after'] = (js(window, modal_open), js(window, "!document.getElementById('settings-modal').hidden"), js(window, 'openModalId()'))
    js(window, "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));'go'")
    time.sleep(0.3)
    results['stacked_closed'] = js(window, 'openModalId()')
    js(window, "document.getElementById('en-money').checked=false;refreshDirty();'go'")

    # Run ended: Balatro deletes save.jkr.
    os.remove(save)
    focus_back(window)
    results['removed'] = js(window, status)
    click('reload')
    time.sleep(1.0)
    results['reload_missing'] = js(window, status)
    window.destroy()


api = Api()
window = webview.create_window('Balatro Save Editor (smoke)', url=index_html(), js_api=api, width=900, height=700)
api._window = window
webview.start(driver, window)

first = results.get('first') or {}
dollars = first.get('dollars')
disk_jokers = first.get('jokers')
disk_centers = first.get('centers') or [None]
settings_file = CONFIG_DIR / 'settings.json'
saved_ui = json.loads(settings_file.read_text(encoding='utf-8')).get('ui') if settings_file.is_file() else None
R = Report('smoke')
R.check('smoke: ui starts themed, switches to flat, saved', (results.get('ui_start'), results.get('ui_after'), saved_ui) == ('themed', 'flat', 'flat'),
        observed=[results.get('ui_start'), results.get('ui_after'), saved_ui])
R.check('smoke: loads the save', (results.get('money'), results.get('eternal'), results.get('jokers')) == ('4', '1', 2),
        observed=[results.get('money'), results.get('eternal'), results.get('jokers')])
R.check('smoke: joker picker search picks Golden Joker', results.get('picked') == 'j_golden', observed=results.get('picked'))
R.check('smoke: edits reach disk', results.get('dirty') is True and results.get('clean') is True and dollars == '12345'
        and disk_jokers == 2 and disk_centers[-1] == 'j_golden',
        observed={'dirty': results.get('dirty'), 'clean': results.get('clean'), 'dollars': dollars, 'centers': disk_centers})
expect = {
    'auto': lambda v: v and v[0] == '777' and 'Reloaded' in v[1],
    'warned': lambda v: v and v[0] == '777' and 'Balatro updated' in v[1],
    'modal_cancel': lambda v: v == (True, True),
    'after_cancel': lambda v: v and v[0] is False and v[2] == '888',
    'after_overwrite': lambda v: v and v[0] is False and v[2:] == ('555', 2),
    'after_reload': lambda v: v == ('999', True, '999'),
    'after_esc': lambda v: v == (False, '1000'),
    'busy_skip': lambda v: v == '999',  # unchanged: no reload while busy
    'busy_after': lambda v: v == '1234',
    'stacked': lambda v: v == (True, True, 'conflict-modal', 'conflict-cancel', 'conflict-overwrite', 'conflict-cancel'),
    'stacked_after': lambda v: v == (False, True, 'settings-modal'),
    'stacked_closed': lambda v: v is None,
    'removed': lambda v: 'removed' in (v or ''),
    'reload_missing': lambda v: 'run ends' in (v or ''),
}
for key, ok in expect.items():
    R.check(f'smoke: save changed on disk / {key}', ok(results.get(key)), observed=results.get(key))
R.finish()

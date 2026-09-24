# Dev-mode GUI smoke test: opens the real window against a temp save,
# drives the UI via evaluate_js, and verifies the edit reaches disk.
# Not part of the pytest suite (needs a display). Run: npm run smoke:gui
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Keep the real per-user settings.json out of it.
CONFIG_DIR = Path(tempfile.mkdtemp())
os.environ['BALATRO_EDITOR_CONFIG_DIR'] = str(CONFIG_DIR)
# No network update check (and no native "update available" dialog) during the smoke run.
(CONFIG_DIR / 'settings.json').write_text('{"check_updates": false}', encoding='utf-8')

import webview  # noqa: E402

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
    window.destroy()


api = Api()
window = webview.create_window('Balatro Save Editor (smoke)', url=index_html(), js_api=api, width=900, height=700)
api._window = window
webview.start(driver, window)

bsf = BalatroSaveFile(str(save))
dollars = str(bsf['GAME']['dollars'])
disk_jokers = len(list(bsf['cardAreas']['jokers']['cards']))
disk_centers = [j['center'] for j in JokerEditor(bsf).list_jokers()]
settings_file = CONFIG_DIR / 'settings.json'
saved_ui = json.loads(settings_file.read_text(encoding='utf-8')).get('ui') if settings_file.is_file() else None
print(f"ui start={results.get('ui_start')} after={results.get('ui_after')} settings.json ui={saved_ui}")
print(
    f"loaded money={results.get('money')} eternal={results.get('eternal')} jokers={results.get('jokers')} "
    f"picked={results.get('picked')} dirty={results.get('dirty')} clean={results.get('clean')} "
    f"disk_dollars={dollars} disk_jokers={disk_jokers} centers={disk_centers}"
)

ok = (
    results.get('ui_start') == 'themed'
    and results.get('ui_after') == 'flat'
    and saved_ui == 'flat'
    and results.get('money') == '4'
    and results.get('eternal') == '1'
    and results.get('jokers') == 2
    and results.get('dirty') is True
    and results.get('clean') is True
    and dollars == '12345'
    and results.get('picked') == 'j_golden'
    and disk_jokers == 2
    and disk_centers[-1] == 'j_golden'
)
if not ok:
    print('GUI SMOKE FAILED')
    sys.exit(1)
print('GUI SMOKE OK')

# Dev-mode GUI smoke test: opens the real window against a temp save,
# drives the UI via evaluate_js, and verifies the edit reaches disk.
# Not part of the pytest suite (needs a display). Run: npm run smoke:gui
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import webview  # noqa: E402

from app import paths  # noqa: E402
from app.api import Api  # noqa: E402
from app.editor import BalatroSaveFile  # noqa: E402
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
    results['money'] = window.evaluate_js("document.getElementById('cur-money').textContent")
    results['eternal'] = window.evaluate_js("document.getElementById('cur-eternal').textContent")
    window.evaluate_js(
        "document.getElementById('en-money').checked=true;"
        "document.getElementById('val-money').value='12345';"
        "document.getElementById('save').click();'go'"
    )
    time.sleep(2.0)
    window.destroy()


api = Api()
window = webview.create_window('Balatro Save Editor (smoke)', url=index_html(), js_api=api, width=900, height=700)
api._window = window
webview.start(driver, window)

bsf = BalatroSaveFile(str(save))
dollars = str(bsf['GAME']['dollars'])
print(f"loaded money={results.get('money')} eternal={results.get('eternal')} disk_dollars={dollars}")

ok = results.get('money') == '4' and results.get('eternal') == '1' and dollars == '12345'
if not ok:
    print('GUI SMOKE FAILED')
    sys.exit(1)
print('GUI SMOKE OK')

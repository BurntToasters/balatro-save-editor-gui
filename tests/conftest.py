import pytest

from app.editor import BalatroSaveFile

# Minimal Balatro-style save body exercising all 5 presets.
SAMPLE = (
    'return{'
    '["GAME"]={'
    '["dollars"]=4,'
    '["chips"]=0,'
    '["chips_text"]="0",'
    '["hands"]={'
    '["High Card"]={["mult"]=1,["played"]=0,},'
    '["Pair"]={["mult"]=2,["played"]=0,},'
    '},'
    '},'
    '["BLIND"]={["chips"]=300,},'
    '["cardAreas"]={'
    '["jokers"]={'
    '["config"]={["card_limit"]=5,["temp_limit"]=5,},'
    '["cards"]={'
    '[1]={["ability"]={["eternal"]=true,["name"]="Joker",},},'
    '[2]={["ability"]={["name"]="Joker",},},'
    '},'
    '},'
    '["consumeables"]={'
    '["config"]={["card_limit"]=2,["temp_limit"]=2,},'
    '["cards"]={},'
    '},'
    '},'
    '}'
)


@pytest.fixture
def sample_text():
    return SAMPLE


@pytest.fixture
def sample_save(tmp_path):
    path = tmp_path / 'save.jkr'
    path.write_bytes(BalatroSaveFile.compress(bytes(SAMPLE, 'ascii')))
    return path

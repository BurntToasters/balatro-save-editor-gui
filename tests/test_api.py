from pathlib import Path

from app import paths
from app.api import Api


def test_load_and_initial_state(sample_save):
    api = Api()
    res = api.load_save(str(sample_save))
    assert res['ok'] is True
    st = res['state']
    assert st['loaded'] is True
    assert st['money'] == '4'
    assert st['chips'] == '0'
    assert st['blind_target'] == '300'
    assert st['joker_limit'] == '5'
    assert st['consumable_limit'] == '2'
    assert st['hand_mults'] == [1, 2]
    assert st['eternal_jokers'] == 1


def test_get_state_unloaded():
    assert Api().get_state() == {'loaded': False}


def test_load_missing_file(tmp_path):
    res = Api().load_save(str(tmp_path / 'nope.jkr'))
    assert res['ok'] is False
    assert res['error']


def test_load_default_none(monkeypatch):
    monkeypatch.setattr(paths, 'default_save', lambda: None)
    res = Api().load_save()
    assert res['ok'] is False
    assert 'No Balatro save' in res['error']


def test_apply_all_presets(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    res = api.apply({
        'money': {'enabled': True, 'value': 19999},
        'chips': {'enabled': True},
        'multipliers': {'enabled': True, 'value': 10000},
        'card_limits': {'enabled': True, 'joker_limit': 20, 'consumable_limit': 10},
        'strip_eternal': {'enabled': True},
    })
    assert res['ok'] is True
    st = res['state']
    assert st['money'] == '19999'
    assert st['chips'] == '299'
    assert st['joker_limit'] == '20'
    assert st['consumable_limit'] == '10'
    assert st['hand_mults'] == [10000]
    assert st['eternal_jokers'] == 0


def test_apply_partial_leaves_rest(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    res = api.apply({'money': {'enabled': True, 'value': 500}})
    st = res['state']
    assert st['money'] == '500'
    assert st['joker_limit'] == '5'  # unchanged
    assert st['eternal_jokers'] == 1  # unchanged


def test_apply_disabled_is_noop(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    res = api.apply({'money': {'enabled': False, 'value': 9}})
    assert res['state']['money'] == '4'


def test_apply_invalid_int(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    res = api.apply({'money': {'enabled': True, 'value': 'abc'}})
    assert res['ok'] is False
    assert 'whole number' in res['error']


def test_apply_without_load():
    res = Api().apply({'money': {'enabled': True, 'value': 1}})
    assert res['ok'] is False
    assert 'No save loaded' in res['error']


def test_save_persists_and_revalidates(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    api.apply({'money': {'enabled': True, 'value': 12345}})
    res = api.save(create_backup=False)
    assert res['ok'] is True
    # Fresh load from disk confirms persistence + round-trip validity.
    fresh = Api()
    fresh.load_save(str(sample_save))
    assert fresh.get_state()['money'] == '12345'


def test_save_creates_backup(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    api.apply({'money': {'enabled': True, 'value': 7}})
    api.save(create_backup=True)
    backups = list(Path(sample_save).parent.glob('save.jkr*.bak'))
    assert len(backups) == 1


def test_detect_saves(monkeypatch, tmp_path):
    fake = tmp_path / 'Balatro' / '1' / 'save.jkr'
    monkeypatch.setattr(paths, 'find_saves', lambda: [fake])
    out = Api().detect_saves()
    assert out == [{'path': str(fake), 'label': 'Profile 1'}]

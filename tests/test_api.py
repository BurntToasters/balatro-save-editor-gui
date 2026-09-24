import json
import os
from pathlib import Path

import app as app_pkg
from app import paths, resources
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


def _balatro_writes(path, dollars=999):
    # Simulate Balatro rewriting the file with a different run.
    other = Api()
    other.load_save(str(path))
    other.apply({'money': {'enabled': True, 'value': dollars}})
    assert other.save(create_backup=False)['ok']


def test_load_missing_file_is_friendly(tmp_path):
    res = Api().load_save(str(tmp_path / 'save.jkr'))
    assert res['ok'] is False
    assert 'run ends' in res['error']


def test_save_status_ignores_same_bytes_and_mtime(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    # Balatro rewriting identical bytes (or only touching the file) isn't a change.
    data = Path(sample_save).read_bytes()
    Path(sample_save).write_bytes(data)
    st = os.stat(sample_save)
    os.utime(sample_save, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert api.save_status()['changed'] is False


def test_save_status_sees_change_with_same_mtime(sample_save):
    # exFAT keeps 2-second timestamps: a rewrite can land on the same mtime.
    api = Api()
    api.load_save(str(sample_save))
    st = os.stat(sample_save)
    _balatro_writes(sample_save)
    os.utime(sample_save, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert api.save_status()['changed'] is True


def test_save_status_unloaded():
    assert Api().save_status() == {'loaded': False, 'changed': False, 'missing': False}


def test_save_status_tracks_disk_changes(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    assert api.save_status() == {'loaded': True, 'changed': False, 'missing': False}
    _balatro_writes(sample_save)
    assert api.save_status()['changed'] is True
    api.load_save(str(sample_save))
    assert api.save_status()['changed'] is False
    os.remove(sample_save)
    assert api.save_status() == {'loaded': True, 'changed': True, 'missing': True}


def test_save_refuses_when_changed_on_disk(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    api.apply({'money': {'enabled': True, 'value': 12345}})
    _balatro_writes(sample_save)
    before = Path(sample_save).read_bytes()
    res = api.save(create_backup=True)
    assert res['ok'] is False and res['conflict'] is True and res['missing'] is False
    assert Path(sample_save).read_bytes() == before
    assert not list(Path(sample_save).parent.glob('save.jkr*.bak'))


def test_save_overwrite_after_change(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    api.apply({'money': {'enabled': True, 'value': 12345}})
    _balatro_writes(sample_save)
    res = api.save(create_backup=True, overwrite=True)
    assert res['ok'] is True and res['backed_up'] is True
    assert res['state']['money'] == '12345'
    assert len(list(Path(sample_save).parent.glob('save.jkr*.bak'))) == 1
    # Our own write is the new baseline, not a change by Balatro.
    assert api.save_status()['changed'] is False


def test_save_overwrite_restores_deleted_save(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    os.remove(sample_save)
    res = api.save(create_backup=True, overwrite=True)
    assert res['ok'] is True and res['backed_up'] is False
    assert Path(sample_save).exists()
    assert api.save_status()['changed'] is False


def test_detect_saves(monkeypatch, tmp_path):
    fake = tmp_path / 'Balatro' / '1' / 'save.jkr'
    monkeypatch.setattr(paths, 'find_saves', lambda: [fake])
    out = Api().detect_saves()
    assert out == [{'path': str(fake), 'label': 'Profile 1'}]


def test_open_url_only_allows_http(monkeypatch):
    calls = []
    monkeypatch.setattr('webbrowser.open', lambda u: calls.append(u))
    api = Api()
    assert api.open_url('https://example.com') is True
    assert api.open_url('http://example.com') is True
    assert api.open_url('file:///etc/passwd') is False
    assert api.open_url('javascript:alert(1)') is False
    assert api.open_url(None) is False
    assert calls == ['https://example.com', 'http://example.com']


def test_get_licenses_reads_file(monkeypatch, tmp_path):
    payload = {'app': {'name': 'Balatro Save Editor', 'license': 'MPL-2.0'}, 'entries': [{'name': 'bottle'}]}
    f = tmp_path / 'licenses.json'
    f.write_text(json.dumps(payload), encoding='utf-8')
    monkeypatch.setattr(resources, 'licenses_path', lambda: str(f))
    assert Api().get_licenses() == payload


def test_get_licenses_missing_is_graceful(monkeypatch, tmp_path):
    monkeypatch.setattr(resources, 'licenses_path', lambda: str(tmp_path / 'nope.json'))
    out = Api().get_licenses()
    assert out == {'app': None, 'entries': []}


def test_joker_catalog():
    cat = Api().joker_catalog()
    assert len(cat) == 150
    assert {'key', 'name', 'rarity'} <= set(cat[0])


def test_get_jokers_requires_load():
    assert Api().get_jokers()['ok'] is False


def test_get_jokers_after_load(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    res = api.get_jokers()
    assert res['ok'] is True
    assert len(res['jokers']) == 2


def test_joker_add_and_edition_via_api(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    res = api.joker_add('j_blueprint', 'Blueprint')
    assert res['ok'] is True
    assert len(res['jokers']) == 3
    assert res['jokers'][-1]['center'] == 'j_blueprint'

    res = api.joker_set_edition(0, 'foil')
    assert res['jokers'][0]['edition'] == 'foil'


def test_joker_delete_via_api(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    res = api.joker_delete(0)
    assert len(res['jokers']) == 1


def test_joker_edits_persist_through_save(sample_save):
    api = Api()
    api.load_save(str(sample_save))
    api.joker_add('j_dna', 'DNA')
    assert api.save(create_backup=False)['ok'] is True

    fresh = Api()
    fresh.load_save(str(sample_save))
    jokers = fresh.get_jokers()['jokers']
    assert len(jokers) == 3
    assert jokers[-1]['center'] == 'j_dna'


class FakeWindow:
    def __init__(self, answer=True):
        self.answer = answer
        self.shown = False
        self.asked = None

    def show(self):
        self.shown = True

    def create_confirmation_dialog(self, title, message):
        self.asked = (title, message)
        return self.answer


def test_ui_ready_shows_window():
    win = FakeWindow()
    assert Api(win).ui_ready() is True
    assert win.shown is True
    assert Api().ui_ready() is True


def test_confirm_uses_native_dialog():
    win = FakeWindow(answer=False)
    assert Api(win).confirm('T', 'M') is False
    assert win.asked == ('T', 'M')
    assert Api(FakeWindow(answer=True)).confirm('T', 'M') is True
    assert Api().confirm('T', 'M') is True


def test_app_info(monkeypatch):
    # The version comes from the app package (kept current by npm run sync), not licenses.json.
    monkeypatch.setattr(resources, 'load_licenses', lambda: {'app': None, 'entries': []})
    info = Api(debug=True).app_info()
    assert (info['version'], info['debug']) == (app_pkg.__version__, True)
    assert info['settings'] == {'ui': 'themed', 'backup': True, 'check_updates': True}
    assert info['settings_path'].endswith('settings.json')
    assert Api().app_info()['debug'] is False


def test_set_and_reset_settings(isolated_settings):
    api = Api()
    res = api.set_setting('ui', 'flat')
    assert res == {'ok': True, 'settings': {'ui': 'flat', 'backup': True, 'check_updates': True}}
    assert api.app_info()['settings']['ui'] == 'flat'
    assert (isolated_settings / 'settings.json').is_file()

    bad = api.set_setting('ui', 'neon')
    assert bad['ok'] is False and 'ui' in bad['error']
    assert api.set_setting('nope', 1)['ok'] is False

    assert api.reset_settings() == {'ok': True, 'settings': {'ui': 'themed', 'backup': True, 'check_updates': True}}
    assert not (isolated_settings / 'settings.json').exists()


def test_restart_relaunches_then_closes(monkeypatch):
    launched = {}

    def fake_popen(argv, **kwargs):
        launched.update(argv=argv, kwargs=kwargs)

    monkeypatch.setattr('app.api.subprocess.Popen', fake_popen)
    win = FakeWindow()
    win.destroyed = False
    win.destroy = lambda: setattr(win, 'destroyed', True)

    assert Api(win).restart() == {'ok': True}
    assert launched['argv'][1:] == ['-m', 'app.main']
    assert launched['kwargs']['cwd'] == resources.resource_base()
    assert win.destroyed is True


def test_restart_reports_launch_failure(monkeypatch):
    def boom(argv, **kwargs):
        raise OSError('nope')

    monkeypatch.setattr('app.api.subprocess.Popen', boom)
    win = FakeWindow()
    win.destroy = lambda: (_ for _ in ()).throw(AssertionError('must not close'))
    res = Api(win).restart()
    assert res['ok'] is False and 'nope' in res['error']

import json

import pytest

from app import settings


def test_defaults_when_no_file(isolated_settings):
    assert settings.path() == isolated_settings / 'settings.json'
    assert settings.load() == {'ui': 'themed', 'backup': True, 'check_updates': True}


def test_save_round_trip_and_merge(isolated_settings):
    assert settings.save({'ui': 'flat'}) == {'ui': 'flat', 'backup': True, 'check_updates': True}
    assert settings.save({'backup': False}) == {'ui': 'flat', 'backup': False, 'check_updates': True}
    assert settings.load() == {'ui': 'flat', 'backup': False, 'check_updates': True}
    on_disk = json.loads((isolated_settings / 'settings.json').read_text(encoding='utf-8'))
    assert on_disk == {'ui': 'flat', 'backup': False, 'check_updates': True}
    assert not [p for p in isolated_settings.iterdir() if p.name.startswith('.settings-')]


@pytest.mark.parametrize('changes', [{'ui': 'neon'}, {'backup': 'yes'}, {'extra': 1}, 'ui=flat'])
def test_save_rejects_bad_values(changes):
    with pytest.raises(ValueError):
        settings.save(changes)
    assert settings.load() == settings.DEFAULTS


def test_corrupt_or_odd_file_falls_back(isolated_settings):
    isolated_settings.mkdir(parents=True)
    target = isolated_settings / 'settings.json'
    target.write_text('{not json', encoding='utf-8')
    assert settings.load() == settings.DEFAULTS
    target.write_text('[1, 2]', encoding='utf-8')
    assert settings.load() == settings.DEFAULTS
    target.write_text(json.dumps({'ui': 'neon', 'backup': False, 'junk': 1}), encoding='utf-8')
    assert settings.load() == {'ui': 'themed', 'backup': False, 'check_updates': True}


def test_reset_removes_file(isolated_settings):
    settings.save({'ui': 'flat'})
    assert settings.reset() == settings.DEFAULTS
    assert not settings.path().exists()
    assert settings.reset() == settings.DEFAULTS  # already gone is fine


def test_platform_locations(monkeypatch, tmp_path):
    monkeypatch.delenv('BALATRO_EDITOR_CONFIG_DIR')
    monkeypatch.setattr(settings.Path, 'home', lambda: tmp_path)

    monkeypatch.setattr(settings.sys, 'platform', 'win32')
    monkeypatch.setenv('APPDATA', str(tmp_path / 'Roaming'))
    assert settings.config_dir() == tmp_path / 'Roaming' / 'Balatro Save Editor'

    monkeypatch.setattr(settings.sys, 'platform', 'darwin')
    assert settings.config_dir() == tmp_path / 'Library' / 'Application Support' / 'Balatro Save Editor'

    monkeypatch.setattr(settings.sys, 'platform', 'linux')
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    assert settings.config_dir() == tmp_path / '.config' / 'balatro-save-editor'
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'xdg'))
    assert settings.config_dir() == tmp_path / 'xdg' / 'balatro-save-editor'

from pathlib import Path

from app import paths


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b'x')
    return p


def test_macos_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, 'platform', 'darwin')
    monkeypatch.setattr(paths, '_home', lambda: tmp_path)
    save = _touch(tmp_path / 'Library' / 'Application Support' / 'Balatro' / '1' / 'save.jkr')
    assert paths.default_save() == save.resolve()


def test_windows_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, 'platform', 'win32')
    roaming = tmp_path / 'Roaming'
    monkeypatch.setenv('APPDATA', str(roaming))
    save = _touch(roaming / 'Balatro' / '1' / 'save.jkr')
    assert save.resolve() in paths.find_saves()


def test_linux_proton_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, 'platform', 'linux')
    monkeypatch.setattr(paths, '_home', lambda: tmp_path)
    save = _touch(
        tmp_path / '.steam' / 'steam' / 'steamapps' / 'compatdata' / '2379780'
        / 'pfx' / 'drive_c' / 'users' / 'steamuser' / 'AppData' / 'Roaming'
        / 'Balatro' / '1' / 'save.jkr'
    )
    assert save.resolve() in paths.find_saves()


def test_linux_extra_library_from_vdf(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, 'platform', 'linux')
    monkeypatch.setattr(paths, '_home', lambda: tmp_path)
    steamapps = tmp_path / '.steam' / 'steam' / 'steamapps'
    steamapps.mkdir(parents=True)
    extra = tmp_path / 'games' / 'SteamLibrary'
    (steamapps / 'libraryfolders.vdf').write_text(
        '"libraryfolders"{"0"{"path"\t"%s"}}' % str(extra), encoding='utf-8'
    )
    save = _touch(
        extra / 'steamapps' / 'compatdata' / '2379780' / 'pfx' / 'drive_c'
        / 'users' / 'steamuser' / 'AppData' / 'Roaming' / 'Balatro' / '2' / 'save.jkr'
    )
    assert save.resolve() in paths.find_saves()


def test_multiple_profiles(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, 'platform', 'darwin')
    monkeypatch.setattr(paths, '_home', lambda: tmp_path)
    base = tmp_path / 'Library' / 'Application Support' / 'Balatro'
    s1 = _touch(base / '1' / 'save.jkr')
    s3 = _touch(base / '3' / 'save.jkr')
    found = paths.find_saves()
    assert s1.resolve() in found and s3.resolve() in found


def test_no_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, 'platform', 'darwin')
    monkeypatch.setattr(paths, '_home', lambda: tmp_path)
    assert paths.default_save() is None


def test_profile_label():
    assert paths.profile_label('/x/Balatro/2/save.jkr') == 'Profile 2'
    assert paths.profile_label('/x/Balatro/custom/save.jkr') == 'custom'

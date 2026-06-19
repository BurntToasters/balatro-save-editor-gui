import os
import re
import sys
from pathlib import Path

BALATRO_STEAM_APPID = '2379780'
SAVE_NAME = 'save.jkr'


def _home():
    return Path.home()


def _windows_bases():
    bases = []
    appdata = os.environ.get('APPDATA')
    if appdata:
        bases.append(Path(appdata) / 'Balatro')
    return bases


def _macos_bases():
    return [_home() / 'Library' / 'Application Support' / 'Balatro']


def _steam_roots():
    home = _home()
    return [
        home / '.steam' / 'steam',
        home / '.steam' / 'root',
        home / '.local' / 'share' / 'Steam',
        home / '.var' / 'app' / 'com.valvesoftware.Steam' / '.local' / 'share' / 'Steam',
    ]


def _steam_libraries():
    libs = []
    for root in _steam_roots():
        steamapps = root / 'steamapps'
        if steamapps.is_dir():
            libs.append(steamapps)
        vdf = steamapps / 'libraryfolders.vdf'
        if vdf.is_file():
            try:
                text = vdf.read_text(encoding='utf-8', errors='ignore')
            except OSError:
                continue
            for m in re.finditer(r'"path"\s*"([^"]+)"', text):
                libs.append(Path(m.group(1)) / 'steamapps')
    return _dedupe(libs)


def _linux_bases():
    bases = []
    for steamapps in _steam_libraries():
        bases.append(
            steamapps / 'compatdata' / BALATRO_STEAM_APPID / 'pfx' / 'drive_c'
            / 'users' / 'steamuser' / 'AppData' / 'Roaming' / 'Balatro'
        )
    return bases


def _dedupe(items):
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def candidate_bases():
    if sys.platform.startswith('win'):
        return _windows_bases()
    if sys.platform == 'darwin':
        return _macos_bases()
    return _linux_bases()


def find_saves():
    saves = []
    for base in candidate_bases():
        if not base.is_dir():
            continue
        direct = base / SAVE_NAME
        if direct.is_file():
            saves.append(direct)
        for child in sorted(base.iterdir()):
            if child.is_dir():
                save = child / SAVE_NAME
                if save.is_file():
                    saves.append(save)
    return _dedupe([s.resolve() for s in saves])


def default_save():
    saves = find_saves()
    return saves[0] if saves else None


def profile_label(save_path):
    parent = Path(save_path).parent.name
    return f'Profile {parent}' if parent.isdigit() else (parent or str(save_path))


if __name__ == '__main__':
    found = find_saves()
    if found:
        for s in found:
            print(f'{profile_label(s)}: {s}')
    else:
        print('No Balatro save files found. Checked:')
        for b in candidate_bases():
            print(f'  {b}')

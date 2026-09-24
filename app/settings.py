"""User settings, stored as settings.json in the per-user app-data folder.

pywebview runs in private mode, so browser storage doesn't survive a restart; the
page reads and writes settings through the Api instead.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

APP_DIR_NAME = 'Balatro Save Editor'
FILE_NAME = 'settings.json'
DEFAULTS = {'ui': 'themed', 'backup': True, 'check_updates': True}
UI_MODES = ('themed', 'flat')


def config_dir():
    override = os.environ.get('BALATRO_EDITOR_CONFIG_DIR')
    if override:
        return Path(override)
    if sys.platform.startswith('win'):
        base = os.environ.get('APPDATA')
        return (Path(base) if base else Path.home() / 'AppData' / 'Roaming') / APP_DIR_NAME
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / APP_DIR_NAME
    base = os.environ.get('XDG_CONFIG_HOME')
    return (Path(base) if base else Path.home() / '.config') / 'balatro-save-editor'


def path():
    return config_dir() / FILE_NAME


def _valid(key, value):
    if key == 'ui':
        return value in UI_MODES
    if key in ('backup', 'check_updates'):
        return isinstance(value, bool)
    return False


def load():
    """Defaults overlaid with whatever valid values the file has. Never raises."""
    merged = dict(DEFAULTS)
    try:
        with open(path(), encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return merged
    if isinstance(data, dict):
        for key, value in data.items():
            if key in DEFAULTS and _valid(key, value):
                merged[key] = value
    return merged


def save(changes):
    """Validate and merge `changes` into the stored settings; returns the result."""
    if not isinstance(changes, dict):
        raise ValueError('Settings must be an object')
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise ValueError(f'Unknown setting: {key}')
        if not _valid(key, value):
            raise ValueError(f'Invalid value for {key}: {value!r}')
    merged = {**load(), **changes}
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.settings-', suffix='.json', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2)
            f.write('\n')
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return merged


def reset():
    try:
        path().unlink()
    except FileNotFoundError:
        pass
    return dict(DEFAULTS)

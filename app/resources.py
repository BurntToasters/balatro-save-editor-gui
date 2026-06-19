import json
import os
import sys


def resource_base():
    # PyInstaller unpacks bundled data under _MEIPASS; in dev use the repo root.
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def web_dir():
    return os.path.join(resource_base(), 'web')


def index_html():
    return os.path.join(web_dir(), 'index.html')


def licenses_path():
    return os.path.join(web_dir(), 'licenses.json')


def load_licenses():
    try:
        with open(licenses_path(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'app': None, 'entries': []}

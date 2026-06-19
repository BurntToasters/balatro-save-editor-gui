import os
import sys

import webview

from .api import Api

TITLE = 'Balatro Save Editor'


def resource_base():
    # PyInstaller unpacks bundled data under _MEIPASS; in dev use the repo root.
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def web_dir():
    return os.path.join(resource_base(), 'web')


def index_html():
    return os.path.join(web_dir(), 'index.html')


def main():
    api = Api()
    window = webview.create_window(
        TITLE,
        url=index_html(),
        js_api=api,
        width=920,
        height=720,
        min_size=(720, 560),
    )
    api._window = window
    debug = os.environ.get('BALATRO_EDITOR_DEBUG') == '1'
    webview.start(debug=debug)


if __name__ == '__main__':
    main()

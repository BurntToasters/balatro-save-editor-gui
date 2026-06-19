import os

import webview

from .api import Api
from .resources import index_html

TITLE = 'Balatro Save Editor'


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

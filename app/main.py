import os
import time

import webview

from .api import Api
from .resources import index_html

TITLE = 'Balatro Save Editor'


def main():
    debug = os.environ.get('BALATRO_EDITOR_DEBUG') == '1'
    api = Api(debug=debug)
    window = webview.create_window(
        TITLE,
        url=index_html(),
        js_api=api,
        width=920,
        height=720,
        min_size=(760, 560),
        hidden=True,
        text_select=False,
        zoomable=False,
    )
    api._window = window
    webview.start(func=_show_fallback, args=(window,), debug=debug)


def _show_fallback(window, delay=3.0):
    # The page calls api.ui_ready() once rendered; never leave the window hidden if it doesn't.
    time.sleep(delay)
    window.show()


if __name__ == '__main__':
    main()

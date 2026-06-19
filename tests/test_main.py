import os

from app import main as main_module
from app.api import Api


def test_index_html_exists():
    assert main_module.index_html().endswith(os.path.join('web', 'index.html'))
    assert os.path.isfile(main_module.index_html())


def test_main_wires_window(monkeypatch):
    captured = {}
    fake_window = object()

    def fake_create_window(title, url=None, js_api=None, **kwargs):
        captured.update(title=title, url=url, js_api=js_api, kwargs=kwargs)
        return fake_window

    started = {}

    monkeypatch.setattr(main_module.webview, 'create_window', fake_create_window)
    monkeypatch.setattr(main_module.webview, 'start', lambda **k: started.update(called=True, **k))

    main_module.main()

    assert captured['title'] == main_module.TITLE
    assert captured['url'] == main_module.index_html()
    assert isinstance(captured['js_api'], Api)
    assert captured['js_api']._window is fake_window
    assert captured['kwargs']['min_size'] == (720, 560)
    assert started.get('called') is True


def test_debug_env_enables_debug(monkeypatch):
    monkeypatch.setenv('BALATRO_EDITOR_DEBUG', '1')
    rec = {}
    monkeypatch.setattr(main_module.webview, 'create_window', lambda *a, **k: object())
    monkeypatch.setattr(main_module.webview, 'start', lambda **k: rec.update(k))
    main_module.main()
    assert rec.get('debug') is True

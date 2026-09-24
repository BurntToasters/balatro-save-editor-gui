import os

from app import main as main_module
from app.api import Api


class _Handlers(list):
    def __iadd__(self, handler):
        self.append(handler)
        return self


class FakeWindow:
    def __init__(self):
        self.events = type('Events', (), {})()
        self.events.closing = _Handlers()


def test_index_html_exists():
    assert main_module.index_html().endswith(os.path.join('web', 'index.html'))
    assert os.path.isfile(main_module.index_html())


def test_main_wires_window(monkeypatch):
    captured = {}
    fake_window = FakeWindow()

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
    assert captured['kwargs']['min_size'] == (760, 560)
    assert captured['kwargs']['hidden'] is True
    assert fake_window.events.closing == [captured['js_api'].on_closing]
    assert started.get('called') is True
    assert started['func'] is main_module._show_fallback
    assert started['args'] == (fake_window,)


def test_show_fallback_shows_window():
    shown = []

    class FakeWindow:
        def show(self):
            shown.append(True)

    main_module._show_fallback(FakeWindow(), delay=0)
    assert shown == [True]


def test_debug_env_enables_debug(monkeypatch):
    monkeypatch.setenv('BALATRO_EDITOR_DEBUG', '1')
    rec = {}
    monkeypatch.setattr(main_module.webview, 'create_window', lambda *a, **k: FakeWindow())
    monkeypatch.setattr(main_module.webview, 'start', lambda **k: rec.update(k))
    main_module.main()
    assert rec.get('debug') is True


def test_debug_passed_to_api(monkeypatch):
    monkeypatch.setenv('BALATRO_EDITOR_DEBUG', '1')
    rec = {}
    monkeypatch.setattr(main_module.webview, 'create_window', lambda *a, **k: rec.update(k) or FakeWindow())
    monkeypatch.setattr(main_module.webview, 'start', lambda **k: None)
    main_module.main()
    assert rec['js_api'].app_info()['debug'] is True

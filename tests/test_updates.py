import io
import urllib.error

import pytest

from app import updates
from app.api import Api


@pytest.mark.parametrize('newer, older', [
    ('1.0.1', '1.0.0'),
    ('v1.1.0', '1.0.9'),
    ('2.0.0', '1.99.99'),
    ('1.0.0', '1.0.0-beta.3'),
    ('1.0.0-beta.10', '1.0.0-beta.2'),
    ('1.0.0-rc.1', '1.0.0-beta.9'),
    ('1.0.0-beta.1', '1.0.0-beta'),
])
def test_version_ordering(newer, older):
    assert updates.is_newer(newer, older)
    assert not updates.is_newer(older, newer)


def test_same_version_is_not_newer():
    assert not updates.is_newer('v1.0.0', '1.0.0')
    assert not updates.is_newer('1.0.0+build.7', '1.0.0')


@pytest.mark.parametrize('bad', ['', 'latest', '1.0', 'v1.0.0.0', None])
def test_rejects_non_versions(bad):
    with pytest.raises(ValueError):
        updates.parse_version(bad)


def test_update_available():
    res = updates.check('1.0.0', fetch=lambda: {'tag_name': 'v1.2.0'})
    assert res == {
        'ok': True,
        'current': '1.0.0',
        'latest': '1.2.0',
        'update_available': True,
        'url': 'https://github.com/BurntToasters/balatro-save-editor-gui/releases/latest',
    }


def test_up_to_date_and_ahead():
    assert updates.check('1.0.0', fetch=lambda: {'tag_name': 'v1.0.0'})['update_available'] is False
    # A dev build newer than the last release is not offered a "downgrade".
    assert updates.check('1.1.0', fetch=lambda: {'tag_name': 'v1.0.0'})['update_available'] is False


def _http_error(code):
    def fetch():
        raise urllib.error.HTTPError(updates.LATEST_API, code, 'x', {}, io.BytesIO())
    return fetch


@pytest.mark.parametrize('fetch, message', [
    (_http_error(404), 'No published release'),
    (_http_error(403), 'rate-limiting'),
    (_http_error(500), 'HTTP 500'),
    (lambda: (_ for _ in ()).throw(urllib.error.URLError('offline')), 'Could not reach GitHub'),
    (lambda: (_ for _ in ()).throw(TimeoutError('timed out')), 'Could not reach GitHub'),
    (lambda: (_ for _ in ()).throw(ValueError('bad json')), 'unexpected response'),
    (lambda: {'tag_name': 'nightly'}, 'Unrecognised release tag: nightly'),
    (lambda: {}, 'Unrecognised release tag: (none)'),
])
def test_failures_are_reported_not_raised(fetch, message):
    res = updates.check('1.0.0', fetch=fetch)
    assert res['ok'] is False
    assert message in res['error']


def test_api_uses_the_app_version(monkeypatch):
    monkeypatch.setattr(updates, 'fetch_latest', lambda: {'tag_name': 'v99.0.0'})
    res = Api().check_for_updates()
    assert res['ok'] and res['update_available'] and res['current'] == updates.__version__


def test_ssl_context_falls_back_to_os_bundle(monkeypatch):
    loaded = []

    class EmptyStore:
        def cert_store_stats(self):
            return {'x509_ca': 0}

        def load_verify_locations(self, cafile):
            loaded.append(cafile)

    monkeypatch.setattr(updates.ssl, 'create_default_context', EmptyStore)
    monkeypatch.setattr(updates.os.path, 'isfile', lambda p: p == '/etc/ssl/certs/ca-certificates.crt')
    updates.ssl_context()
    assert loaded == ['/etc/ssl/certs/ca-certificates.crt']


def test_ssl_context_keeps_a_populated_store(monkeypatch):
    class FullStore:
        def cert_store_stats(self):
            return {'x509_ca': 120}

        def load_verify_locations(self, cafile):
            raise AssertionError('should not load a fallback')

    monkeypatch.setattr(updates.ssl, 'create_default_context', FullStore)
    updates.ssl_context()

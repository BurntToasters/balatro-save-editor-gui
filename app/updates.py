"""Rudimentary update check: compare the latest GitHub release tag with this build's version.

Nothing is downloaded or installed; if a newer release exists the page offers to open
the releases/latest page in the browser.
"""
import json
import os
import re
import ssl
import urllib.error
import urllib.request

from . import __version__

REPO = 'BurntToasters/balatro-save-editor-gui'
LATEST_API = f'https://api.github.com/repos/{REPO}/releases/latest'
LATEST_PAGE = f'https://github.com/{REPO}/releases/latest'
TIMEOUT_S = 8

_VERSION = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$')


def parse_version(text):
    m = _VERSION.match(str(text or '').strip())
    if not m:
        raise ValueError(f'Not a version: {text!r}')
    core = tuple(int(x) for x in m.group(1, 2, 3))
    pre = tuple(m.group(4).split('.')) if m.group(4) else ()
    return core, pre


def _pre_key(pre):
    # Semver: a release outranks its pre-releases; numeric identifiers sort below text ones.
    if not pre:
        return (1,)
    return (0, *[(0, int(p), '') if p.isdigit() else (1, 0, p) for p in pre])


def is_newer(candidate, current):
    (c_core, c_pre), (k_core, k_pre) = parse_version(candidate), parse_version(current)
    if c_core != k_core:
        return c_core > k_core
    return _pre_key(c_pre) > _pre_key(k_pre)


# Frozen builds can ship an OpenSSL whose default CA path doesn't exist on the user's
# machine (python.org macOS builds especially); fall back to the OS bundle.
CA_BUNDLES = (
    '/etc/ssl/cert.pem',
    '/etc/ssl/certs/ca-certificates.crt',
    '/etc/pki/tls/certs/ca-bundle.crt',
)


def ssl_context():
    ctx = ssl.create_default_context()
    if not ctx.cert_store_stats().get('x509_ca'):
        for bundle in CA_BUNDLES:
            if os.path.isfile(bundle):
                ctx.load_verify_locations(cafile=bundle)
                break
    return ctx


def fetch_latest():
    req = urllib.request.Request(
        LATEST_API,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': f'balatro-save-editor/{__version__}',
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=ssl_context()) as res:
        return json.load(res)


def check(current=__version__, fetch=None):
    try:
        release = (fetch or fetch_latest)()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {'ok': False, 'error': 'No published release found.'}
        if e.code in (403, 429):
            return {'ok': False, 'error': 'GitHub is rate-limiting update checks. Try again later.'}
        return {'ok': False, 'error': f'GitHub returned HTTP {e.code}.'}
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, 'reason', e)
        return {'ok': False, 'error': f'Could not reach GitHub ({reason}).'}
    except ValueError:
        return {'ok': False, 'error': 'GitHub sent an unexpected response.'}

    tag = str((release or {}).get('tag_name') or '')
    try:
        available = is_newer(tag, current)
    except ValueError:
        return {'ok': False, 'error': f'Unrecognised release tag: {tag or "(none)"}'}
    return {
        'ok': True,
        'current': current,
        'latest': tag.lstrip('v'),
        'update_available': available,
        'url': LATEST_PAGE,
    }

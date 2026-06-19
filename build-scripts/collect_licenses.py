"""Collect third-party license info into web/licenses.json + THIRD_PARTY_NOTICES.txt.

Walks the runtime dependency closure of pywebview (per-platform), plus curated
entries for things bundled but not pip-resolved (CPython, PyInstaller bootloader,
the original upstream save editor). Run via: npm run licenses
"""
import datetime
import importlib.metadata as im
import json
import os
import sys

try:
    from packaging.requirements import Requirement
except Exception:  # packaging is normally present (PyInstaller dep)
    Requirement = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JSON = os.path.join(ROOT, 'web', 'licenses.json')
OUT_TXT = os.path.join(ROOT, 'THIRD_PARTY_NOTICES.txt')
FILE_HINTS = ('license', 'licence', 'copying', 'notice')


def norm(name):
    return name.lower().replace('_', '-')


def runtime_closure(roots):
    seen = {}
    stack = list(roots)
    while stack:
        key = norm(stack.pop())
        if key in seen:
            continue
        try:
            dist = im.distribution(key)
        except im.PackageNotFoundError:
            continue
        seen[key] = dist
        for req in dist.requires or []:
            if Requirement is None:
                continue
            try:
                r = Requirement(req)
            except Exception:
                continue
            # Skip deps gated behind extras or non-matching platform markers.
            if r.marker and not r.marker.evaluate({'extra': ''}):
                continue
            stack.append(r.name)
    return seen


def license_name(dist):
    meta = dist.metadata
    val = meta.get('License-Expression') or meta.get('License')
    if val and val.strip() and len(val) < 64 and '\n' not in val:
        return val.strip()
    for c in meta.get_all('Classifier', []) or []:
        if c.startswith('License ::'):
            return c.split('::')[-1].strip()
    return (val or 'Unknown').strip().splitlines()[0][:64]


def license_text(dist):
    out = []
    for f in dist.files or []:
        rel = str(f).replace(os.sep, '/').lower()
        base = os.path.basename(rel)
        if any(h in base for h in FILE_HINTS) or '/licenses/' in rel:
            try:
                text = f.locate().read_text(encoding='utf-8', errors='replace').strip()
            except Exception:
                continue
            if text and text not in out:
                out.append(text)
    return '\n\n'.join(out)


def im_version(name):
    try:
        return im.version(name)
    except Exception:
        return ''


def read_file(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read().strip()
    except OSError:
        return ''


def app_version():
    try:
        sys.path.insert(0, ROOT)
        import app
        return getattr(app, '__version__', '0.0.0')
    except Exception:
        return '0.0.0'


def curated_entries():
    return [
        {
            'name': 'Python',
            'version': '%d.%d.%d' % sys.version_info[:3],
            'license': 'PSF-2.0',
            'url': 'https://docs.python.org/3/license.html',
            'text': 'The bundled CPython interpreter and standard library are distributed '
                    'under the Python Software Foundation License (PSF-2.0). '
                    'Full text: https://docs.python.org/3/license.html',
        },
        {
            'name': 'PyInstaller (bootloader)',
            'version': im_version('pyinstaller'),
            'license': 'GPL-2.0-or-later WITH Bootloader-exception',
            'url': 'https://github.com/pyinstaller/pyinstaller',
            'text': 'This application is frozen with PyInstaller. Its bootloader is licensed '
                    'under the GPL with an exception permitting use in applications under any '
                    'license. See https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt',
        },
        {
            'name': 'Balatro save editor (original)',
            'version': '',
            'license': 'No upstream license file',
            'url': 'https://github.com/problemsalved/balatro_save_editor',
            'text': 'The save-file parsing and editing logic is derived from '
                    'problemsalved/balatro_save_editor. The upstream repository does not '
                    'include a separate license file. Included with attribution to the '
                    'original author (problemsalved).',
        },
    ]


def write_txt(data):
    lines = [f"{data['app']['name']} {data['app']['version']}",
             f"License: {data['app']['license']}",
             '',
             'This product bundles the following third-party components:',
             '']
    for e in data['entries']:
        head = f"- {e['name']}"
        if e['version']:
            head += f" {e['version']}"
        head += f" ({e['license']})"
        lines.append(head)
        if e['url']:
            lines.append(f"  {e['url']}")
    lines += ['', '=' * 70, '']
    for e in data['entries']:
        if not e['text']:
            continue
        lines.append(f"## {e['name']} {e['version']}".rstrip())
        lines += ['', e['text'], '', '-' * 70, '']
    with open(OUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    closure = runtime_closure(['pywebview'])
    pkg_entries = []
    for key in sorted(closure):
        dist = closure[key]
        pkg_entries.append({
            'name': dist.metadata['Name'],
            'version': dist.version,
            'license': license_name(dist),
            'url': dist.metadata.get('Home-page') or '',
            'text': license_text(dist),
        })

    data = {
        'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'app': {
            'name': 'Balatro Save Editor',
            'version': app_version(),
            'license': 'MPL-2.0',
            'url': 'https://github.com/BurntToasters/balatro-save-editor-gui',
            'text': read_file(os.path.join(ROOT, 'LICENSE')),
        },
        'entries': curated_entries() + pkg_entries,
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    write_txt(data)
    print(f'Wrote {OUT_JSON} ({len(data["entries"])} third-party entries)')
    print(f'Wrote {OUT_TXT}')


if __name__ == '__main__':
    main()

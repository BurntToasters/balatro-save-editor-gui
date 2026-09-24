# E2E: `npm run bump` on a copy of the repo's version files (FAILURE_MODES.md 11b).
# Report: e2e-artifacts/release.json
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report import ROOT, Report, sha256  # noqa: E402

R = Report('release')
FILES = ['package.json', 'package-lock.json', 'app/__init__.py', 'CHANGELOG.md',
         'build-scripts/bump-version.js', 'build-scripts/sync-version.js', 'build-scripts/venv-python.js']


def fresh_copy(version):
    root = Path(tempfile.mkdtemp(prefix='bse-e2e-release-'))
    for rel in FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, root / rel)
    for name in ('package.json', 'package-lock.json'):
        data = json.loads((root / name).read_text(encoding='utf-8'))
        data['version'] = version
        if name == 'package-lock.json':
            data['packages']['']['version'] = version
        (root / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    return root


def bump(root, arg):
    return subprocess.run(['node', str(root / 'build-scripts' / 'bump-version.js'), arg], capture_output=True, text=True)


def versions(root):
    pkg = json.loads((root / 'package.json').read_text(encoding='utf-8'))['version']
    lock = json.loads((root / 'package-lock.json').read_text(encoding='utf-8'))
    init = (root / 'app' / '__init__.py').read_text(encoding='utf-8').strip()
    return {'package': pkg, 'lock': lock['version'], 'lock_root': lock['packages']['']['version'], 'app': init}


roots = []

root = fresh_copy('1.0.1')
roots.append(root)
res = bump(root, 'patch')
v = versions(root)
R.check('release: bump updates lockfile', res.returncode == 0 and v == {
    'package': '1.0.2', 'lock': '1.0.2', 'lock_root': '1.0.2', 'app': '__version__ = "1.0.2"'},
    observed={'code': res.returncode, **v, 'stderr': res.stderr[-200:]})
changelog = (root / 'CHANGELOG.md').read_text(encoding='utf-8')
R.check('release: bump syncs changelog links', '/v1.0.2/Balatro-Save-Editor-1.0.2-win-x64.exe' in changelog,
        observed='v1.0.2 download links present' if '/v1.0.2/' in changelog else 'missing')

res = bump(root, '1.1.0-beta.1')
v = versions(root)
R.check('release: bump to pre-release', res.returncode == 0 and v['package'] == v['lock'] == '1.1.0-beta.1'
        and v['app'] == '__version__ = "1.1.0-beta.1"', observed={'code': res.returncode, **v, 'stderr': res.stderr[-200:]})

results = {}
for kind, want in (('patch', '1.1.0'), ('minor', '1.1.0'), ('major', '2.0.0')):
    r = fresh_copy('1.1.0-beta.1')
    roots.append(r)
    out = bump(r, kind)
    results[kind] = (out.returncode, versions(r)['package'])
R.check('release: bump from pre-release', results == {'patch': (0, '1.1.0'), 'minor': (0, '1.1.0'), 'major': (0, '2.0.0')},
        observed=results)

root = fresh_copy('1.0.1')
roots.append(root)
before = {rel: sha256(root / rel) for rel in FILES[:4]}
bad = [bump(root, arg).returncode for arg in ('banana', '1.2', 'v1.2.3')]
after = {rel: sha256(root / rel) for rel in FILES[:4]}
R.check('release: bad bump changes nothing', all(code != 0 for code in bad) and before == after,
        observed={'codes': bad, 'unchanged': before == after})

for r in roots:
    shutil.rmtree(r, ignore_errors=True)
R.finish()

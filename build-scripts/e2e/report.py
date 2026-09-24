"""E2E report: every check with what was observed, plus screenshots, written to e2e-artifacts/.

Each suite makes one Report, calls check() for every assertion, and finish() at the end, which
writes e2e-artifacts/<suite>.json and exits non-zero if anything failed. The JSON records the
commit, tool versions and input hashes so a run can be compared against a later one.
"""
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = Path(os.environ.get('BSE_E2E_ARTIFACTS') or ROOT / 'e2e-artifacts')


def _git(*args):
    try:
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Report:
    def __init__(self, suite):
        self.suite = suite
        self.dir = ARTIFACTS / suite
        self.dir.mkdir(parents=True, exist_ok=True)
        for old in self.dir.glob('*.png'):
            old.unlink()
        self.data = {
            'suite': suite,
            'started': datetime.datetime.now().isoformat(timespec='seconds'),
            'commit': _git('rev-parse', 'HEAD'),
            'worktree_dirty': bool(_git('status', '--porcelain')),
            'platform': platform.platform(),
            'python': sys.version.split()[0],
            'inputs': {},
            'checks': [],
            'skipped': [],
            'screenshots': [],
        }

    def input(self, name, value):
        self.data['inputs'][name] = value

    def check(self, name, ok, observed=None, expected=None):
        ok = bool(ok)
        self.data['checks'].append({'name': name, 'ok': ok, 'observed': observed, 'expected': expected})
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ('' if ok else f'  observed={observed!r} expected={expected!r}'))
        return ok

    def skip(self, name, reason):
        self.data['skipped'].append({'name': name, 'reason': reason})
        print(f'SKIP  {name}  ({reason})')

    def screenshot(self, name, x, y, w, h):
        """Grab a screen rectangle (Windows) into the suite's artifact folder."""
        out = self.dir / f'{name}.png'
        if sys.platform != 'win32':
            self.skip(f'screenshot {name}', 'screen capture is Windows-only')
            return None
        ps = (
            'Add-Type -AssemblyName System.Drawing;'
            f'$b=New-Object System.Drawing.Bitmap({w},{h});'
            '$g=[System.Drawing.Graphics]::FromImage($b);'
            f'$g.CopyFromScreen({x},{y},0,0,$b.Size);'
            f"$b.Save('{out}')"
        )
        subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=False)
        if out.is_file():
            self.data['screenshots'].append({'name': name, 'file': out.name, 'sha256': sha256(out)})
        return out

    @property
    def failed(self):
        return [c['name'] for c in self.data['checks'] if not c['ok']]

    def finish(self):
        self.data['finished'] = datetime.datetime.now().isoformat(timespec='seconds')
        self.data['passed'] = not self.failed and bool(self.data['checks'])
        path = ARTIFACTS / f'{self.suite}.json'
        path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        total = len(self.data['checks'])
        print(f"{self.suite}: {total - len(self.failed)}/{total} passed, {len(self.data['skipped'])} skipped -> {path}")
        sys.exit(0 if self.data['passed'] else 1)

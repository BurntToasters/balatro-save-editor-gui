# E2E: a real PyInstaller build of a pre-release version, then launch it (FAILURE_MODES.md 11c).
# Builds a copy of the repo in a temp folder; dist/ and build/ in the repo are untouched.
# Takes a minute or two. Report: e2e-artifacts/build.json
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report import ROOT, Report  # noqa: E402

R = Report('build')
VERSION = '1.1.0-beta.1'
TMP = Path(tempfile.mkdtemp(prefix='bse-e2e-build-'))
work = TMP / 'repo'
work.mkdir()
for rel in ('balatro-save-editor.spec', 'run.py', 'package.json'):
    shutil.copy(ROOT / rel, work / rel)
for rel in ('app', 'web', 'icon'):
    shutil.copytree(ROOT / rel, work / rel, ignore=shutil.ignore_patterns('__pycache__'))
pkg = json.loads((work / 'package.json').read_text(encoding='utf-8'))
pkg['version'] = VERSION
(work / 'package.json').write_text(json.dumps(pkg, indent=2) + '\n', encoding='utf-8')
R.input('version', VERSION)

t0 = time.monotonic()
build = subprocess.run(
    [sys.executable, '-m', 'PyInstaller', 'balatro-save-editor.spec', '--noconfirm', '--clean',
     '--workpath', str(TMP / 'build'), '--distpath', str(TMP / 'dist')],
    cwd=work, capture_output=True, text=True,
)
if sys.platform == 'win32':
    exe = TMP / 'dist' / 'balatro-save-editor' / 'balatro-save-editor.exe'
elif sys.platform == 'darwin':
    exe = TMP / 'dist' / 'Balatro Save Editor.app' / 'Contents' / 'MacOS' / 'balatro-save-editor'
else:
    exe = TMP / 'dist' / 'balatro-save-editor' / 'balatro-save-editor'
built = R.check('build: pre-release builds', build.returncode == 0 and exe.is_file(),
                observed={'code': build.returncode, 'seconds': round(time.monotonic() - t0), 'tail': build.stderr[-600:]})

if built and sys.platform == 'win32':
    ps = f"$v=(Get-Item '{exe}').VersionInfo; \"$($v.FileVersion)|$($v.ProductVersion)|$($v.FileMajorPart).$($v.FileMinorPart).$($v.FileBuildPart)\""
    info = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True).stdout.strip()
    R.check('build: exe version info', info == f'{VERSION}|{VERSION}|1.1.0', observed=info, expected=f'{VERSION}|{VERSION}|1.1.0')
elif built:
    R.skip('build: exe version info', 'Windows version resource only')

spec = (ROOT / 'balatro-save-editor.spec').read_text(encoding='utf-8')
R.check('build: mac bundle version', "'CFBundleShortVersionString': APP_VERSION_CORE" in spec
        and "'CFBundleVersion': APP_VERSION_CORE" in spec, observed='bundle versions use the numeric core')

if built:
    # The built app has to start and stay up (own settings folder, no update check, no saves).
    cfg = TMP / 'cfg'
    cfg.mkdir()
    (cfg / 'settings.json').write_text('{"check_updates": false}', encoding='utf-8')
    env = {**os.environ, 'BALATRO_EDITOR_CONFIG_DIR': str(cfg), 'APPDATA': str(TMP / 'appdata'), 'HOME': str(TMP / 'home')}
    proc = subprocess.Popen([str(exe)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(8)
    alive = proc.poll() is None
    proc.kill()
    out = proc.communicate()[0].decode(errors='replace')[-400:]
    R.check('build: built app starts', alive, observed={'running_after_8s': alive, 'output': out})

shutil.rmtree(TMP, ignore_errors=True)
R.finish()

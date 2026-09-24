# E2E: build the NSIS installer from a fake app folder and really install, upgrade and uninstall
# it (FAILURE_MODES.md 1, 6, 7). Windows only. Uses a user-level build so no admin is needed.
# NSIS: makensis on PATH, or MAKENSIS=<path to makensis.exe>. Report: e2e-artifacts/installer.json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report import ROOT, Report, sha256  # noqa: E402

R = Report('installer')
# Its own name, so the run never touches a real install's shortcuts or registry keys.
APP = 'Balatro Save Editor E2E'
EXE = 'balatro-save-editor.exe'


def makensis():
    found = os.environ.get('MAKENSIS') or shutil.which('makensis')
    return found if found and Path(found).is_file() else None


if sys.platform != 'win32' or not makensis():
    R.skip('installer suite', 'needs Windows and NSIS (set MAKENSIS to makensis.exe)')
    R.check('installer: suite ran', False, observed='skipped', expected='NSIS available')
    R.finish()

TMP = Path(tempfile.mkdtemp(prefix='bse-e2e-nsis-'))
R.input('makensis', makensis())
R.input('makensis_version', subprocess.run([makensis(), '-VERSION'], capture_output=True, text=True).stdout.strip())

# A fake app build: ping.exe stands in for the app exe, since a running copy has to lock it.
src = TMP / 'src'
(src / '_internal').mkdir(parents=True)
shutil.copy(Path(os.environ['SystemRoot']) / 'System32' / 'PING.EXE', src / EXE)
(src / '_internal' / 'lib-v2.txt').write_text('new version', encoding='utf-8')
setup = TMP / 'setup.exe'

build = subprocess.run(
    ['node', str(ROOT / 'build-scripts' / 'installer-nsis.js'), '--source', str(src), '--out', str(setup), '--e2e-user-level', '--app-name', APP],
    env={**os.environ, 'MAKENSIS': makensis()}, capture_output=True, text=True,
)
if not R.check('installer: builds', build.returncode == 0 and setup.is_file(),
               observed={'code': build.returncode, 'tail': (build.stdout + build.stderr)[-800:]}):
    R.finish()
R.input('setup_sha256', sha256(setup))


def install(target):
    # /D must be last and unquoted (NSIS rule); temp paths here have no spaces.
    return subprocess.run(f'"{setup}" /S /D={target}', capture_output=True).returncode


def uninstall(folder, timeout=30):
    # The uninstaller copies itself to %TEMP% and returns at once; wait for it to finish.
    subprocess.run(f'"{folder / "Uninstall.exe"}" /S', capture_output=True)
    end = time.monotonic() + timeout
    while time.monotonic() < end and (folder / 'Uninstall.exe').exists():
        time.sleep(0.3)
    time.sleep(0.5)


def listing(folder):
    return sorted(str(p.relative_to(folder)) for p in folder.rglob('*')) if folder.exists() else None


def shell_folder(name):
    ps = f"[Environment]::GetFolderPath('{name}')"
    return Path(subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True).stdout.strip())


# 1.0.0-style per-user shortcuts, which an upgrade has to clean up.
user_links = [shell_folder('Programs') / f'{APP}.lnk', shell_folder('DesktopDirectory') / f'{APP}.lnk']
for link in user_links:
    link.write_bytes(b'stand-in for a 1.0.0 shortcut')

# ---- 1. typed an existing folder: install goes into its own subfolder ----
games = TMP / 'Games'
games.mkdir()
(games / 'keep.txt').write_text('user data', encoding='utf-8')
(games / 'OtherGame').mkdir()
(games / 'OtherGame' / 'save.dat').write_text('other game', encoding='utf-8')
code = install(games)
app_dir = games / APP
R.check('installer: forces dedicated folder', code == 0 and (app_dir / EXE).is_file() and not (games / EXE).exists()
        and not (games / '_internal').exists(), observed={'code': code, 'games': listing(games)})

R.check('installer: removes 1.0.0 per-user shortcuts', not any(link.exists() for link in user_links),
        observed={str(link): link.exists() for link in user_links})
for link in user_links:
    link.unlink(missing_ok=True)

# ---- 7. upgrade removes the old version's files, keeps the user's ----
(app_dir / '_internal' / 'stale-v1.txt').write_text('old version', encoding='utf-8')
(app_dir / 'notes.txt').write_text('user notes in the app folder', encoding='utf-8')
code = install(games)
R.check('installer: upgrade drops stale files', code == 0 and not (app_dir / '_internal' / 'stale-v1.txt').exists()
        and (app_dir / '_internal' / 'lib-v2.txt').is_file() and (app_dir / 'notes.txt').is_file(),
        observed={'code': code, 'app_dir': listing(app_dir)})

# ---- 7. a running copy stops the install ----
exe_hash = sha256(app_dir / EXE)
(app_dir / '_internal' / 'marker.txt').write_text('must survive a refused install', encoding='utf-8')
running = subprocess.Popen([str(app_dir / EXE), '-n', '60', '127.0.0.1'], stdout=subprocess.DEVNULL)
time.sleep(1.0)
try:
    code = install(games)
    survived = (app_dir / '_internal' / 'marker.txt').is_file()
finally:
    running.kill()
    running.wait()
R.check('installer: refuses while app runs', code != 0 and survived and sha256(app_dir / EXE) == exe_hash,
        observed={'code': code, 'files_untouched': survived})

# ---- 1. uninstall removes the app, leaves everything else ----
uninstall(app_dir)
R.check('installer: uninstall removes app', not (app_dir / EXE).exists() and not (app_dir / '_internal').exists()
        and not (app_dir / 'Uninstall.exe').exists(), observed=listing(app_dir))
R.check('installer: uninstall keeps foreign files', (games / 'keep.txt').is_file() and (games / 'OtherGame' / 'save.dat').is_file()
        and (app_dir / 'notes.txt').is_file(), observed=listing(games))

# A clean install folder disappears completely on uninstall.
clean = TMP / 'Apps' / APP
code = install(clean)
uninstall(clean)
R.check('installer: empty app folder removed', code == 0 and not clean.exists() and (TMP / 'Apps').is_dir(),
        observed={'code': code, 'apps': listing(TMP / 'Apps')})

# ---- 6. shortcuts use the all-users folders in both sections ----
nsi = (ROOT / 'build-scripts' / 'win' / 'installer.nsi').read_text(encoding='utf-8')
macro = nsi.split('!macro RemoveUserShortcuts', 1)[-1].split('!macroend', 1)[0].strip().splitlines()
install_part = nsi.split('Section "Install"', 1)[-1].split('SectionEnd', 1)[0]
uninstall_part = nsi.split('Section "Uninstall"', 1)[-1].split('SectionEnd', 1)[0]


def shortcuts_after_all(part):
    # Context switches to all-users before the first shortcut line in the section.
    first_link = part.index('.lnk')
    return part.index('!insertmacro RemoveUserShortcuts') < first_link


R.check('installer: all-users shortcuts', macro[-1].strip() == 'SetShellVarContext all'
        and shortcuts_after_all(install_part) and shortcuts_after_all(uninstall_part),
        observed={'macro_last_line': macro[-1].strip()})
R.skip('installer: all-users shortcut files on disk', 'writing to the all-users Start menu needs admin; the E2E build runs as the user')

shutil.rmtree(TMP, ignore_errors=True)
R.finish()

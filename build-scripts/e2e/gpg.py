# E2E: release signing with a passphrase-protected key (FAILURE_MODES.md 11).
# Uses a throwaway keyring in a temp GNUPGHOME and a temp release folder; the real ones are untouched.
# Report: e2e-artifacts/gpg.json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report import ROOT, Report  # noqa: E402

R = Report('gpg')
# Git Bash puts its MSYS gpg first on PATH, which mangles Windows paths; prefer native GnuPG.
NATIVE = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'GnuPG' / 'bin'
if sys.platform == 'win32' and (NATIVE / 'gpg.exe').is_file():
    os.environ['PATH'] = str(NATIVE) + os.pathsep + os.environ['PATH']
if not shutil.which('gpg'):
    R.skip('gpg suite', 'gpg not installed')
    R.check('gpg: suite ran', False, observed='skipped', expected='gpg available')
    R.finish()

TMP = Path(tempfile.mkdtemp(prefix='bse-e2e-gpg-'))
home = TMP / 'gnupg'
home.mkdir()
release = TMP / 'release'
release.mkdir()
PASS = 'e2e passphrase with spaces & symbols $x'
env = {**os.environ, 'GNUPGHOME': str(home)}
R.input('gpg', subprocess.run(['gpg', '--version'], capture_output=True, text=True).stdout.splitlines()[0])

gen = subprocess.run(
    ['gpg', '--batch', '--pinentry-mode', 'loopback', '--passphrase-fd', '0',
     '--quick-gen-key', 'BSE E2E <e2e@example.invalid>', 'ed25519', 'sign', '1d'],
    input=PASS + '\n', env=env, capture_output=True, text=True,
)
fpr = next((line.split(':')[9] for line in subprocess.run(
    ['gpg', '--batch', '--with-colons', '--list-secret-keys'], env=env, capture_output=True, text=True,
).stdout.splitlines() if line.startswith('fpr:')), None)
if not R.check('gpg: throwaway key created', gen.returncode == 0 and fpr, observed=gen.stderr[-300:]):
    R.finish()

(release / 'Balatro-Save-Editor-9.9.9-win-x64.exe').write_bytes(b'fake installer for signing')


def sign(passphrase):
    for f in release.glob('*.asc'):
        f.unlink()
    return subprocess.run(
        ['node', str(ROOT / 'build-scripts' / 'gpg-sign.js')],
        env={**env, 'GPG_KEY_ID': fpr, 'GPG_PASSPHRASE': passphrase, 'BSE_RELEASE_DIR': str(release)},
        capture_output=True, text=True,
    )


res = sign(PASS)
sigs = sorted(f.name for f in release.glob('*.asc'))
verify_runs = [subprocess.run(['gpg', '--batch', '--verify', str(release / s), str(release / s[:-4])],
                              env=env, capture_output=True, text=True) for s in sigs]
verify = [v.returncode for v in verify_runs]
R.check('gpg: passphrase via stdin signs', res.returncode == 0 and len(sigs) == 2 and verify == [0, 0],
        observed={'code': res.returncode, 'signatures': sigs, 'verify_codes': verify,
                  'verify_stderr': [v.stderr[-200:] for v in verify_runs if v.returncode], 'stderr': res.stderr[-300:]})

# A wrong passphrase must fail: proves the passphrase really reaches gpg (not a cached unlock).
subprocess.run(['gpgconf', '--kill', 'gpg-agent'], env=env, capture_output=True)
bad = sign('wrong passphrase')
R.check('gpg: wrong passphrase fails', bad.returncode != 0, observed={'code': bad.returncode})

src = (ROOT / 'build-scripts' / 'gpg-sign.js').read_text(encoding='utf-8')
R.check('gpg: passphrase not in gpg arguments', "'--passphrase'," not in src and "'--passphrase-fd', '0'" in src,
        observed='gpg-sign.js passes --passphrase-fd 0 and writes the passphrase to stdin')

subprocess.run(['gpgconf', '--kill', 'gpg-agent'], env=env, capture_output=True)
shutil.rmtree(TMP, ignore_errors=True)
R.finish()

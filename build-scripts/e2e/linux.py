# E2E: build the real Linux bundle in its compatibility container and inspect every ELF file.
# Report: e2e-artifacts/linux.json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report import ROOT, Report  # noqa: E402

R = Report('linux')
package = (ROOT / 'package.json').read_text(encoding='utf-8')
R.check(
    'linux: pinned compatibility build',
    'build:linux' in package and 'build-scripts/build-linux.js' in package,
    observed='package release path',
    expected='build-scripts/build-linux.js',
)

if not shutil.which('docker'):
    R.check('linux: Docker available', False, observed=None, expected='docker on PATH')
    R.finish()

build = subprocess.run(
    ['node', 'build-scripts/build-linux.js'], cwd=ROOT, text=True, capture_output=True,
    env={**os.environ, 'BSE_LINUX_E2E_DOCKER_DESKTOP': '1'},
)
R.check(
    'linux: compatibility bundle builds',
    build.returncode == 0,
    observed={'code': build.returncode, 'tail': (build.stdout + build.stderr)[-1000:]},
    expected=0,
)

bundle = ROOT / 'dist' / 'balatro-save-editor'
if sys.platform == 'linux':
    verify_command = [sys.executable, 'build-scripts/verify-linux-compat.py', str(bundle)]
else:
    verify_command = [
        'docker', 'run', '--rm', '--volume', f'{ROOT}:/project:ro', '--workdir', '/project',
        'balatro-save-editor-linux-build:manylinux_2_28-py312',
        'python', 'build-scripts/verify-linux-compat.py', 'dist/balatro-save-editor',
    ]
verify = subprocess.run(verify_command, cwd=ROOT, text=True, capture_output=True)
R.check(
    'linux: bundle requires glibc 2.28 or older',
    verify.returncode == 0,
    observed={'code': verify.returncode, 'output': (verify.stdout + verify.stderr)[-1000:]},
    expected='maximum GLIBC_2.28',
)

qt_webengine = list(bundle.rglob('libQt6WebEngineCore.so.6'))
R.check(
    'linux: Qt backend bundled',
    bool(qt_webengine),
    observed=[os.fspath(p.relative_to(bundle)) for p in qt_webengine],
    expected='libQt6WebEngineCore.so.6 in bundle',
)

uid = os.getuid() if hasattr(os, 'getuid') else 1000
gid = os.getgid() if hasattr(os, 'getgid') else 1000
started = time.monotonic()
launch = subprocess.run(
    [
        'docker', 'run', '--rm', '--user', f'{uid}:{gid}',
        '--env', 'HOME=/tmp', '--env', 'QT_QPA_PLATFORM=offscreen',
        '--env', 'QT_QUICK_BACKEND=software',
        '--env', 'QTWEBENGINE_DISABLE_SANDBOX=1',
        '--env', 'QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu --disable-software-rasterizer',
        '--volume', f'{ROOT}:/project:ro', '--workdir', '/project',
        'quay.io/pypa/manylinux_2_28_x86_64:2026.05.07-2',
        '/bin/bash', '-lc', 'timeout 8s dist/balatro-save-editor/balatro-save-editor',
    ],
    text=True, capture_output=True,
)
elapsed = time.monotonic() - started
launch_output = launch.stdout + launch.stderr
R.check(
    'linux: frozen app starts on baseline',
    elapsed >= 7 and 'WebViewException' not in launch_output and 'Failed to execute script' not in launch_output,
    observed={'code': launch.returncode, 'seconds': round(elapsed, 1), 'output': launch_output[-1000:]},
    expected='runs at least 7 seconds without a pywebview startup exception',
)
R.finish()

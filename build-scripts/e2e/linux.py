# E2E: build the real Linux bundle in its compatibility container, inspect every ELF file, then
# run it on real X servers with each target distribution's own Mesa (see FAILURE_MODES.md 13-14).
# Report: e2e-artifacts/linux.json, screenshots and app logs in e2e-artifacts/linux/
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report import ROOT, Report, sha256  # noqa: E402

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
    'linux: bundle within the glibc 2.28 baseline',
    verify.returncode == 0,
    observed={'code': verify.returncode, 'output': (verify.stdout + verify.stderr)[-1000:]},
    expected='maximum GLIBC_2.28, GLIBCXX_3.4.25, CXXABI_1.3.11, GCC_7.0.0; no host libraries',
)

host_libs = {
    line.strip()
    for line in (ROOT / 'build-scripts' / 'linux-host-libs.txt').read_text(encoding='utf-8').splitlines()
    if line.strip() and not line.startswith('#')
}
bundled_host_libs = sorted(os.fspath(p.relative_to(bundle)) for p in bundle.rglob('*') if p.name in host_libs)
R.check(
    'linux: host libraries not bundled',
    bundle.is_dir() and not bundled_host_libs,
    observed=bundled_host_libs,
    expected='none of build-scripts/linux-host-libs.txt in bundle',
)

qt_webengine = list(bundle.rglob('libQt6WebEngineCore.so.6'))
R.check(
    'linux: Qt backend bundled',
    bool(qt_webengine),
    observed=[os.fspath(p.relative_to(bundle)) for p in qt_webengine],
    expected='libQt6WebEngineCore.so.6 in bundle',
)


def xwd_to_png(src, dst):
    """Convert a 32-bit TrueColor xwd dump to PNG; return (width, height, distinct colours)."""
    data = src.read_bytes()
    (header_size, _, _, _, width, height, _, byte_order, _, _, _, bits_per_pixel, bytes_per_line,
     _, red_mask, green_mask, blue_mask, _, _, ncolors, *_) = struct.unpack('>25I', data[:100])
    if bits_per_pixel != 32:
        raise ValueError(f'unsupported xwd: {bits_per_pixel} bits per pixel')
    pixels = data[header_size + ncolors * 12:]
    # Byte holding each 8-bit channel within a pixel (byte_order 0 = least significant first).
    index = [m.bit_length() // 8 - 1 if byte_order == 0 else 4 - m.bit_length() // 8
             for m in (red_mask, green_mask, blue_mask)]
    rgb = bytearray(width * height * 3)
    for y in range(height):
        line = pixels[y * bytes_per_line:y * bytes_per_line + width * 4]
        for channel, i in enumerate(index):
            rgb[y * width * 3 + channel:(y + 1) * width * 3:3] = line[i::4]
    colours = len({bytes(rgb[i:i + 3]) for i in range(0, len(rgb), 3)})

    def chunk(tag, body):
        return struct.pack('>I', len(body)) + tag + body + struct.pack('>I', zlib.crc32(tag + body))
    rows = b''.join(b'\0' + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    dst.write_bytes(
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(rows, 9))
        + chunk(b'IEND', b'')
    )
    return width, height, colours


# Real X server + the target's own Mesa, launched like a user would (no offscreen platform or
# software-rendering overrides: the 1.0.3 check used those and missed #17).
TARGETS = [
    ('almalinux8', 'almalinux:8', 'AlmaLinux 8, glibc 2.28 baseline'),
    ('ubuntu22.04', 'ubuntu:22.04', 'Ubuntu 22.04, Linux Mint 21 base'),
    ('ubuntu24.04', 'ubuntu:24.04', 'Ubuntu 24.04, Linux Mint 22 base'),
]
GL_FAILURES = [
    'Could not initialize GLX', 'qglx_findConfig', 'MESA-LOADER: failed', 'failed to load driver',
    'QRhiGles2: Failed', 'GLOzone not found', 'GLIBCXX_', 'CXXABI_', 'Failed to execute script',
]
uid = os.getuid() if hasattr(os, 'getuid') else 1000
gid = os.getgid() if hasattr(os, 'getgid') else 1000
# Sent on stdin as LF bytes: a Windows checkout may have made it CRLF, and a text-mode pipe on
# Windows would turn LF back into CRLF.
desktop_script = (ROOT / 'build-scripts' / 'e2e' / 'linux-desktop.sh').read_bytes().replace(b'\r\n', b'\n')
for name, base, label in TARGETS:
    image = f'balatro-save-editor-e2e-desktop:{name}'
    built = subprocess.run(
        ['docker', 'build', '--file', 'build-scripts/e2e/linux-desktop.Dockerfile',
         '--build-arg', f'BASE={base}', '--tag', image, '.'],
        cwd=ROOT, text=True, capture_output=True,
    )
    if built.returncode != 0:
        R.check(f'linux: {label} image builds', False,
                observed=(built.stdout + built.stderr)[-1000:], expected=0)
        continue
    for stale in R.dir.glob(f'{name}*'):
        stale.unlink()
    run = subprocess.run(
        ['docker', 'run', '--rm', '--interactive', '--user', f'{uid}:{gid}', '--env', 'HOME=/tmp',
         '--volume', f'{ROOT}:/project:ro', '--volume', f'{R.dir}:/out', image,
         'bash', '-s', '--', name, '/project/dist/balatro-save-editor', '/out'],
        input=desktop_script, capture_output=True,
    )
    stdout = run.stdout.decode('utf-8', errors='replace')
    stderr = run.stderr.decode('utf-8', errors='replace')
    result = {}
    for line in stdout.splitlines():
        key, _, value = line.partition('=')
        result.setdefault(key, []).append(value)

    gl_errors = (R.dir / f'{name}-gl.txt').read_text(encoding='utf-8').splitlines() \
        if (R.dir / f'{name}-gl.txt').is_file() else ['(not written)']
    R.check(
        f'linux: host GL stack loads beside bundle ({label})',
        bool(result.get('gl_checked')) and not gl_errors,
        observed={'checked': result.get('gl_checked'), 'errors added by bundle': gl_errors[:20]},
        expected='host Mesa libraries found and no link errors added by the bundle',
    )

    log_file = R.dir / f'{name}.log'
    log = log_file.read_text(encoding='utf-8', errors='replace') if log_file.is_file() else ''
    xwd = R.dir / f'{name}.xwd'
    shot = None
    if xwd.is_file():
        png = R.dir / f'{name}.png'
        width, height, colours = xwd_to_png(xwd, png)
        xwd.unlink()
        R.data['screenshots'].append({'name': name, 'file': png.name, 'sha256': sha256(png)})
        shot = {'file': png.name, 'size': f'{width}x{height}', 'distinct_colours': colours}
    R.check(
        f'linux: renders on real X11 ({label})',
        result.get('window_after', ['never'])[0] != 'never'
        and result.get('alive') == ['yes']
        and shot is not None and shot['distinct_colours'] > 256
        and not any(marker in log for marker in GL_FAILURES),
        observed={
            'window_after_s': result.get('window_after'), 'alive': result.get('alive'),
            'screenshot': shot,
            'gl_failures': [m for m in GL_FAILURES if m in log],
            'log_tail': log[-800:], 'docker': run.returncode, 'stderr': stderr[-300:],
        },
        expected='window shown, painted (>256 colours), still running, no GL failures in log',
    )
R.finish()

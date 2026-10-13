"""Fail when a Linux bundle needs a newer runtime than the glibc 2.28 baseline, or ships a library
the target system must provide (build-scripts/linux-host-libs.txt)."""
import re
import subprocess
import sys
from pathlib import Path

# Newest symbol versions on the manylinux_2_28 baseline (AlmaLinux 8: glibc 2.28, GCC 8 runtime).
# libstdc++ and libgcc_s come from the target system, so the bundle can't need more than this.
MAX_VERSIONS = {
    'GLIBC': (2, 28),
    'GLIBCXX': (3, 4, 25),
    'CXXABI': (1, 3, 11),
    'GCC': (7, 0, 0),
}
SYMBOL_VERSION = re.compile(r'\b(GLIBCXX|CXXABI|GLIBC|GCC)_(\d+(?:\.\d+)*)\b')
HOST_LIBS_FILE = Path(__file__).with_name('linux-host-libs.txt')


def host_libs():
    lines = HOST_LIBS_FILE.read_text(encoding='utf-8').splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith('#')}


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: verify-linux-compat.py BUNDLE_DIR')
    bundle = Path(sys.argv[1])
    if not bundle.is_dir():
        raise SystemExit(f'bundle not found: {bundle}')

    excluded = host_libs()
    scanned = 0
    violations = []
    for path in sorted(p for p in bundle.rglob('*') if p.is_file()):
        try:
            with path.open('rb') as source:
                if source.read(4) != b'\x7fELF':
                    continue
        except OSError as error:
            raise SystemExit(f'cannot read {path}: {error}') from error
        scanned += 1
        if path.name in excluded:
            violations.append(f'{path.relative_to(bundle)}: host library must not be bundled')
        result = subprocess.run(
            ['readelf', '--version-info', '--wide', path], capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise SystemExit(f'readelf failed for {path}: {result.stderr.strip()}')
        required = {}
        for name, version in SYMBOL_VERSION.findall(result.stdout):
            required[name] = max(required.get(name, ()), tuple(map(int, version.split('.'))))
        for name, version in sorted(required.items()):
            if version > MAX_VERSIONS[name]:
                text = '.'.join(map(str, version))
                violations.append(f'{path.relative_to(bundle)}: requires {name}_{text}')

    if not scanned:
        raise SystemExit(f'no ELF files found in {bundle}')
    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        raise SystemExit('Linux bundle exceeds the glibc 2.28 baseline')
    limits = ', '.join(f"{name}_{'.'.join(map(str, v))}" for name, v in MAX_VERSIONS.items())
    print(f'Linux compatibility verified: {scanned} ELF files, maximum {limits}, no host libraries')


if __name__ == '__main__':
    main()

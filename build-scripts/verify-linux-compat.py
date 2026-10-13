"""Fail when an ELF file in a Linux bundle requires glibc newer than 2.28."""
import re
import subprocess
import sys
from pathlib import Path

MAX_GLIBC = (2, 28)
GLIBC_VERSION = re.compile(r'GLIBC_(\d+)\.(\d+)')


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: verify-linux-compat.py BUNDLE_DIR')
    bundle = Path(sys.argv[1])
    if not bundle.is_dir():
        raise SystemExit(f'bundle not found: {bundle}')

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
        result = subprocess.run(
            ['readelf', '--version-info', '--wide', path], capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise SystemExit(f'readelf failed for {path}: {result.stderr.strip()}')
        versions = [tuple(map(int, match)) for match in GLIBC_VERSION.findall(result.stdout)]
        required = max(versions, default=(0, 0))
        if required > MAX_GLIBC:
            violations.append((path.relative_to(bundle), required))

    if not scanned:
        raise SystemExit(f'no ELF files found in {bundle}')
    if violations:
        for path, version in violations:
            print(f'{path}: requires GLIBC_{version[0]}.{version[1]}', file=sys.stderr)
        raise SystemExit(f'Linux bundle exceeds GLIBC_{MAX_GLIBC[0]}.{MAX_GLIBC[1]} baseline')
    print(f'Linux compatibility verified: {scanned} ELF files, maximum GLIBC_2.28')


if __name__ == '__main__':
    main()

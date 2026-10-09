"""Engineering packager: already-built modules + offline Windows wheel dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent


def build(packages, wheels, output):
    entries = {}
    for name in ('provider.lhpkg', 'client.lhpkg', 'package-hashes.json'):
        entries['packages/' + name] = (packages / name).read_bytes()
    for name in ('Start.cmd', 'menu.py', 'sort_shell.py', 'check_kit.py', 'NOTICE.md', 'WINDOWS_README.txt'):
        entries[name] = (HERE / name).read_bytes()
    wheel_files = sorted(wheels.glob('*.whl'))
    if not any(p.name.startswith('academicos-') for p in wheel_files) or not any(
            p.name.startswith('wasmtime-36.0.0-') for p in wheel_files):
        raise ValueError('matching platform and Wasmtime wheels required')
    entries.update({'wheels/' + p.name: p.read_bytes() for p in wheel_files})
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip()
    manifest = {'source_commit': revision, 'target': 'Windows x64 Python 3.12',
                'scope': 'developer trial; no publisher signature or acceptance claim',
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()}}
    entries['KIT_MANIFEST.json'] = (json.dumps(manifest, indent=2, sort_keys=True)+'\n').encode()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('packages', type=Path)
    parser.add_argument('wheels', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.packages, args.wheels, args.output)

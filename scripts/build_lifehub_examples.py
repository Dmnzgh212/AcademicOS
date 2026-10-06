"""Build a reproducible developer examples archive; does not install or grant anything."""

import argparse
from pathlib import Path
import zipfile

README = '''# LifeHub developer examples

Install the matching AcademicOS wheel with its Wasm dependencies in a disposable
virtual environment. This archive contains source examples, not the platform wheel.
Start with examples/lifehub/reader/README.md and examples/lifehub/json_echo/README.md.
Independent shells are in examples/lifehub/catalog_shell and records_shell.

Build scripts generate synthetic plugin ZIPs; building grants no permissions.
Follow explicit review/install/grant/revoke steps in each example README.

To validate an installed wheel against only disposable synthetic storage:
python scripts/lifehub_wheel_smoke.py "$PWD"
This check automatically approves only its synthetic temporary fixtures.
Never substitute personal packages or storage into that smoke script.

The archive is a developer prototype companion, not a published release.
'''


def build(destination):
    repo = Path(__file__).resolve().parents[1]
    paths = sorted(p for p in (repo / 'examples/lifehub').rglob('*')
                   if p.is_file() and p.suffix in {'.py', '.toml', '.wat', '.md'}
                   and '__pycache__' not in p.parts)
    paths.append(repo / 'scripts/lifehub_wheel_smoke.py')
    entries = {'README.md': README.encode()}
    entries.update({p.relative_to(repo).as_posix(): p.read_bytes() for p in paths})
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    build(parser.parse_args().destination)

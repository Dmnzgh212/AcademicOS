"""Build a reproducible developer examples archive; does not install or grant anything."""

import argparse
import hashlib
import json
import subprocess
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

Engine engineering proofs are also included (Linux and Windows only):
python -I examples/lifehub-background-apps/run_demo.py
python -I examples/lifehub-background-apps/run_recovery.py --output /fresh/path/recovery
python -I examples/lifehub-external-energy/independent_proof.py --output /fresh/path/energy
Use an installed matching wheel with wasmtime>=36,<37, outside the source checkout.
The background proof loads the included third-party proof helper by relative path.
These scripts approve only synthetic fixtures and inject real process failures.
Never point them at personal storage. Linux recovery/energy observation needs pidfd support.
SOURCE_MANIFEST.json records checkout commit and per-file SHA256; it is not attestation.
The wheel is supplied separately and must match the source revision. Set GITHUB_SHA
to the source commit when retaining recovery metadata. Keep only allowlisted evidence,
never operator.key, auth files or engine.db. User-facing installation is a separate task.

The archive is a developer prototype companion, not a published release.
'''


def build(destination):
    repo = Path(__file__).resolve().parents[1]
    folders = ('lifehub', 'lifehub-third-party-apps', 'lifehub-background-apps',
               'lifehub-external-energy')
    paths = sorted(p for name in folders for p in (repo / 'examples' / name).rglob('*')
                   if p.is_file() and p.suffix in {'.py', '.toml', '.wat', '.md'}
                   and '__pycache__' not in p.parts)
    paths.extend(repo / 'scripts' / name for name in
                 ('lifehub_wheel_smoke.py', 'check_lifehub_recovery_evidence.py'))
    entries = {'README.md': README.encode()}
    entries.update({p.relative_to(repo).as_posix(): p.read_bytes() for p in paths})
    # Stable identity from this checkout; no timestamps, databases, keys or generated packages.
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, check=True,
                              capture_output=True, text=True).stdout.strip()
    identity = {'source_commit': revision,
                'files': {name: hashlib.sha256(data).hexdigest()
                          for name, data in sorted(entries.items())},
                'scope': 'source companion; wheel supplied separately; no acceptance claim'}
    entries['SOURCE_MANIFEST.json'] = (json.dumps(identity, indent=2, sort_keys=True) + '\n').encode()
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

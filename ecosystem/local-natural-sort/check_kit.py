"""Detect accidental bundle changes; hashes are not signatures or publisher identity."""
import hashlib
import json
from pathlib import Path
import sys


def check(root):
    manifest = json.loads((root / 'KIT_MANIFEST.json').read_text(encoding='utf-8'))
    for name, digest in manifest['files'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError('missing/outside bundle file')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('bundle file changed')


if __name__ == '__main__':
    try:
        check(Path(__file__).resolve().parent)
    except (OSError, ValueError, KeyError):
        print('LHSORT_KIT_INVALID: bundle incomplete or changed.', file=sys.stderr)
        raise SystemExit(1)

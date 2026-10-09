"""Independent local Shell: import, authorize, sort, revoke and uninstall."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CALLER = 'local.sort-shell'
PROVIDER = 'local.natural-sort:sort'


def cli(*args):
    result = subprocess.run([sys.executable, '-I', '-m', 'academicos.lifehub.cli',
                             *map(str, args)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        # Never copy labels, private paths or raw traceback into diagnostics.
        raise RuntimeError(f'LHSORT_OPERATION_FAILED exit={result.returncode}')
    return result.stdout


def run(args):
    root = args.workspace.resolve()
    root.mkdir(parents=True, exist_ok=True)
    options = ['--db', root / 'lifehub.db', '--installed', root / 'installed']

    def confirm(message):
        print(message)
        if not args.yes and input('Type yes to confirm: ').strip() != 'yes':
            raise RuntimeError('LHSORT_CANCELLED')

    if args.action == 'import':
        reviewed = []
        for name in ('provider', 'client'):
            path = args.packages / f'{name}.lhpkg'
            review = cli('review-package', path)
            print(review)
            digest = re.search(r'sha256-content:\s*([0-9a-f]{64})', review)
            if not digest:
                raise RuntimeError('LHSORT_REVIEW_INVALID')
            reviewed.append((path, digest.group(1)))
        confirm('Install reviewed local modules. Installation grants no service authority.')
        for path, digest in reviewed:
            cli('install-package', path, '--approve-hash', digest, *options)
        print('Imported. Use enable to authorize sorting.')
    elif args.action == 'enable':
        review = json.loads(cli('review-service', CALLER, PROVIDER,
                                'lifehub.service-json@1', *options))
        confirm('Allow this Shell to send your entered labels to the local sorting module. '
                'This module has no file/network permission. You can revoke with disable.')
        cli('grant-service', CALLER, PROVIDER, 'lifehub.service-json@1',
            '--approve-hash', review['approval_digest'], *options)
        print('Sorting enabled.')
    elif args.action == 'sort':
        if len(args.labels) > 16 or any(len(s) > 64 or
                any(ord(c) < 32 or ord(c) > 126 for c in s) for s in args.labels):
            raise RuntimeError('LHSORT_INPUT_LIMIT: at most 16 printable ASCII labels, 64 chars each')
        with tempfile.TemporaryDirectory() as temp:
            request = Path(temp) / 'request.json'
            request.write_text(json.dumps(args.labels), encoding='utf-8')
            result = json.loads(cli('call-service', CALLER, PROVIDER,
                                    '--request', request, *options))
        for label in result:
            print(label)
    elif args.action == 'disable':
        cli('revoke-service', CALLER, PROVIDER, 'lifehub.service-json@1', *options)
        print('Sorting authority revoked.')
    else:
        confirm('Uninstall both local modules; grants are invalidated.')
        for name in (CALLER, 'local.natural-sort'):
            cli('uninstall-package', name, *options)
        print('Removed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['import', 'enable', 'sort', 'disable', 'remove'])
    parser.add_argument('labels', nargs='*')
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--packages', type=Path, default=Path('packages'))
    parser.add_argument('--yes', action='store_true', help='Explicit noninteractive approval')
    args = parser.parse_args()
    try:
        run(args)
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(str(exc) if isinstance(exc, RuntimeError) else
              f'LHSORT_ERROR {type(exc).__name__}', file=sys.stderr)
        raise SystemExit(1)

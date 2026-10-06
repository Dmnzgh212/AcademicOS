"""Validate an installed wheel with synthetic packages and temporary storage only."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    repo = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='lifehub-wheel-') as directory:
        work = Path(directory)

        def process(args, *, success=True):
            result = subprocess.run([sys.executable, '-I', *map(str, args)], cwd=work,
                                    text=True, capture_output=True)
            if success and result.returncode != 0:
                raise RuntimeError(result.stderr)
            if not success and (result.returncode == 0 or result.stdout):
                raise RuntimeError('denied execution unexpectedly succeeded or emitted output')
            return result.stdout

        location = process(['-c', 'import academicos; print(academicos.__file__)']).strip()
        if Path(location).resolve().is_relative_to(repo):
            raise RuntimeError('smoke test requires a wheel installation outside the source tree')
        process([repo / 'examples/lifehub/json_echo/build.py', work / 'packages'])
        options = ['--db', work / 'hub.db', '--installed', work / 'installed']

        def cli(*args, success=True):
            return process(['-m', 'academicos.lifehub.cli', *args], success=success)

        # Approval is solely for shipped synthetic fixtures in this disposable directory.
        for name in ('provider', 'caller'):
            archive = work / 'packages' / f'{name}.zip'
            review = cli('review-package', archive)
            digest = re.search(r'sha256-content: ([0-9a-f]{64})', review).group(1)
            cli('install-package', archive, '--approve-hash', digest, *options)
        catalog = json.loads(cli('catalog', '--db', work / 'hub.db', '--plugins', work / 'installed'))
        assert len(catalog['packages']) == 2
        request = work / 'request.json'
        request.write_text('{"message":"wheel smoke"}', encoding='utf-8')
        target = ['example.client', 'example.echo:echo']
        call = ['call-service', *target, '--request', request, *options]
        cli(*call, success=False)
        review = json.loads(cli('review-service', *target, 'lifehub.service-json@1', *options))
        cli('grant-service', *target, 'lifehub.service-json@1', '--approve-hash',
            review['approval_digest'], *options)
        assert json.loads(cli(*call)) == {'message': 'wheel smoke'}
        assert 'Result: 29' in cli('run-wasm', 'example.client:invoke', *options)
        cli('revoke-service', *target, 'lifehub.service-json@1', *options)
        cli(*call, success=False)
        cli('run-wasm', 'example.client:invoke', *options, success=False)
        print('PASS installed wheel: package/catalog/service/guest/revocation')


if __name__ == '__main__':
    main()
